# Lender Products Collector - TODO

> Project task tracking and roadmap

Last Updated: 2025-12-21

---

## 🎯 FUNCTIONAL SCOPE

### Core Functionality
- **Automated Collection**: Collect loan product data from Australian lenders using multi-strategy extraction
- **URL Discovery**: Dynamically discover lender product pages using Google Custom Search API and fallback search engines
- **Multi-Strategy Extraction**: 5 extraction strategies (Network API, JSON-LD, Embedded State, Select Dropdowns, DOM Parsing)
- **Data Normalization**: Convert raw data to BIAN (Banking Industry Architecture Network) schema
- **Data Storage**: Store products with versioning, snapshots, and deduplication
- **REST API**: Expose collected data via FastAPI endpoints

### Search & Filter Functionality
- **Search lenders**: Find all or selected lenders via API
  - Filter by lender name/abbreviation
  - Support multiple selected lenders
  - Example: `GET /api/v1/lenders?search=ANZ` or `GET /api/v1/lenders?lenders=ANZ,CBA`

### AI-Powered Quality Assurance
- **Result Verification Agent**: AI agent at end of collection workflow to verify results
- **Confidence Scoring**: Publish confidence score (0-100) for each product/lender based on:
  - Data completeness (required fields present)
  - Data consistency (rates within expected ranges)
  - Source reliability (extraction strategy used)
  - Historical comparison (changes from previous collection)
- **Missing Information Detection**: Identify and report missing BIAN schema fields
- **Quality Assessment Reports**: Generate reports with confidence scores, missing info, and data quality metrics
- **API Access**: Expose quality metrics via `GET /api/v1/quality-assessment/{lender}`

### LVR Tier Support
- **Multiple LVR Tiers**: Support products with different rates for different LVR brackets
- **LVR-Based Rate Lookup**: Helper methods to get rates by LVR (`get_rate_by_lvr()`)
- **Tier Information**: Extract and store LVR tier data in product schema

---

## 🔧 PENDING TASKS

### Phase 1: Agent Testing (CURRENT PRIORITY)

