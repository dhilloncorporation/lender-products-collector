# Debug Tools

Organized debug tools for different components of the system.

## Structure

```
debug/
├── scraper/              # Web scraping debug tools
│   ├── debug_page_inspector.py
│   ├── outputs/         # HTML, screenshots (git-ignored)
│   └── README.md
│
├── workflow/            # LangGraph workflow debug tools (future)
│   └── outputs/
│
├── storage/             # JSON storage debug tools (future)
│   └── outputs/
│
└── README.md           # This file
```

## Usage

Each debug category has its own folder with:
- Debug scripts
- `outputs/` subfolder for generated files
- `README.md` with usage instructions

## Current Tools

### Scraper Debugging
- **Location**: `debug/scraper/`
- **Purpose**: Inspect lender pages, find correct CSS selectors
- **Run**: `python debug/scraper/debug_page_inspector.py`

## Adding New Debug Tools

1. Create a folder for the debug category (e.g., `debug/workflow/`)
2. Add your debug script
3. Create `outputs/` subfolder
4. Add `README.md` with usage instructions
5. Update this main README
