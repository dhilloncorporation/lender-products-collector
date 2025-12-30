# Externalized Keywords Manifest

## Overview

The **Externalized Keywords Architecture** is a configuration-driven approach where all semantic keywords, selectors, and UI interaction patterns are defined in YAML configuration files rather than hardcoded in Python, ensuring the collector remains generic, maintainable, and easily adaptable to new lenders.

## Design Principles

### 1. Zero Hardcoded Strings
**Before:**
```python
# BAD: Hardcoded in Python
if "interest only" in text.lower() or "IO" in text:
    filter_type = "repayment_type"
```

**After:**
```python
# GOOD: Externalized to YAML
if any(keyword in text.lower() for keyword in _filter_keywords.INTEREST_ONLY_KEYWORDS):
    filter_type = "repayment_type"
```

### 2. Single Source of Truth
All semantic concepts defined once in `filter_keywords.yaml`:
```yaml
repayment_type:
  interest_only_keywords:
    - "interest only"
    - "interest-only"
    - "io"
    - "int only"
```

### 3. Lender-Agnostic Logic
The collector code contains **zero** lender-specific logic. All variations are captured in configuration:
```yaml
rate_type:
  fixed_keywords:
    # Standard terms
    - "fixed"
    - "fixed rate"
    # Lender-specific variations
    - "locked rate"      # Some credit unions
    - "set rate"         # Commonwealth Bank variant
```

## Architecture

### Configuration Files

#### 1. `filter_keywords.yaml`
**Location:** `src/configs/filter_keywords.yaml`

**Sections:**
```yaml
loan_type:          # Owner Occupied, Investment, etc.
rate_type:          # Variable, Fixed
repayment_type:     # P&I, Interest Only
region_residency:   # States/territories
lvr_bands:          # Loan-to-value ratios
special_filters:    # New to bank, first home buyer, etc.
ui_interactions:    # Show more, reset, calculator detection
```

#### 2. `FilterKeywordManager`
**Location:** `src/agents/collector/filter_keywords.py`

**Responsibilities:**
- Load and parse `filter_keywords.yaml`
- Provide type-safe property accessors
- Handle environment variable substitution (future)
- Validate keyword schema

### Integration Pattern

**Every semantic check in the codebase:**

```python
from src.agents.collector.filter_keywords import _filter_keywords

# Identify loan type
if any(kw in text_lower for kw in _filter_keywords.OWNER_OCCUPIED_KEYWORDS):
    loan_type = "OwnerOccupied"
elif any(kw in text_lower for kw in _filter_keywords.INVESTMENT_KEYWORDS):
    loan_type = "Investment"

# Identify rate type  
if any(kw in text_lower for kw in _filter_keywords.VARIABLE_KEYWORDS):
    rate_type = "Variable"
elif any(kw in text_lower for kw in _filter_keywords.FIXED_KEYWORDS):
    rate_type = "Fixed"

# Identify repayment type
if any(kw in text_lower for kw in _filter_keywords.PRINCIPAL_AND_INTEREST_KEYWORDS):
    repayment_type = "PrincipalAndInterest"
elif any(kw in text_lower for kw in _filter_keywords.INTEREST_ONLY_KEYWORDS):
    repayment_type = "InterestOnly"

# UI interactions
show_more_selector = " | ".join(_filter_keywords.SHOW_MORE_PATTERNS)
reset_selector = " | ".join(_filter_keywords.RESET_PATTERNS)

# Calculator detection
calc_indicators = _filter_keywords.CALCULATOR_INDICATORS
```

## Complete Keyword Coverage

### Filter Group Keywords

#### Loan Type (Purpose)
```yaml
loan_type:
  owner_occupied_keywords:
    - "owner occupier"
    - "owner-occupier"
    - "home to live in"
    - "live in"
    - "own home"
    - "primary residence"
    
  investment_keywords:
    - "investment"
    - "investor"
    - "rental"
    - "rental property"
    - "investment property"
```

**Usage:**
- Filter detection in `_identify_filter_groups()`
- State normalization in `_normalize_ui_state_to_bian_axes()`
- BIAN mapping in product models

#### Rate Type
```yaml
rate_type:
  variable_keywords:
    - "variable"
    - "variable rate"
    - "floating"
    - "floating rate"
    - "standard variable"
    
  fixed_keywords:
    - "fixed"
    - "fixed rate"
    - "locked"
    - "locked rate"
```

**Usage:**
- Rate type classification
- Product categorization
- Fixed term extraction triggers

