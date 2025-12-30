# Closed-World Matrix Materialization

## Overview

The **Closed-World Matrix** is a data completeness pattern that explicitly materializes **all theoretical pricing states**, including those for which no data was found. This transforms the output from a "list of what we found" into a "complete map of the lender's offering."

## Problem Statement

### Before: Omission Model
```json
{
  "product_name": "ANZ Home Loans",
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "pricing": { "rate_tiers": [...] }
    }
  ],
  "provenance": {
    "missing_states": ["Investment", "InterestOnly"]
  }
}
```

**Issues:**
- Ambiguity: Is data missing because we didn't look, or because it doesn't exist?
- Non-queryable: Can't easily answer "Does this lender offer Investment loans?"
- Incomplete: Missing states are just a note, not structured data

### After: Materialization Model
```json
{
  "product_name": "ANZ Home Loans",
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "pricing": { "rate_tiers": [...] },
      "provenance": { "capture_status": "complete" }
    },
    {
      "state_id": "INV_PI_VAR",
      "pricing": null,
      "provenance": {
        "capture_status": "not_available",
        "reason": "UI state present but pricing not displayed"
      }
    },
    {
      "state_id": "OO_IO_VAR",
      "pricing": { "rate_tiers": [...] },
      "provenance": { "capture_status": "complete" }
    },
    {
      "state_id": "INV_IO_VAR",
      "pricing": null,
      "provenance": {
        "capture_status": "not_available",
        "reason": "State not found during UI exploration"
      }
    }
  ]
}
```

**Benefits:**
- **Explicit**: Clear distinction between "unavailable" and "not captured"
- **Queryable**: Can definitively answer product availability questions
- **Complete**: Every theoretical state is accounted for

## Architecture

### 1. Define the Theoretical Matrix

Before extraction, the system identifies all possible combinations:

```python
# Example for a Variable Rate product
expected_states = [
    ('OwnerOccupied', 'PrincipalAndInterest'),
    ('OwnerOccupied', 'InterestOnly'),
    ('Investment', 'PrincipalAndInterest'),
    ('Investment', 'InterestOnly')
]
```

For Fixed Rate products, this multiplies by the number of available terms:
```python
# e.g., Fixed 1yr, 2yr, 3yr, 4yr, 5yr
# = 4 loan/repayment combinations × 5 terms = 20 expected states
```

### 2. Track Captured States

During recursive exploration, the system records which states were successfully captured:

```python
captured_states = {
    "OO_PI_VAR": True,
    "OO_IO_VAR": True,
    # INV_PI_VAR and INV_IO_VAR were not found
}
```

### 3. Materialize Missing States

In `LoanProduct.to_state_explicit_json()`, after grouping captured states:

```python
for loan_type, repayment_type in expected_states:
    state_sig = f"{loan_type}_{repayment_type}"
    
    if state_sig not in captured_states:
        # Create EXPLICIT null-state entry
        null_state = {
            'state_id': f"{loan_type_abbrev}_{repayment_abbrev}_{rate_type}",
            'state_parameters': {
                'loan_type': loan_type,
                'repayment_type': repayment_type
            },
            'pricing': None,  # Explicitly null
            'provenance': {
                'extraction_method': 'not_attempted',
                'extraction_strategy': 'matrix_materialization',
                'confidence_score': 0,
                'capture_status': 'not_available',
                'reason': 'State not found during UI exploration'
            }
        }
        pricing_states.append(null_state)
```

### 4. Provenance Upgrade

Capture status is now **state-level**, not product-level:

**Old (Product-Level):**
```json
{
  "provenance": {
    "capture_status": "partial",
    "missing_states": ["Investment", "InterestOnly"]
  }
}
```

**New (State-Level):**
```json
{
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "provenance": { "capture_status": "complete" }
    },
    {
      "state_id": "INV_IO_VAR",
      "provenance": { 
        "capture_status": "not_available",
        "reason": "Lender does not offer this combination"
      }
    }
  ]
}
```

## Capture Status Values

### `complete`
- Pricing data successfully extracted
- All required fields populated
- High confidence score (typically 80+)

### `not_available`
- State combination exists in UI but no pricing displayed
- OR state was not found during exploration
- Pricing field is `null`
- Reason field explains why

### `failed`
- Extraction was attempted but encountered an error
- Pricing field is `null`
- Error details in reason field

