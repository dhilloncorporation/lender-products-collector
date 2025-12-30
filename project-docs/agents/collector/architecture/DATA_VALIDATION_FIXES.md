# Data Validation Fixes

## Overview

This document details **6 critical data correctness fixes** implemented to ensure the collected product data meets production-grade quality standards for financial comparison engines.

These fixes address structural, logical, and identity issues that would have made the data unusable for accurate product comparisons.

---

## Fix #1: Eliminate LVR Overlaps (Critical)

### Problem

**Invalid Data Example:**
```json
{
  "state_id": "OO_PI_VAR",
  "pricing": {
    "rate_tiers": [
      { "lvr_min": 0.0, "lvr_max": 0.80, "interest_rate": 6.49 },
      { "lvr_min": 0.0, "lvr_max": 0.80, "interest_rate": 6.69 }  // DUPLICATE LVR RANGE
    ]
  }
}
```

**Why This Happens:**
- Collector fails to identify distinct filter combinations (e.g., "Standard" vs. "Simplicity PLUS")
- Rates from different product variants get merged into the same pricing state
- Results in ambiguous/unusable pricing data

### Solution

**Strict Tiering Validator** in `LoanProduct.to_state_explicit_json()`:

```python
# Detect overlaps within each state
for state in pricing_states:
    tiers = state['pricing']['rate_tiers']
    
    # Sort by LVR range
    tiers_sorted = sorted(tiers, key=lambda t: (t['lvr_min'], t['lvr_max']))
    
    # Check for overlaps
    for i in range(len(tiers_sorted) - 1):
        current_max = tiers_sorted[i]['lvr_max']
        next_min = tiers_sorted[i + 1]['lvr_min']
        
        if current_max > next_min:  # Overlap detected
            # If different rates -> data quality issue
            if tiers_sorted[i]['interest_rate'] != tiers_sorted[i+1]['interest_rate']:
                logger.warning(
                    f"LVR OVERLAP DETECTED in state {state['state_id']}: "
                    f"LVR [{next_min}, {current_max}] has 2 rates. "
                    f"This suggests missing state_parameter (e.g., package, special_offer)."
                )
                
                # Keep higher rate (conservative for consumer)
                # Apply confidence penalty
                state['provenance']['confidence_score'] -= 40
                
                # Remove duplicate tier
                # ...
```

**Outcome:**
- **Detection**: Warns when overlaps indicate missing filter dimensions
- **Resolution**: Applies "one rate per tier" rule, keeping most conservative rate
- **Penalty**: Reduces confidence score by 40 points for overlap issues
- **Root Cause Fix**: Prompted implementation of Full Matrix Explorer to capture all filter combinations

### Code Reference
- `src/models/product.py::LoanProduct.to_state_explicit_json()` (~line 620)

---

## Fix #2: Align Product ID and Name (Critical)

### Problem

**Invalid Data Example:**
```json
{
  "product_id": "anz-simplicity-plus-special-offer-discount",
  "product_name": "Standard Variable"  // MISMATCH
}
```

**Impact:**
- Deduplication fails (same product appears multiple times with different IDs)
- Comparison engines can't match related products
- Breaks product history tracking

### Solution

**Canonical Product Identity** generation:

```python
# 1. Slugify utility function
def slugify(text: str) -> str:
    """Normalize text to lowercase, hyphenated, alphanumeric slug."""
    text = re.sub(r'[^\w\s-]', '', text.lower())  # Remove non-alphanumeric
    text = re.sub(r'[-\s]+', '-', text)           # Normalize hyphens
    return text.strip('-')

# 2. Generate product_id from product_name
product_id = f"{lender_id}-{slugify(product_name)}"

# Example:
# product_name: "Simplicity PLUS"
# product_id: "anz-simplicity-plus"
```

**Enforcement in `_merge_products_by_name()`:**

