# Discovery Debug Tools

Tools to debug URL discovery issues.

## Tools

### `test_google_search.py`
Tests Google search and saves the HTML response to find why URL extraction fails.

**Usage:**
```bash
python debug/discovery/test_google_search.py
```

**Output:**
- `outputs/google_response.html` - Full Google search result HTML
- Console shows different regex patterns tried

## Purpose

Google's HTML structure changes frequently, breaking regex-based URL extraction.
This tool helps us:
1. See what Google actually returns
2. Find the current URL format in the HTML
3. Update the regex pattern accordingly
