# Scraper Debug Tools

Tools to debug web scraping issues and inspect lender pages.

## Tools

### `debug_page_inspector.py`
Inspects lender pages to understand their structure.

**Usage:**
```bash
cd C:\SourceCode\AIProject-WS\lender-products-collector
python debug/scraper/debug_page_inspector.py
```

**Output:**
- `outputs/*.html` - Full page HTML
- `outputs/*.png` - Screenshots
- Console output showing element counts

## Outputs

All debug outputs are saved to `debug/scraper/outputs/` (git-ignored).