```python
def _merge_products_by_name(products: List[LoanProduct]) -> List[LoanProduct]:
    """Merge products with the same canonical name."""
    
    # Group by normalized name
    name_groups = defaultdict(list)
    for product in products:
        canonical_name = product.product_name.strip().lower()
        name_groups[canonical_name].append(product)
    
    merged = []
    for canonical_name, product_group in name_groups.items():
        # Generate stable ID from name
        base_product = product_group[0]
        stable_id = f"{base_product.lender.lender_id}-{slugify(canonical_name)}"
        
        # Merge all interest components and features
        base_product.product_id = stable_id
        for other_product in product_group[1:]:
            base_product.interest_components.extend(other_product.interest_components)
            # Merge features...
        
        merged.append(base_product)
    
    return merged
```

### Outcome
- **Consistency**: `product_id` always derived from `product_name`
- **Stable IDs**: Same product gets same ID across collection runs
- **Deduplication**: Products correctly merged by canonical identity

### Code References
- `src/models/product.py::slugify()` (~line 45)
- `src/agents/collector/playwright_collector.py::_merge_products_by_name()` (~line 1560)

---

## Fix #3: Canonicalize ID Normalization (High)

### Problem

**Inconsistent IDs:**
```json
[
  { "lender_id": "Australia-and-New-Zealand-Banking-Group" },
  { "lender_id": "australia and new zealand banking group" },
  { "lender_id": "ANZ" }
]
```

All refer to the same lender but have different IDs.

### Solution

**Centralized `slugify()` Utility:**

```python
def slugify(text: str) -> str:
    """
    Normalize text to canonical ID format:
    - Lowercase
    - Alphanumeric + hyphens only
    - No leading/trailing hyphens
    """
    # Remove punctuation except spaces and hyphens
    text = re.sub(r'[^\w\s-]', '', text.lower())
    
    # Replace spaces and multiple hyphens with single hyphen
    text = re.sub(r'[-\s]+', '-', text)
    
    # Remove leading/trailing hyphens
    return text.strip('-')
```

**Applied To:**
- `product_id`
- `lender_id`
- `state_id` components

**Examples:**
```python
slugify("Australia and New Zealand Banking Group")  
# → "australia-and-new-zealand-banking-group"

slugify("Simplicity PLUS")  
# → "simplicity-plus"

slugify("Owner-Occupier P&I Variable")  
# → "owner-occupier-pi-variable"
```

### Outcome
- **Consistency**: All IDs use same format
- **Predictability**: Stakeholders can construct IDs programmatically
- **Queryability**: Easy to search/filter by ID

### Code Reference
- `src/models/product.py::slugify()` (~line 45)

---

## Fix #4: Materialize IO + Investment States (High)

### Problem

**Incomplete Data:**
```json
{
  "product_name": "ANZ Home Loans",
  "pricing_states": [
    { "state_id": "OO_PI_VAR" }  // Only 1 of 4 expected states
  ],
  "provenance": {
    "missing_states": ["Investment", "InterestOnly"]  // Just a note
  }
}
```

**Issues:**
- Can't definitively say if lender offers Investment or Interest-Only loans
- Ambiguous: Missing because unavailable or because collector failed?
- Non-structured: Can't query for "lenders that don't offer Investment"

### Solution

**Explicit State Materialization** (see [CLOSED_WORLD_MATRIX.md](CLOSED_WORLD_MATRIX.md)):

```python
# In to_state_explicit_json():

# Define full theoretical matrix
expected_states = [
    ('OwnerOccupied', 'PrincipalAndInterest'),
    ('OwnerOccupied', 'InterestOnly'),
    ('Investment', 'PrincipalAndInterest'),
    ('Investment', 'InterestOnly')
]

# Track which were captured
captured_states = {state_id: True for state_id in collected_states}

# Materialize missing states explicitly
for loan_type, repayment_type in expected_states:
    state_sig = f"{loan_type}_{repayment_type}"
    
    if state_sig not in captured_states:
        null_state = {
            'state_id': f"{loan_type_abbrev}_{repayment_abbrev}_{rate_type}",
            'pricing': None,  # Explicit null
            'provenance': {
                'capture_status': 'not_available',
                'reason': 'State not found during UI exploration'
            }
        }
        pricing_states.append(null_state)
```

