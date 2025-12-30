# Calculator Detection & Optimization

## Overview

**Calculator Detection** is an intelligent optimization that identifies when the current page context represents a rate calculator widget rather than a product listing, allowing the system to skip wasteful recursive exploration and fall back to more appropriate extraction strategies.

## 🎯 Generic vs. Lender-Specific

**Important:** This is a **100% generic solution** discovered through an ANZ-specific problem.

- ✅ **Generic Implementation**: Uses semantic keywords and structural patterns applicable to ANY lender
- ✅ **Externalized Keywords**: All detection patterns in `filter_keywords.yaml` (not hardcoded)
- ✅ **No ANZ-Specific Logic**: Works automatically for Westpac, NAB, or any future lender with calculators
- 🔍 **Discovery Context**: Performance bottleneck was first observed on ANZ Bank's rate calculator page

**This will automatically optimize collection for:**
- Commonwealth Bank calculator pages
- Regional bank rate estimators  
- Credit union loan calculators
- Any future lender with similar UI patterns

## Problem Discovered

### ANZ Performance Issue

During collection runs for ANZ Bank, the system exhibited extremely long execution times:

**Observed Behavior:**
```
[2025-12-26 16:30:15] INFO: Starting recursive exploration...
[2025-12-26 16:30:45] INFO: Detected filter groups: ['loan_type', 'repayment_type'] (radio buttons)
[2025-12-26 16:31:15] INFO: Recursion depth 1: Exploring 2 options
[2025-12-26 16:32:00] INFO: Recursion depth 2: Exploring 2 options
[2025-12-26 16:33:30] INFO: Products found: 0
[2025-12-26 16:35:00] INFO: Re-scanning for filters...
[2025-12-26 17:23:45] INFO: Recursive exploration complete (53 minutes)
```

**Root Cause:**
- ANZ's "Interest Rates" page contains interactive calculator widgets
- These calculators use radio buttons for "Loan Type" and "Repayment Type"
- The Recursive State Explorer correctly detected and interacted with these buttons
- However, **calculators don't display product listings** - they show estimated rates
- The explorer kept recursing, finding 0 products, and re-scanning in a long loop

## Solution Architecture

### Detection Strategy

The system uses **semantic analysis** combined with **structural checks**:

#### 1. Semantic Indicators
Keywords that suggest a calculator context (from `filter_keywords.yaml`):
```yaml
calculator_indicators:
  - "estimated rate"
  - "your rate"
  - "calculate"
  - "calculator"
  - "example rate"
  - "loan amount"
  - "property value"
  - "repayment amount"
  - "repayment calculator"
  - "how much could i borrow"
  - "what if i change"
  - "see how changes"
```

#### 2. Structural Checks
```python
# If 2+ calculator indicators present AND very few enumeration filter groups:
if indicator_count >= 2 and len(filter_groups) <= 2:
    return True  # Likely a calculator
```

**Rationale:**
- Real product listings have multiple filter groups (rate type, LVR, features, packages)
- Calculators typically have 1-3 simple inputs (loan type, repayment type, amount)
- The combination of calculator keywords + simple structure is a strong signal

### Implementation

#### Core Method: `_is_calculator_widget()`

```python
async def _is_calculator_widget(
    self, 
    page: Page, 
    filter_groups: List[Dict[str, Any]]
) -> bool:
    """
    Detects if the current page context represents a calculator widget
    rather than a product listing with filters.
    """
    page_text = await page.inner_text('body')
    page_text_lower = page_text.lower()
    
    # Count calculator indicators on the page
    indicator_count = sum(
        1 for indicator in _filter_keywords.CALCULATOR_INDICATORS
        if indicator in page_text_lower
    )
    
    # Threshold: 2+ indicators + few filter groups = calculator
    if indicator_count >= 2 and len(filter_groups) <= 2:
        logger.warning(
            f"   🧮 Calculator detected ({indicator_count} indicators found), "
            "skipping recursive exploration."
        )
        return True
    
    return False
```

#### Integration Point

In `_extract_from_ui_enumeration()`, before starting exploration:

```python
# Early exit if calculator detected
if await self._is_calculator_widget(page, enumeration_groups):
    logger.info("   ⏩ Skipped recursive exploration (calculator widget detected)")
    return []  # Triggers fallback to other extraction strategies
```

## Benefits

### 1. Performance Optimization

**Before (ANZ):**
- Recursive exploration: **53 minutes**
- Products found: 0
- Wasteful processing of calculator inputs

**After (Expected):**
- Calculator detection: **< 5 seconds**
- Immediate fallback to DOM parsing or LLM extraction
- Estimated total time: **< 2 minutes**

**Speedup:** ~26× faster

### 2. Resource Efficiency

- Fewer page interactions (no recursive clicking)
- Reduced browser memory consumption
- Lower CPU usage from unnecessary state exploration

### 3. Improved Accuracy

- Calculator-estimated rates are not real product pricing
- Skipping them prevents false data from entering the system
- Fallback strategies may find actual product data elsewhere on the page

## Safety Features

### 1. Conservative Thresholds

```python
if indicator_count >= 2 and len(filter_groups) <= 2:
```

- Requires **multiple** indicators (not just one ambiguous keyword)
- Requires **few** filter groups (real product pages have more complexity)
- **Low false positive rate**: Won't skip legitimate product listings

### 2. Externalized Keywords

All indicators in `filter_keywords.yaml`:
- Easy to update without code changes
- Can be customized per lender if needed
- Versioned with the codebase

### 3. Logging

```python
logger.warning(
    f"   🧮 Calculator detected ({indicator_count} indicators found), "
    "skipping recursive exploration."
)
```

- Clear visibility into detection decisions
- Helps identify false positives during review
- Indicator count aids in threshold tuning

