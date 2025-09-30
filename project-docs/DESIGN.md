# Detailed Design

## Module-by-Module Design

### 1. Workflow Orchestration (`src/agents/workflows/`)

#### CollectionWorkflow (LangGraph State Machine)

**Purpose**: Orchestrate the entire collection process using LangGraph

**State Schema**:
```python
class CollectionState(TypedDict):
    lenders: List[Dict]           # All lenders to process
    current_lender: str           # Current lender abbreviation
    current_lender_urls: List[str]  # URLs discovered for current lender
    collection_results: Dict      # Results per lender
    errors: List[str]             # Error log
    completed_lenders: List[str]  # Completed lenders
    total_lenders: int            # Total count
    success_count: int            # Success count
    failure_count: int            # Failure count
```

**Nodes**:
1. **initialize**: Load lenders from config
2. **select_lender**: Pick next lender by priority
3. **discover_urls**: Google search for pages
4. **collect_products**: Playwright scraping
5. **process_results**: Validate and save
6. **check_completion**: Decision point
7. **finalize**: Summary report

**Flow**:
```
initialize → [loop: select → discover → collect → process → check] → finalize
```

---

### 2. URL Discovery (`src/agents/discovery/`)

#### GoogleSearchDiscovery

**Purpose**: Dynamically find lender product pages using Google search

**Search Templates**:
```python
{
    "interest_rates": 'site:{domain} intitle:"home loan" interest rates',
    "products": 'site:{domain} intitle:"home loans" products',
    "comparison": 'site:{domain} intitle:"home loans" compare',
    "fees": 'site:{domain} "home loan" fees OR charges'
}
```

**Method**: `discover_lender_pages(lender_name, lender_domain)`

**Returns**:
```json
{
  "interest_rates": ["url1", "url2", "url3"],
  "products": ["url4", "url5"],
  "fees": ["url6"],
  "comparison": ["url7"]
}
```

**Parameters**:
- User-Agent: Chrome 124
- Locale: en-AU, region=AU
- Timeout: 20s with retry

**Known Issues**:
- Google HTML structure changes frequently
- Regex may need updates
- Consider switching to Google Custom Search API

---

### 3. Data Collection (`src/agents/collector/`)

#### PlaywrightCollectorAgent

**Purpose**: Extract loan product data using multi-strategy approach

**Initialization**:
```python
collector = PlaywrightCollectorAgent(headless=True, timeout=30000)
```

**Main Method**: `collect_from_url(url, lender_name, selectors=None)`

**Multi-Strategy Extraction**:

**Strategy 0: Network Introspection**
- Captures all JSON API responses during page load
- Recursively searches JSON for product arrays
- **Best for**: React/Next.js sites with XHR/fetch calls

**Strategy 1: JSON-LD**
- Finds `<script type="application/ld+json">`
- Parses schema.org Product/FinancialProduct
- **Best for**: SEO-optimized sites

**Strategy 2: Embedded State**
- Executes JavaScript to access:
  - `window.dataLayer` (Google Tag Manager)
  - `window.__NEXT_DATA__` (Next.js)
  - `window.__NUXT__` (Nuxt)
- **Best for**: Modern web apps

**Strategy 3: Select Dropdowns**  
- Finds `<select id="*Interest*">` elements
- Parses option text: `"{rate}% p.a {name} {LVR}"`
- **Best for**: ANZ-style calculator dropdowns
- ✅ **WORKING**: ANZ - 8 products

**Strategy 4: DOM Parsing**
- Finds headings matching loan product patterns
- Extracts rates from nearby text with regex
- **Best for**: Simple HTML pages

**Decision Logic**: Try strategies 0→4, return on first success

---

### 4. Data Storage (`src/services/`)

#### JSONStorageService

**Purpose**: Persist collected data in JSON format

**Directory Structure**:
```
data/
├── current/
│   ├── products.json              # All products
│   └── by_lender/{LENDER}.json   # Per-lender files
├── snapshots/
│   ├── raw/{LENDER}/{timestamp}/  # Original HTML
│   └── parsed/{LENDER}/{timestamp}.json  # BIAN JSON
├── diffs/{LENDER}/{date}.json     # Change detection (future)
└── index.json                     # Collection catalog
```