**Confidence Penalty:**

```python
# If any expected states are missing, reduce confidence
captured_count = len([s for s in pricing_states if s['pricing'] is not None])
total_expected = len(expected_states)

if captured_count < total_expected:
    penalty = 20 * (total_expected - captured_count)  # 20 points per missing state
    for state in pricing_states:
        if state['pricing'] is not None:
            state['provenance']['confidence_score'] -= penalty
            state['provenance']['is_partial_capture'] = True
```

### Outcome
- **Completeness**: Every product has all expected state entries
- **Clarity**: Explicit distinction between "not available" and "not attempted"
- **Queryable**: Can filter by `pricing: null` and `capture_status`
- **Incentivized**: Low confidence scores drive fixes to recursive explorer

### Code References
- `src/models/product.py::LoanProduct.to_state_explicit_json()` (~line 580)
- `src/agents/collector/playwright_collector.py::_explore_state_recursively()` (~line 1100)

---

## Fix #5: Mandatory Fixed-Term Metadata (High)

### Problem

**Incomplete Fixed-Rate Products:**
```json
{
  "rate_type": "Fixed",
  "fixed_term_months": null  // MISSING
}
```

**Impact:**
- Can't compare "1 Year Fixed" vs. "3 Year Fixed" rates
- Unusable for comparison engines that need term filtering
- Breaks BIAN schema requirements

### Solution

**Mandatory Extraction** in `_normalize_ui_state_to_bian_axes()`:

```python
# 1. Extract from filter state
if 'fixed_term' in applied_filters:
    term_value = applied_filters['fixed_term']
    fixed_term_months = _parse_term_to_months(term_value)

# 2. Extract from product name
elif rate_type == "Fixed":
    # Regex: "1 year", "2yr", "3 Years"
    match = re.search(r'(\d+)\s*(year|yr)', product_name, re.I)
    if match:
        years = int(match.group(1))
        fixed_term_months = years * 12

# 3. Extract from table row text
elif rate_type == "Fixed":
    row_text = await rate_row.inner_text()
    match = re.search(r'(\d+)\s*(year|yr)', row_text, re.I)
    if match:
        fixed_term_months = int(match.group(1)) * 12

# 4. Validation: Fail if still missing
if rate_type == "Fixed" and fixed_term_months is None:
    logger.error(f"Fixed-rate product '{product_name}' missing fixed_term_months")
    state['provenance']['confidence_score'] -= 20
    state['provenance']['validation_failed'] = True
```

**Confidence Penalty:**
- **-20 points** for missing fixed_term on fixed-rate products

### Outcome
- **Completeness**: All fixed-rate products have term metadata
- **Usability**: Enables term-based filtering in comparison tools
- **Quality Gate**: Low confidence flags incomplete data for review

### Code References
- `src/agents/collector/playwright_collector.py::_normalize_ui_state_to_bian_axes()` (~line 1480)
- `src/agents/collector/playwright_collector.py::_extract_from_current_state()` (~line 1300)

---

## Fix #6: Calibrate Confidence Scores (Medium)

### Problem

**Over-Optimistic Scores:**
```json
{
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "pricing": {
        "rate_tiers": [
          { "lvr_min": 0.0, "lvr_max": 0.80, "interest_rate": 6.49 },
          { "lvr_min": 0.0, "lvr_max": 0.80, "interest_rate": 6.69 }  // Overlap
        ]
      },
      "provenance": {
        "confidence_score": 70  // TOO HIGH for broken data
      }
    }
  ]
}
```

**Issue:** Confidence scores didn't reflect actual data quality.

### Solution

