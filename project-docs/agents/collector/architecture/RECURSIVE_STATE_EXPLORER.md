# Recursive State Explorer ("Full Matrix Explorer")

## Overview

The **Recursive State Explorer** is a hierarchical UI enumeration system that systematically discovers and interacts with nested filter groups to capture all possible pricing states for financial products.

## Problem Statement

### Before: Flat Enumeration
- Collected only the first visible state
- Missed filters that appeared conditionally (e.g., "Interest Only" only visible after clicking "Loan Type")
- Created duplicate products instead of merging states
- No detection of explicitly unavailable states

### After: Recursive Exploration
- **Hierarchical traversal**: Rate Type → Loan Type → Repayment Type
- **Dynamic re-scanning**: Discovers new filters after each interaction
- **Stable product identity**: Merges all states into single product objects
- **Explicit unavailability**: Records when combinations exist but have no pricing

## Architecture

### 1. Core Method: `_explore_state_recursively()`

```python
async def _explore_state_recursively(
    self,
    page: Page,
    current_path: List[str],
    all_filter_groups: List[Dict[str, Any]],
    depth: int = 0
) -> List[LoanProduct]
```

**Recursive Logic:**
1. Extract data from current state
2. Identify remaining filter groups at this level
3. For each option in each filter group:
   - Apply the filter (click/select)
   - Wait for UI update
   - Recurse to explore deeper states
   - Reset to previous state
4. Return merged products from all branches

### 2. Dynamic Filter Discovery

After clicking any "Tab" or "Dropdown", the system re-runs `_identify_filter_groups()` to discover:
- Nested filters that only appear in specific contexts
- Conditional UI elements (e.g., "Interest Only" toggle)
- State-dependent filter options

### 3. State Path Tracking

Each recursion maintains a `current_path` list:
```python
current_path = ["Variable", "Owner Occupier", "Principal & Interest"]
```

This path is used to:
- Generate deterministic `state_id` values
- Avoid infinite loops
- Provide audit trails in provenance data

### 4. Explicit Unavailable States

When a state combination is clicked but no pricing table appears, the system:
1. Detects "Not Available" messages or empty content
2. Creates a `pricing_state` entry with:
   - `pricing: null`
   - `capture_status: "not_available"`
   - `reason: "UI state present but pricing not displayed"`

## Implementation Details

### Entry Point: `_extract_from_ui_enumeration()`

```python
# Step 1: Calculator detection (skip if found)
if await self._is_calculator_widget(page, enumeration_groups):
    return []

# Step 2: Prepare user flow
filled_values = await self._fill_numeric_inputs(page)
show_more_count = await self._click_show_more_buttons(page)

# Step 3: Start recursive exploration
all_products = await self._explore_state_recursively(
    page=page,
    current_path=[],
    all_filter_groups=enumeration_groups,
    depth=0
)
```

### Filter Type Handling

The explorer handles multiple UI patterns:
- **Tabs**: `await tab_elem.click()`
- **Dropdowns**: `await page.select_option(selector, value)`
- **Toggles**: `await toggle_elem.click()`
- **Radio Buttons**: `await label.click()` (clicks associated `<label>`)

### State Resetting

After exploring each branch, the system:
1. Looks for a "Reset" or "Clear All" button
2. If found: clicks it
3. If not found: reloads the page

## Key Benefits

### 1. Completeness
Discovers **all** pricing states, not just the default view:
- Owner Occupied + P&I
- Owner Occupied + Interest Only
- Investment + P&I  
- Investment + Interest Only

### 2. Accuracy
Each state is captured independently, preventing:
- Rate mixing/contamination
- LVR tier overlaps from merged states
- Incorrect product-state associations

### 3. Auditability
Every pricing state includes:
- Full filter path taken to reach it
- Extraction method and strategy
- Confidence score based on completeness
- Timestamp and source URL

### 4. Product Consolidation
All states for "1 Year Fixed" are merged into a single product with multiple `pricing_states`, instead of creating 4 separate products.

## Example: ANZ Home Loans

### Discovered Filter Hierarchy
```
Level 1: Rate Type
  ├─ Variable
  └─ Fixed
      └─ [Dynamically shows] Fixed Term options (1yr, 2yr, 3yr...)

Level 2: Loan Type (appears after Level 1)
  ├─ Home to live in (Owner Occupied)
  └─ Investment

Level 3: Repayment Type (appears after Level 2)
  ├─ Principal & Interest
  └─ Interest Only
```

### Exploration Path for 1 State
```
Click "Variable" 
  → Wait 2500ms 
  → Re-scan for filters
  → Click "Home to live in"
    → Wait 2500ms
    → Re-scan for filters
    → Click "Principal & Interest"
      → Wait 2500ms
      → Extract rate table
      → Generate state_id: "OO_PI_VAR"
```

### Result
- **8 states** for Variable rates (4 combinations)
- **~24 states** for Fixed rates (4 combinations × ~6 terms)
- All merged into stable product objects by name
- Explicit `null` entries for any unavailable combinations

## Performance Considerations

### Calculator Detection
Before starting exploration, the system checks if the page is a calculator widget (not a product listing). If detected, recursive exploration is skipped to avoid wasteful processing.

See: [CALCULATOR_DETECTION.md](CALCULATOR_DETECTION.md)

### Wait Times
- Standard interaction wait: **2500ms** (increased from 1500ms)
- Critical filters (e.g., `repayment_type`): May use longer waits
- Ensures dynamic content fully loads before extraction

### Depth Limits
- Maximum recursion depth: **5 levels**
- Prevents infinite loops from circular UI patterns
- Can be configured via settings

## Related Documentation

- [Closed-World Matrix](CLOSED_WORLD_MATRIX.md) - How unavailable states are materialized
- [Calculator Detection](CALCULATOR_DETECTION.md) - Optimization for calculator pages
- [Data Validation Fixes](DATA_VALIDATION_FIXES.md) - Quality improvements enabled by this system

## Code References

**Main Implementation:**
- `src/agents/collector/playwright_collector.py::_explore_state_recursively()`
- `src/agents/collector/playwright_collector.py::_extract_from_ui_enumeration()`
- `src/agents/collector/playwright_collector.py::_identify_filter_groups()`

**Models:**
- `src/models/product.py::PricingState`
- `src/models/product.py::LoanProduct.to_state_explicit_json()`

