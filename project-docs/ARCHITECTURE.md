# System Architecture - Lender Products Collector

## 🎯 Complete End-to-End Flow

```
1. User runs: python run_collection.py
   │
2. LangGraph Workflow Initializes
   ├─ Load lenders.json (15 lenders with domains)
   ├─ Filter by enabled=true (4 lenders: CBA, Westpac, NAB, ANZ)
   └─ Sort by priority
   │
3. For Each Lender (Loop):
   │
   ├─ SELECT LENDER (by priority)
   │  └─ Current: "CBA"
   │
   ├─ DISCOVER URLS (Google Search) 🆕
   │  ├─ Search: "site:commbank.com.au home loan interest rates"
   │  ├─ Search: "site:commbank.com.au home loan products"
   │  ├─ Search: "site:commbank.com.au compare home loans"
   │  └─ Returns: Top 3 URLs
   │
   ├─ COLLECT PRODUCTS (Multi-Strategy) 🆕
   │  For each discovered URL:
   │  │
   │  ├─ Strategy 0: Network Introspection
   │  │  └─ Capture JSON API calls → Parse responses
   │  │
   │  ├─ Strategy 1: JSON-LD
   │  │  └─ Find <script type="application/ld+json"> → Parse
   │  │
   │  ├─ Strategy 2: Embedded State
   │  │  ├─ Check window.dataLayer (Google Tag Manager)
   │  │  ├─ Check window.__NEXT_DATA__ (Next.js)
   │  │  └─ Check window.__NUXT__ (Nuxt)
   │  │
   │  ├─ Strategy 3: Select Dropdowns ✅ (ANZ WORKS!)
   │  │  └─ Find <select id="*Interest*"> → Parse options
   │  │
   │  └─ Strategy 4: DOM Parsing (Fallback)
   │     └─ CSS selectors for tables/cards/divs
   │
   ├─ PROCESS RESULTS (Validate & Save)
   │  ├─ Validate BIAN schema
   │  ├─ Save to data/current/by_lender/{LENDER}.json
   │  ├─ Save snapshot to data/snapshots/parsed/
   │  └─ Update data/index.json
   │
   ├─ CHECK COMPLETION
   │  └─ More lenders? → Loop back to SELECT LENDER
   │     All done? → FINALIZE
   │
4. FINALIZE
   ├─ Print summary
   └─ END
```

## 📁 Data Sources & Configuration

### Input: `src/configs/lenders.json`
```json
{
  "lender_name": "Commonwealth Bank of Australia",
  "abbreviation": "CBA",
  "domain": "commbank.com.au",    // 🆕 Used for Google search
  "website": "https://...",
  "jurisdiction": "AU",            // BIAN standard
  "enabled": true,                 // Control which lenders to process
  "priority": 1                    // Processing order
}
```

### Output: `data/current/by_lender/ANZ.json`
```json
[
  {
    "product_id": "ANZ-Standard-Variable",
    "name": "ANZ Standard Variable",
    "interest_components": [
      {"comparison_rate_pct_au": 6.49}
    ],
    "lender": "ANZ",
    "source_url": "https://...",
    "collected_at": "2025-09-30T14:02:52"
  }
]
```

## 🔄 Agent Architecture (LangGraph)

### Agents:

1. **Discovery Agent** (`GoogleSearchDiscovery`)
   - Finds lender product pages using Google search
   - No hardcoded URLs
   - Self-healing when banks change URLs

2. **Collector Agent** (`PlaywrightCollectorAgent`)
   - Multi-strategy extraction (5 strategies)
   - Network capture for API discovery
   - Outputs BIAN schema

3. **Storage Agent** (`JSONStorageService`)
   - Saves current products
   - Creates historical snapshots
   - Maintains index catalog

4. **Workflow Orchestrator** (`CollectionWorkflow`)
   - LangGraph state machine
   - Coordinates all agents
   - Handles errors & retries

## 🧩 Key Components

### LangGraph Workflow Nodes:
```
initialize → select_lender → discover_urls → collect_products → 
process_results → check_completion → [finalize | loop back]
```

### Extraction Strategies (Priority Order):
```
0. Network Introspection (captured APIs)
1. JSON-LD (structured data)
2. Embedded State (dataLayer, __NEXT_DATA__)
3. Select Dropdowns (ANZ-style) ✅ WORKING
4. DOM Parsing (fallback)
```

### Data Storage:
```
data/
├── current/
│   └── by_lender/
│       └── ANZ.json (8 products) ✅
├── snapshots/
│   └── parsed/
│       └── ANZ/
│           └── 2025-09-30-14-02-52.json
└── index.json (collection catalog)
```

## 📊 Current Status

### Working:
- ✅ LangGraph workflow orchestration
- ✅ Google Search URL discovery  
- ✅ 5 extraction strategies implemented
- ✅ ANZ: 8 products collected via select dropdown
- ✅ JSON storage with snapshots
- ✅ BIAN schema compliance

### Not Working Yet:
- ⚠️ CBA: 0 products (Google search finding no URLs, need to debug)
- ⚠️ Westpac: 0 products
- ⚠️ NAB: 0 products
- ⚠️ Other banks: disabled

### Issues to Fix:
1. **Google Search not extracting URLs** - regex pattern needs adjustment
2. **CBA dataLayer** - needs specific parsing logic
3. **NAB JSON-LD** - needs to check if product data exists
4. **Westpac** - needs custom DOM parsing

## 🎯 Success Criteria

**Current**: 1/4 banks (25%)
**Goal**: 4/4 major banks (100%)

## 🛠️ Debug Tools

### Check what's on a page:
```bash
python debug/scraper/debug_page_inspector.py
```

### Batch analyze all banks:
```bash
python debug/scraper/batch_analyze_banks.py
```

### Test extraction for specific bank:
```bash
python debug/scraper/extract_anz_products.py
```

## 📝 Next Priority

1. **Fix Google Search URL extraction** - the regex is missing URLs
2. **Test with simpler search** - try without `site:` restriction first
3. **Implement per-bank extraction logic** based on batch analysis