### `partial`
- Some pricing data captured but incomplete
- May be missing LVR tiers or comparison rates
- Reduced confidence score (typically 40-70)

## Confidence Score Calibration

The matrix completeness affects confidence scoring:

### All States Accounted For
If all expected states are either captured or explicitly unavailable:
```python
if captured_count + unavailable_count == total_count:
    for state in captured_states:
        state['confidence_score'] = max(80, original_confidence)
```

### Partial Matrix
If some states are genuinely missing (not explored):
```python
if captured_count < total_count:
    penalty = 20  # Or more based on severity
    for state in captured_states:
        state['confidence_score'] = max(30, original_confidence - penalty)
        state['capture_status'] = 'partial'
```

## Disambiguation: Unavailable vs. Missing

### Scenario 1: UI Shows "Not Available"
```python
# During recursive exploration:
if "not available" in page_text.lower() or "unavailable" in page_text.lower():
    return explicit_unavailable_state(
        reason="Lender explicitly states product not available for this combination"
    )
```

**Result:** `capture_status: "not_available"` with high confidence this is intentional

### Scenario 2: State Never Explored
```python
# In to_state_explicit_json():
if state_sig not in captured_states:
    return materialized_null_state(
        reason="State not found during UI exploration"
    )
```

**Result:** `capture_status: "not_available"` but with lower confidence (might be collector limitation)

### Scenario 3: Extraction Failed
```python
# During collection:
try:
    pricing_data = extract_rates(page)
except Exception as e:
    return failed_state(
        reason=f"Extraction error: {str(e)}"
    )
```

**Result:** `capture_status: "failed"` - technical issue, should be re-attempted

## Benefits

### For Data Consumers

**Query:** "Which lenders offer Investment Interest-Only loans?"

**With Omission Model:**
```python
# Ambiguous - absence could mean "not offered" or "not captured"
lenders_with_inv_io = [
    lender for lender in data 
    if any(s['state_id'] == 'INV_IO_VAR' for s in lender['pricing_states'])
]
```

**With Materialization Model:**
```python
# Definitive - we know exactly which lenders offer it
lenders_with_inv_io = [
    lender for lender in data
    if any(
        s['state_id'] == 'INV_IO_VAR' and s['pricing'] is not None
        for s in lender['pricing_states']
    )
]

# And which explicitly don't:
lenders_without_inv_io = [
    lender for lender in data
    if any(
        s['state_id'] == 'INV_IO_VAR' and s['capture_status'] == 'not_available'
        for s in lender['pricing_states']
    )
]
```

### For Data Quality

- **Validation**: Can assert that every product has exactly N expected states
- **Monitoring**: Track ratio of complete vs. unavailable vs. failed states
- **Debugging**: Immediately see which specific state combinations are problematic

### For Comparison Engines

- **Accurate Filtering**: Don't show "ANZ" in results for Investment loans if explicitly unavailable
- **User Messaging**: Can say "ANZ doesn't offer this product type" vs. "We couldn't find this data"
- **Coverage Reports**: Track which lenders have complete data vs. partial coverage

## Implementation

### Code References

**State Materialization:**
- `src/models/product.py::LoanProduct.to_state_explicit_json()` (lines ~580-650)

**Unavailable Detection:**
- `src/agents/collector/playwright_collector.py::_extract_from_current_state()` (lines ~1250-1280)

**Recursive Explorer:**
- `src/agents/collector/playwright_collector.py::_explore_state_recursively()` (lines ~1100-1230)

### Configuration

The expected state matrix is derived from:
- **`filter_keywords.yaml`** - Defines standard loan_type and repayment_type values
- **Dynamic Discovery** - Rate types and fixed terms discovered during collection
- **BIAN Schema** - Defines canonical state parameter names

## Related Documentation

- [Recursive State Explorer](RECURSIVE_STATE_EXPLORER.md) - How states are discovered
- [Data Validation Fixes](DATA_VALIDATION_FIXES.md) - Quality improvements
- Schema v2.0.0 State-Explicit Model documentation

## Future Enhancements

1. **Re-collection Optimization**: Only re-explore `failed` states, skip confirmed `not_available`
2. **Lender Profiles**: Build "capability matrices" showing what each lender offers
3. **Temporal Tracking**: Detect when lenders add/remove product types over time
4. **Confidence Calibration**: ML model to predict if `not_available` is collector error or genuine unavailability