**Methods**:
- `save_current_products(products, lender)` - Save latest data
- `save_snapshot(products, lender, raw_html)` - Historical backup
- `update_index(lender, status, count, path)` - Update catalog
- `load_current_products(lender)` - Read saved data

**File Format**: JSON with BIAN schema structure

---

### 5. Data Models (`src/models/`)

#### BIAN Schema Models

**Reference**: `src/schemas/bian_financial_product_schema.json`

**Models** (from schema):
```python
LoanProduct           # Main product structure
InterestComponent     # Interest rate details
FeeStructure          # Fee breakdown
ProductFeatures       # Features (offset, redraw, etc.)
EligibilityCriteria   # Eligibility rules
```

**Validation**: All fields validated by Pydantic

**Backward Compatibility**:
```python
# Properties for legacy code
@property
def rate_percent(self) -> Decimal:
    return self.interest_components[0].comparison_rate_pct_au
```

---

### 6. Configuration (`src/configs/`)

#### Lender Configuration (`lenders.json`)

**Structure**:
```json
{
  "lender_name": "Commonwealth Bank of Australia",
  "abbreviation": "CBA",
  "domain": "commbank.com.au",
  "website": "https://www.commbank.com.au",
  "lender_type": "major_bank",
  "jurisdiction": "AU",
  "enabled": true,
  "priority": 1
}
```

**Priority Levels**:
- 1: Major banks (CBA, Westpac, NAB, ANZ)
- 2: Second-tier banks
- 3: Mutual banks
- 4: Non-bank lenders
- 5: Digital lenders

#### Collection Settings (`collection_settings.json`)

**Categories**:
- Collection: Frequency, retries, timeouts
- Scheduler: Cron settings
- Storage: Paths, backup settings
- Monitoring: Logging, alerts
- API: Host, port, CORS
- LangChain: Model, temperature
- LangGraph: State management

---

### 7. API Layer (`src/api/`)

#### FastAPI Application

**Endpoints**:
```
GET  /                          # Root - health check
GET  /health                    # Detailed health status
GET  /api/v1/products/         # All products
GET  /api/v1/products/{lender} # Products by lender
```

**Response Format**: BIAN schema JSON

**Features**:
- CORS middleware
- Error handling
- Rate limiting (future)
- Authentication (future)

---

## 🔄 Data Flow

```
1. run_collection.py
   └─> CollectionWorkflow (LangGraph)
       └─> For each lender:
           ├─> GoogleSearchDiscovery
           │   └─> Returns top 3 URLs
           ├─> PlaywrightCollectorAgent
           │   ├─> Browse each URL
           │   ├─> Try all 5 extraction strategies
           │   └─> Return products
           └─> JSONStorageService
               ├─> Save current products
               ├─> Save snapshot
               └─> Update index

2. FastAPI serves from data/current/
```

---

## 🧪 Testing Strategy

### Unit Tests (`tests/unit/`)
- Test each extraction strategy independently
- Mock Playwright responses
- Validate BIAN schema

### Integration Tests (`tests/integration/`)
- Test API endpoints
- Test workflow orchestration
- Test storage operations

### Debug Tools (`debug/`)
- `debug/scraper/` - Page inspection, batch analysis
- `debug/discovery/` - Google search testing

---

## 🎯 Design Decisions

### Why LangGraph?
- State management for complex workflows
- Easy to visualize and debug
- Retry and error handling built-in
- Scales to more complex agent interactions

### Why Multiple Extraction Strategies?
- Each bank uses different technology
- No single approach works for all
- Cascading ensures maximum coverage
- No custom code per bank

### Why Google Search Discovery?
- URLs change over time
- No maintenance of static URL lists
- Finds best pages automatically
- Self-healing system

### Why JSON Storage (not Database)?
- Simple and portable
- Human-readable for debugging
- Sufficient for 15 lenders
- Easy backup and version control
- Can migrate to DB later if needed

### Why BIAN Schema?
- Industry standard
- Comprehensive coverage
- Interoperability with other systems
- Future-proof