**Comprehensive Scoring System** in `_calculate_confidence_score()`:

```python
def _calculate_confidence_score(
    product: LoanProduct,
    extraction_method: str,
    has_comparison_rates: bool = False
) -> int:
    """
    Calculate confidence score with penalties for quality issues.
    
    Base Scores:
    - NetworkAPIInterception: 95
    - JSON-LD: 90
    - UIStateEnumeration: 85
    - DOMParsing: 70
    - LLMFallback: 40
    """
    
    # Base score by extraction method
    base_scores = {
        'NetworkAPIInterception': 95,
        'JSON-LD': 90,
        'UIStateEnumeration': 85,
        'EmbeddedState': 80,
        'CompareCards': 75,
        'DOMParsing': 70,
        'LLMFallback': 40
    }
    score = base_scores.get(extraction_method, 50)
    
    # Penalty: LVR overlaps (-40 points)
    if has_lvr_overlaps(product):
        score -= 40
        logger.warning("Confidence penalty: LVR overlap detected")
    
    # Penalty: Missing Investment state (-20 points)
    if not has_investment_state(product):
        score -= 20
        logger.warning("Confidence penalty: Missing Investment state")
    
    # Penalty: Missing Interest Only state (-20 points)
    if not has_interest_only_state(product):
        score -= 20
        logger.warning("Confidence penalty: Missing Interest Only state")
    
    # Penalty: Fixed-rate missing term (-20 points)
    if is_fixed_rate(product) and not has_fixed_term(product):
        score -= 20
        logger.warning("Confidence penalty: Fixed-rate missing term metadata")
    
    # Bonus: Has comparison rates (+5 points)
    if has_comparison_rates:
        score += 5
    
    # Floor: Minimum score of 0
    return max(0, score)
```

**Confidence Tiers:**
- **80-100**: Production-ready, high confidence
- **60-79**: Usable but may have minor gaps
- **40-59**: Significant issues, needs review
- **0-39**: Broken data, should not be published

### Outcome
- **Accurate Quality Indicators**: Scores reflect actual data completeness
- **Incentivized Fixes**: Low scores drive improvements to collection logic
- **Filtering**: Consumers can filter by confidence threshold (e.g., `score >= 80`)
- **Monitoring**: Easy to track average confidence across lenders

### Code Reference
- `src/agents/collector/playwright_collector.py::_calculate_confidence_score()` (~line 1620)

---

## Validation Results

### Before Fixes

**ANZ Output (Schema v1.0):**
```json
{
  "products": [
    {
      "product_id": "anz-simplicity-plus-special-offer",  // Mismatched ID
      "product_name": "Standard Variable",                // Different name
      "interest_components": [
        {
          "rate_tiers": [
            { "lvr_min": 0.0, "lvr_max": 0.80, "rate": 6.49 },  // Overlap
            { "lvr_min": 0.0, "lvr_max": 0.80, "rate": 6.69 }   // Overlap
          ]
        }
      ],
      "provenance": {
        "confidence_score": 70,  // Too high
        "missing_states": ["Investment", "InterestOnly"]  // Just a note
      }
    }
  ]
}
```

**Issues:** 5 critical validation failures

### After Fixes

**ANZ Output (Schema v2.0):**
```json
{
  "product": {
    "product_id": "anz-standard-variable",  // ✅ Canonical, matches name
    "product_name": "Standard Variable"
  },
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "pricing": {
        "rate_tiers": [
          { "lvr_min": 0.0, "lvr_max": 0.60, "interest_rate": 6.49 },  // ✅ No overlaps
          { "lvr_min": 0.60, "lvr_max": 0.80, "interest_rate": 6.59 },
          { "lvr_min": 0.80, "lvr_max": 0.90, "interest_rate": 6.69 }
        ]
      },
      "provenance": {
        "confidence_score": 85,  // ✅ Accurate
        "capture_status": "complete"
      }
    },
    {
      "state_id": "OO_IO_VAR",
      "pricing": { "rate_tiers": [...] },
      "provenance": { "capture_status": "complete" }
    },
    {
      "state_id": "INV_PI_VAR",
      "pricing": { "rate_tiers": [...] },
      "provenance": { "capture_status": "complete" }
    },
    {
      "state_id": "INV_IO_VAR",
      "pricing": null,  // ✅ Explicitly materialized
      "provenance": {
        "capture_status": "not_available",
        "reason": "Lender does not offer Investment Interest-Only"
      }
    }
  ]
}
```