#### Unit Tests - Verify Each Agent Works
- [ ] **Test API Agent** (`tests/unit/agents/api/test_product_api_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/api/ -v`
  - [ ] Verify REST endpoints work correctly
  - [ ] Test query parameter validation
  - [ ] Test error handling
  - [ ] Fix any failing tests

- [ ] **Test Collector Agent** (`tests/unit/agents/collector/test_playwright_collector_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/collector/ -v`
  - [ ] Test with real URL (ANZ) to verify extraction works
  - [ ] Verify all 5 extraction strategies are tested
  - [ ] Fix mocking issues in unit tests
  - [ ] Verify real-world collection works

- [ ] **Test Discovery Agents** (`tests/unit/agents/discovery/test_discovery_agents.py`)
  - [ ] Run tests: `pytest tests/unit/agents/discovery/ -v`
  - [ ] Test WebSearchDiscovery with real search
  - [ ] Test GoogleCustomSearchAPI integration
  - [ ] Verify URL extraction works
  - [ ] Test fallback mechanisms

- [ ] **Test Monitoring Agent** (`tests/unit/agents/monitoring/test_collection_monitor_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/monitoring/ -v`
  - [ ] Verify metrics tracking works
  - [ ] Test health check functionality
  - [ ] Test alert generation
  - [ ] Verify data freshness checks

- [ ] **Test Normalizer Agent** (`tests/unit/agents/normalizer/test_product_normalizer_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/normalizer/ -v`
  - [ ] Test rate parsing with various formats
  - [ ] Test feature extraction
  - [ ] Test fee normalization
  - [ ] Verify error handling

- [ ] **Test Scheduler Agent** (`tests/unit/agents/scheduler/test_collection_scheduler_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/scheduler/ -v`
  - [ ] Test scheduler lifecycle
  - [ ] Test daily/hourly collection triggers
  - [ ] Test concurrent collections
  - [ ] Verify error handling

- [ ] **Test Storage Agent** (`tests/unit/agents/storage/test_product_storage_agent.py`)
  - [ ] Run tests: `pytest tests/unit/agents/storage/ -v`
  - [ ] Test product storage and retrieval
  - [ ] Test deduplication logic
  - [ ] Test filtering (lender, rate type, rate range)
  - [ ] Test storage statistics

- [ ] **Test Workflow Agent** (`tests/unit/agents/workflows/test_collection_workflow.py`)
  - [ ] Run tests: `pytest tests/unit/agents/workflows/ -v`
  - [ ] Test LangGraph state machine
  - [ ] Test workflow orchestration
  - [ ] Test error handling and state transitions
  - [ ] Verify end-to-end collection flow

#### Integration Tests - Verify Agent Interactions
- [ ] **Test Discovery + Collector Integration** (`tests/integration/test_collector_discovery_integration.py`)
  - [ ] Run integration test: `pytest tests/integration/test_collector_discovery_integration.py -v`
  - [ ] Verify discovery finds URLs correctly
  - [ ] Verify collector extracts products from discovered URLs
  - [ ] Test with real lender (ANZ)

#### Test Coverage & Quality
- [ ] **Run all agent tests**: `pytest tests/unit/agents/ -v --cov=src/agents --cov-report=html`
- [ ] **Verify test coverage > 80%** for each agent
- [ ] **Fix any failing tests**
- [ ] **Document test results** in `tests/AGENT_TEST_ORGANIZATION.md`

---

### Phase 2: Fix Major Bank Extraction (PRIORITY)

#### 🔴 Critical - Major Banks
- [ ] **FIX: Westpac extraction**
  - Status: 0 products
  - Action: Analyze saved HTML, check for tables/embedded state
  - Files: `debug/scraper/outputs/westpac.html`
  
- [ ] **FIX: NAB extraction**
  - Status: 0 products  
  - Action: DOM parsing strategy may need refinement
  - Files: `debug/scraper/outputs/nab.html`

#### 📊 Analysis & Refinement
- [ ] **Run batch analysis** - `python debug/scraper/batch_analyze_banks.py`
  - Systematically identify extraction strategy for each bank
  - Generate extraction strategy report
  - Update `playwright_collector.py` based on findings

- [ ] **Improve extraction accuracy**
  - Current: 2/4 major banks (50% success rate) - CBA ✅, ANZ ✅
  - Target: 12/15 banks (80% success rate)
  - Focus: Westpac, NAB next (major banks)

#### 🔄 Interactive Element Navigation
- [ ] **Navigate buttons, tabs, and links to reveal hidden product data**
  - [ ] Detect interactive elements (tabs, buttons, accordions, dropdowns) on product pages
  - [ ] Implement automatic navigation strategy to click through all tabs/buttons
  - [ ] Extract products from each revealed section
  - [ ] Example: ANZ Bank "Interest Only" options only visible after clicking tab
  - [ ] Handle dynamic content loading after interactions
  - [ ] Wait for content to load after each interaction
  - [ ] Collect products from all revealed sections
  - [ ] Merge/consolidate products from multiple sections if needed
  - [ ] Update `PlaywrightCollectorAgent` to support interactive navigation
  - [ ] Add strategy detection for pages with tabs/buttons
  - [ ] Test with ANZ Bank to capture Interest Only products

---

### Phase 1.7: Functional Scope Enhancements

#### Search & Filter Functionality
- [ ] **Search to find all or selected lenders**
  - [ ] Add search endpoint to ProductAPIAgent
  - [ ] Support filtering by lender name/abbreviation
  - [ ] Support filtering by multiple lenders (selected lenders)
  - [ ] Add search query parameter validation
  - [ ] Return search results with lender metadata
  - [ ] Example: `GET /api/v1/lenders?search=ANZ` or `GET /api/v1/lenders?lenders=ANZ,CBA`

#### AI Agent for Result Verification
- [ ] **AI Agent setup at the end of collection workflow**
  - [ ] Create `ResultVerificationAgent` to analyze collected products
  - [ ] Integrate with LLM (OpenAI) for intelligent analysis
  - [ ] Verify product data completeness and quality
  - [ ] Publish confidence score for each product/lender
  - [ ] Identify and report missing information
  - [ ] Generate quality assessment report
  
- [ ] **Confidence scoring system**
  - [ ] Calculate confidence score (0-100) based on:
    - Data completeness (required fields present)
    - Data consistency (rates within expected ranges)
    - Source reliability (extraction strategy used)
    - Historical comparison (changes from previous collection)
  - [ ] Store confidence scores in product metadata
  - [ ] Expose confidence scores via API

- [ ] **Missing information detection**
  - [ ] Identify missing BIAN schema fields
  - [ ] Flag incomplete products (missing rates, fees, features)
  - [ ] Generate missing info report per lender
  - [ ] Suggest extraction strategy improvements
  - [ ] Store missing info metadata in collection results

- [ ] **Quality assessment report**
  - [ ] Generate summary report after each collection run
  - [ ] Include: confidence scores, missing info, data quality metrics
  - [ ] Save report to `data/reports/{timestamp}_quality_assessment.json`
  - [ ] Expose via API endpoint: `GET /api/v1/quality-assessment/{lender}`

---

## 📋 BACKLOG

### Phase 3: Expand Lender Coverage
- [ ] **Second-tier banks** - Macquarie, Bendigo
- [ ] **Mutual banks** - Great Southern Bank, Heritage  
- [ ] **Building societies** - Newcastle Permanent
- [ ] **Non-bank lenders** - Pepper, Liberty
- [ ] **Foreign banks** - ING, HSBC
- [ ] **Digital lenders** - Athena, Tiimely

### Phase 4: Automation & Monitoring
- [ ] **Scheduled collection**
  - Daily: Most lenders
  - Hourly: Volatile lenders (flagged in config)
  - Use APScheduler for orchestration

- [ ] **Collection monitoring dashboard**
  - Success rate by lender
  - Product count trends
  - Error tracking
  - Data freshness indicators

- [ ] **Alert system**
  - Collection failures (email/Slack)
  - Data anomalies (missing rates, duplicates)
  - Website structure changes detected
  - Stale data warnings (>24h old)

### Phase 5: Data Quality
- [ ] **Validation rules**
  - Interest rate sanity checks (e.g., 0.5% < rate < 20%)
  - Required fields present (product name, rate, lender)
  - Duplicate detection
  - Historical comparison (flag large changes)

- [ ] **Data enrichment - Additional fields**
  - Extract more BIAN fields (fees, features, eligibility)
  - Standardize product names
  - Normalize rate types (variable/fixed)
  - Merge products with same name but different LVR tiers into single product

### Phase 6: Production Deployment
- [ ] **Dockerization**
  - Create `Dockerfile` for collector service
  - Docker Compose for local development
  - Multi-stage build for optimization

- [ ] **GCP Cloud Run deployment**
  - Environment variables setup
  - Secrets management (API keys)
  - Cloud Storage for data persistence
  - Cloud Scheduler for triggers

- [ ] **CI/CD pipeline**
  - GitHub Actions for testing
  - Automated deployment to staging
  - Production deployment approval

### Phase 7: Integration
- [ ] **Connect to mortgage finder agent** (`property-finance-ai`)
  - API endpoint for querying products
  - Filter by borrower criteria
  - Rate comparison logic
  - Product recommendations

- [ ] **API enhancements**
  - Search/filter endpoints
  - Rate comparison endpoints
  - Historical data access
  - OpenAPI/Swagger docs

---

## 🐛 KNOWN ISSUES

1. **Google CAPTCHA blocking** - Mitigated with 5s delays, but may still occur
   - Solution: Always use configured URLs when possible
   - Fallback: Manual URL configuration in `lenders.json`

2. **Westpac/NAB extraction failing** - 0 products collected
   - Root cause: Strategy mismatch (their data structure differs from ANZ/CBA)
   - Fix in progress: Batch analysis to identify correct strategy

3. **Line ending warnings** (LF → CRLF) - Git warnings on Windows
   - Not critical, cosmetic only
   - Can be fixed with `.gitattributes` if needed

---

## 📈 SUCCESS METRICS

### Current Status
- **Lenders configured**: 2 (CBA, ANZ)
- **Lenders extracting successfully**: 2 (CBA ✅, ANZ ✅)
- **Success rate**: 100% (2/2 configured)
- **Total products collected**: 17 (8 from CBA, 9 from ANZ)
- **Major banks working**: 2/4 (CBA ✅, ANZ ✅, Westpac ❌, NAB ❌)

### Target Metrics (End of Phase 2)
- **Success rate**: 80%+ (12/15 lenders)
- **Major banks**: 100% (4/4)
- **Total products**: 200+ across all lenders
- **Data freshness**: <24 hours

### Target Metrics (Production Ready)
- **Success rate**: 95%+ (14/15 lenders)
- **Uptime**: 99.5%
- **Collection frequency**: Daily (most), Hourly (volatile)
- **Alert response time**: <15 minutes for critical failures

---

## 🔍 DEBUG RESOURCES

### Files to Check
- `debug/scraper/outputs/` - Saved HTML/screenshots of each bank
- `debug/discovery/outputs/` - Google search responses
- `data/current/by_lender/` - Successfully extracted products
- `data/index.json` - Collection history catalog

### Debug Scripts
- `python debug/scraper/batch_analyze_banks.py` - Systematic analysis
- `python debug/scraper/debug_page_inspector.py` - Manual inspection
- `python debug/discovery/test_google_search.py` - Test search
- `python test.py` - Quick collector test

---

**Next Action**: 
1. Test each agent to verify they work correctly! Run `pytest tests/unit/agents/ -v` 🧪
2. Fix Westpac and NAB extraction (major banks remaining)
3. Implement product merging for LVR tiers (consolidate same product with different LVR tiers into single product)
4. Add search functionality for lenders (all or selected)
5. Implement AI Agent for result verification (confidence scores and missing info detection)