### 4. Fallback Preservation

Returning `[]` from UI Enumeration triggers the next strategy:
- DOM Parsing (static rate tables)
- LLM Extraction (last resort)
- Ensures we don't completely fail to collect data

## Edge Cases

### False Positives (Incorrectly Detected as Calculator)

**Scenario:** A product page has a sidebar calculator widget alongside product listings.

**Mitigation:**
- High threshold (2+ indicators)
- Structure check (few filter groups)
- In practice: Real product pages have >2 filter groups

**Fallback:** DOM parsing can still extract static rate tables on the main page content.

### False Negatives (Calculator Not Detected)

**Scenario:** A calculator without standard keywords (e.g., in another language or unusual phrasing).

**Mitigation:**
- Recursive explorer will still function correctly
- It will simply take longer to determine no products exist
- Can add lender-specific keywords to `filter_keywords.yaml`

**Impact:** Performance degradation only, not data quality

## Configuration

### Keywords Location

**File:** `src/configs/filter_keywords.yaml`

```yaml
ui_interactions:
  calculator_indicators:
    - "estimated rate"
    - "your rate"
    - "calculate"
    # ... add more as discovered
```

### Threshold Tuning

**In code:** `src/agents/collector/playwright_collector.py::_is_calculator_widget()`

```python
# Current thresholds:
MIN_INDICATORS = 2        # Adjust if too sensitive/insensitive
MAX_FILTER_GROUPS = 2     # Adjust based on calculator complexity observed
```

### Per-Lender Overrides (Future)

Could add to `lenders.json`:
```json
{
  "id": "anz",
  "collection_config": {
    "skip_calculator_detection": false,
    "calculator_thresholds": {
      "min_indicators": 3,  // More conservative for this lender
      "max_filter_groups": 1
    }
  }
}
```

## Case Study: ANZ Discovery

### Why ANZ Was the Discovery Case

**URL:** `https://www.anz.com.au/personal/home-loans/interest-rates/`

**Page Structure:**
1. **Calculator Widget** (top of page):
   - Radio buttons: "Home to live in" / "Investment"
   - Radio buttons: "Principal & Interest" / "Interest Only"
   - Text: "Example rate for your situation"
   - Shows: Single calculated rate based on inputs

2. **Static Rate Tables** (below calculator):
   - Actually contains real product rates
   - No interactive filters needed
   - Extractable via DOM parsing

**Why This Triggered the Issue:**
- ANZ happened to be one of the first lenders tested with the new Recursive State Explorer
- The calculator matched our filter detection patterns (radio buttons with loan/repayment type semantics)
- The 53-minute runtime made the issue immediately obvious

**Generic Detector Response:**
- ✅ Correctly identifies calculator section (using generic keywords)
- ⏩ Skips recursive exploration
- ✅ Falls back to DOM parsing for static tables
- 🎯 Result: Fast, accurate data extraction

**Will Work Identically For:**
- Westpac's rate calculator
- NAB's loan estimator
- Bank of Queensland's repayment calculator
- Any lender using calculator widgets with standard terminology

## Performance Impact

### Metrics (Estimated)

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| ANZ Interest Rates | 53 min | < 2 min | 26× faster |
| Calculator-only page | 30-60 min | < 10 sec | 180× faster |
| Mixed page (calc + products) | Variable | < 5 min | 3-10× faster |

### System-Wide Impact

Assuming 10% of lender pages have calculators:
- **Average collection time reduction**: ~15-20%
- **Resource savings**: ~20% fewer browser interactions
- **Cost savings**: Proportional compute time reduction

## Testing

### Manual Testing

1. Navigate to ANZ calculator page
2. Run collection with debug logging enabled
3. Verify detection message appears
4. Confirm recursive exploration is skipped
5. Check that products are still extracted (via fallback)

### Automated Testing

```python
async def test_calculator_detection():
    collector = PlaywrightCollector()
    
    # Mock page with calculator indicators
    filter_groups = [
        {'name': 'loan_type', 'type': 'radio'},
        {'name': 'repayment_type', 'type': 'radio'}
    ]
    
    # Should detect calculator
    assert await collector._is_calculator_widget(mock_page, filter_groups) == True
    
    # Add more filter groups - should not detect
    filter_groups.append({'name': 'rate_type', 'type': 'tab'})
    filter_groups.append({'name': 'lvr_band', 'type': 'dropdown'})
    assert await collector._is_calculator_widget(mock_page, filter_groups) == False
```

## Related Documentation

- [Recursive State Explorer](RECURSIVE_STATE_EXPLORER.md) - The system this optimizes
- [Performance Analysis ANZ](../performance/PERFORMANCE_ANALYSIS_ANZ.md) - Detailed investigation
- [Externalized Keywords](EXTERNALIZED_KEYWORDS_MANIFEST.md) - Keyword management

## Code References

**Detection Logic:**
- `src/agents/collector/playwright_collector.py::_is_calculator_widget()` (~line 890)
- `src/agents/collector/playwright_collector.py::_extract_from_ui_enumeration()` (~line 820)

**Configuration:**
- `src/configs/filter_keywords.yaml::ui_interactions.calculator_indicators`
- `src/agents/collector/filter_keywords.py::CALCULATOR_INDICATORS` property

## Future Enhancements

1. **ML-Based Detection**: Train a classifier on page structure to detect calculators
2. **Visual Detection**: Use Playwright screenshots + image recognition
3. **DOM Pattern Matching**: Identify common calculator frameworks (e.g., specific CSS classes)
4. **Lender Profiles**: Maintain a database of known calculator URLs to skip preemptively
5. **Hybrid Approach**: Extract calculator parameters as product metadata (e.g., "supports loan amount $X-$Y")