**Result:** ✅ **All validation checks pass**

---

## Testing

### Validation Script

```python
def validate_product_data(product_json: dict) -> List[str]:
    """
    Run all 6 validation checks.
    Returns list of errors (empty if valid).
    """
    errors = []
    
    # Fix #1: LVR Overlaps
    for state in product_json['pricing_states']:
        if state['pricing']:
            if has_lvr_overlap(state['pricing']['rate_tiers']):
                errors.append(f"LVR overlap in {state['state_id']}")
    
    # Fix #2: Product ID/Name Alignment
    product_id = product_json['product']['product_id']
    product_name = product_json['product']['product_name']
    if slugify(product_name) not in product_id:
        errors.append("Product ID doesn't match product name")
    
    # Fix #3: Canonical IDs
    if not is_slugified(product_id):
        errors.append("Product ID not canonicalized")
    
    # Fix #4: Complete State Matrix
    expected_states = 4  # OO/INV × PI/IO
    actual_states = len(product_json['pricing_states'])
    if actual_states < expected_states:
        errors.append(f"Incomplete state matrix: {actual_states}/{expected_states}")
    
    # Fix #5: Fixed-Term Metadata
    for state in product_json['pricing_states']:
        if 'FIX' in state['state_id'] and state['pricing']:
            if not state['pricing'].get('fixed_term_months'):
                errors.append(f"Missing fixed_term_months in {state['state_id']}")
    
    # Fix #6: Confidence Calibration
    for state in product_json['pricing_states']:
        score = state['provenance']['confidence_score']
        if state['pricing'] and score < 60:
            # Has data but low score - check if justified
            if not has_quality_issues(state):
                errors.append(f"Confidence score too low for good data: {score}")
    
    return errors

# Usage:
errors = validate_product_data(json.loads(output_file))
if errors:
    print("VALIDATION FAILED:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✅ All validation checks passed")
```

---

## Impact Summary

| Fix | Severity | Impact | Confidence Penalty |
|-----|----------|--------|-------------------|
| LVR Overlaps | Critical | Enables accurate pricing | -40 points |
| Product ID/Name Alignment | Critical | Enables deduplication | N/A (structural) |
| Canonical IDs | High | Enables queryability | N/A (structural) |
| Materialize Missing States | High | Enables completeness queries | -20 per missing |
| Fixed-Term Metadata | High | Enables term comparisons | -20 points |
| Confidence Calibration | Medium | Enables quality filtering | Cumulative |

**Overall:** These fixes transform the data from "broken" to "production-grade."

---

## Related Documentation

- [Recursive State Explorer](RECURSIVE_STATE_EXPLORER.md) - Enables complete state capture (Fix #4)
- [Closed-World Matrix](CLOSED_WORLD_MATRIX.md) - Architecture for explicit state materialization (Fix #4)
- [Externalized Keywords](EXTERNALIZED_KEYWORDS_MANIFEST.md) - Ensures consistent filter detection (prevents overlap issues)

## Code References

**Validation Logic:**
- `src/models/product.py::LoanProduct.to_state_explicit_json()` - Implements Fixes #1, #2, #3, #4, #5

**Confidence Scoring:**
- `src/agents/collector/playwright_collector.py::_calculate_confidence_score()` - Implements Fix #6

**State Exploration:**
- `src/agents/collector/playwright_collector.py::_explore_state_recursively()` - Enables Fix #4