#### Repayment Type
```yaml
repayment_type:
  principal_and_interest_keywords:
    - "principal and interest"
    - "principal & interest"
    - "p&i"
    - "pi"
    - "p & i"
    - "repaying principal"
    
  interest_only_keywords:
    - "interest only"
    - "interest-only"
    - "io"
    - "int only"
    - "interest only period"
```

**Usage:**
- Critical for discovering Interest Only toggles
- BIAN `repayment_type` field mapping
- Eligibility criteria extraction

### UI Interaction Patterns

#### Show More Buttons
```yaml
ui_interactions:
  show_more_patterns:
    - "button:has-text('Show more')"
    - "button:has-text('Load more')"
    - "button:has-text('See more')"
    - "a:has-text('Show more')"
    - "[class*='show-more']"
    - "[class*='load-more']"
```

**Usage:** `_click_show_more_buttons()`

#### Reset/Clear Filters
```yaml
ui_interactions:
  reset_patterns:
    - "button:has-text('Reset')"
    - "button:has-text('Clear all')"
    - "button:has-text('Clear filters')"
    - "a:has-text('Reset')"
    - "[class*='reset']"
    - "[class*='clear-all']"
```

**Usage:** `_find_reset_button()`, `_explore_state_recursively()`

#### Numeric Input Fields
```yaml
ui_interactions:
  numeric_input_fields:
    loan_amount:
      - "input[name*='loan'][name*='amount']"
      - "input[id*='loanAmount']"
      - "input[placeholder*='loan amount']"
      
    property_value:
      - "input[name*='property'][name*='value']"
      - "input[id*='propertyValue']"
      - "input[placeholder*='property value']"
```

**Usage:** `_fill_numeric_inputs()`

#### Calculator Detection
```yaml
ui_interactions:
  calculator_indicators:
    - "estimated rate"
    - "your rate"
    - "calculate"
    - "calculator"
    - "example rate"
    - "repayment calculator"
    - "how much could i borrow"
```

**Usage:** `_is_calculator_widget()`

### Metadata Keywords

#### Region/Residency
```yaml
region_residency:
  australian_states:
    - "nsw"
    - "new south wales"
    - "vic"
    - "victoria"
    - "qld"
    - "queensland"
    # ... all states/territories
```

**Usage:** Eligibility criteria extraction

#### Special Filters
```yaml
special_filters:
  new_to_bank:
    - "new to bank"
    - "new customer"
    - "switching bonus"
    
  first_home_buyer:
    - "first home buyer"
    - "first home"
    - "fhb"
```

**Usage:** Product feature detection, eligibility rules

## Benefits

### 1. Maintainability

**Single Update Point:**
- Add new lender variation? Update YAML only
- Need to support non-English terms? Add to YAML
- Regional terminology differences? Configure in YAML

**No Code Redeployment:**
- YAML changes don't require code compilation
- Can hot-reload configurations (future enhancement)
- Version control for keywords separate from code logic

### 2. Transparency

**Auditable Decisions:**
```python
# In logs:
logger.debug(f"Matched keyword '{matched_kw}' from filter_keywords.INTEREST_ONLY_KEYWORDS")
```

**Stakeholder Visibility:**
- Business analysts can review keyword lists
- No need to understand Python to see what terms are recognized
- Easy to demonstrate coverage to clients

### 3. Extensibility

**Adding New Lender:**
1. Review their terminology on website
2. Add variations to `filter_keywords.yaml`
3. Run collection - no code changes needed

**Supporting New Filter Types:**
```yaml
# New filter type discovered
credit_score_range:
  excellent_keywords:
    - "excellent credit"
    - "credit score 750+"
  good_keywords:
    - "good credit"
    - "credit score 650-750"
```

Then in code:
```python
# Generic pattern works automatically
if any(kw in text for kw in _filter_keywords.EXCELLENT_CREDIT_KEYWORDS):
    filter_value = "ExcellentCredit"
```

### 4. Testing

**Keyword Coverage Tests:**
```python
def test_all_keywords_loaded():
    assert len(_filter_keywords.OWNER_OCCUPIED_KEYWORDS) > 0
    assert len(_filter_keywords.INVESTMENT_KEYWORDS) > 0
    assert len(_filter_keywords.SHOW_MORE_PATTERNS) > 0

def test_no_hardcoded_strings():
    # Parse Python files, ensure no lender-specific strings
    forbidden = ["owner occupier", "investment", "interest only"]
    for py_file in collector_files:
        assert not any(term in py_file.lower() for term in forbidden)
```

## Code Organization

### Keyword Manager Properties

**File:** `src/agents/collector/filter_keywords.py`

```python
class FilterKeywords:
    def __init__(self):
        self._keywords = self._load_keywords()
    
    @property
    def OWNER_OCCUPIED_KEYWORDS(self) -> List[str]:
        return self._keywords.get("loan_type", {}).get("owner_occupied_keywords", [])
    
    @property
    def INVESTMENT_KEYWORDS(self) -> List[str]:
        return self._keywords.get("loan_type", {}).get("investment_keywords", [])
    
    @property
    def VARIABLE_KEYWORDS(self) -> List[str]:
        return self._keywords.get("rate_type", {}).get("variable_keywords", [])
    
    # ... ~30 more properties covering all keyword categories
```

**Global Instance:**
```python
_filter_keywords = FilterKeywords()
```

### Usage in Collector

**Every semantic check references keywords:**

```python
# playwright_collector.py

from src.agents.collector.filter_keywords import _filter_keywords

# In _identify_filter_groups():
if any(kw in text_lower for kw in _filter_keywords.OWNER_OCCUPIED_KEYWORDS):
    # ...

# In _normalize_ui_state_to_bian_axes():
if any(kw in filter_value.lower() for kw in _filter_keywords.INVESTMENT_KEYWORDS):
    # ...

# In _fill_numeric_inputs():
for field_name, patterns in _filter_keywords.NUMERIC_INPUT_FIELDS.items():
    # ...

# In _is_calculator_widget():
for indicator in _filter_keywords.CALCULATOR_INDICATORS:
    # ...
```

## Migration Checklist

✅ **Completed:**
- [x] All filter detection keywords externalized
- [x] All UI interaction patterns externalized
- [x] Calculator detection keywords externalized
- [x] `FilterKeywordManager` implemented
- [x] Global `_filter_keywords` instance created
- [x] All collector code updated to use keywords
- [x] Zero hardcoded semantic strings in Python

## Validation

### Pre-Deployment Check

Run this before any deployment:

```bash
# 1. YAML syntax validation
python -c "import yaml; yaml.safe_load(open('src/configs/filter_keywords.yaml'))"

# 2. Keyword manager initialization test
python -c "from src.agents.collector.filter_keywords import _filter_keywords; print(len(_filter_keywords.OWNER_OCCUPIED_KEYWORDS))"

# 3. Hardcoded string search (should return nothing)
grep -r "interest only\|owner occupier\|investment" src/agents/collector/playwright_collector.py
```

### Runtime Verification

```python
# In logs during collection:
INFO: Loaded 127 keywords from filter_keywords.yaml
DEBUG: Matched 'interest-only' against INTEREST_ONLY_KEYWORDS
DEBUG: Using selector from SHOW_MORE_PATTERNS: "button:has-text('Show more')"
```

## Future Enhancements

### 1. Per-Lender Overrides

```yaml
# lenders.json
{
  "id": "anz",
  "keyword_overrides": {
    "rate_type": {
      "fixed_keywords": ["locked", "fixed"]  // ANZ-specific only
    }
  }
}
```

### 2. Multi-Language Support

```yaml
# filter_keywords_en_AU.yaml (Australian English)
# filter_keywords_en_US.yaml (US English - mortgages)
# filter_keywords_zh_CN.yaml (Chinese)
```

### 3. Dynamic Keyword Learning

```python
# Suggest keywords based on unmatched text
if not matched:
    logger.warning(f"Unmatched text '{text}' - suggest adding to filter_keywords.yaml")
```

### 4. Keyword Performance Analytics

```python
# Track which keywords are actually used
most_matched_keywords = {
    "owner occupier": 1523,
    "home to live in": 42,
    "primary residence": 3
}
# Suggest removing rarely-matched keywords for performance
```

## Related Documentation

- [Recursive State Explorer](RECURSIVE_STATE_EXPLORER.md) - Uses keywords for filter detection
- [Calculator Detection](CALCULATOR_DETECTION.md) - Uses calculator indicator keywords
- [Data Validation Fixes](DATA_VALIDATION_FIXES.md) - Relies on consistent keyword matching

## Code References

**Configuration:**
- `src/configs/filter_keywords.yaml` - All keyword definitions
- `src/agents/collector/filter_keywords.py` - Keyword manager class

**Usage:**
- `src/agents/collector/playwright_collector.py` - Primary consumer (~50 references to `_filter_keywords`)
- `src/models/product.py` - BIAN mapping uses keywords for normalization

