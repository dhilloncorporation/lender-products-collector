# Functional Requirements

## 📌 Project Overview

**Project Name**: Lender Products Collector  
**Type**: AI Agent System (LangGraph + LangChain)  
**Purpose**: Automatically collect, normalize, and serve Australian loan product data

## 🎯 Project Scope

The **Lender Products Collector** is an AI agent system that:
1. **Automatically discovers** lender product pages using Google search
2. **Collects** loan product data from 15+ Australian lenders
3. **Normalizes** data into BIAN (Banking Industry Architecture Network) standard schema
4. **Stores** data with versioning and historical snapshots
5. **Exposes** data via REST API for downstream consumption

**Goal**: Comprehensive, up-to-date loan product catalogue without manual intervention.

## ✅ Functional Requirements

### FR-1: Lender Configuration
- System SHALL load lender list from `src/configs/lenders.json`
- Each lender SHALL have:
  - Name and abbreviation
  - Domain for URL discovery
  - Lender type classification
  - Priority for processing order
  - Enable/disable flag
- System SHALL support 15+ Australian lenders

### FR-2: URL Discovery
- System SHALL use Google search to discover lender pages dynamically
- System SHALL search for:
  - Interest rates pages
  - Product comparison pages
  - Fees and charges pages
- System SHALL prioritize results (interest rates first)
- System SHALL limit to top 3 URLs per lender
- System SHALL fallback to constructed URLs if search fails

### FR-3: Data Extraction
- System SHALL try multiple extraction strategies in order:
  1. Network introspection (captured JSON APIs)
  2. JSON-LD structured data
  3. Embedded JavaScript state (dataLayer, __NEXT_DATA__)
  4. Select dropdowns
  5. DOM parsing
- System SHALL stop at first successful strategy
- System SHALL extract:
  - Product name
  - Interest rate(s)
  - Comparison rate
  - Rate type (fixed/variable)
  - LVR brackets
  - Features (offset, redraw, etc.)
  - Fees
  - Eligibility criteria

### FR-4: Data Normalization
- System SHALL normalize all data to BIAN financial product schema
- System SHALL validate all products against Pydantic models
- System SHALL handle missing fields gracefully (use defaults/null)
- System SHALL preserve source URL for auditability

### FR-5: Data Storage
- System SHALL store current products at `data/current/by_lender/{LENDER}.json`
- System SHALL create historical snapshots at `data/snapshots/parsed/{LENDER}/{timestamp}.json`
- System SHALL maintain collection catalog at `data/index.json`
- System SHALL track:
  - Collection timestamp
  - Products found count
  - Success/failure status
  - Snapshot paths

### FR-6: API Exposure
- System SHALL expose REST API via FastAPI
- System SHALL provide endpoints:
  - GET `/api/v1/products/` - All products
  - GET `/api/v1/products/{lender}` - Products by lender
  - GET `/health` - System health check
- System SHALL return data in BIAN schema format

### FR-7: Workflow Orchestration
- System SHALL use LangGraph for workflow management
- System SHALL process lenders by priority order
- System SHALL handle errors gracefully (continue to next lender)
- System SHALL log all activities
- System SHALL provide progress reporting

### FR-8: Error Handling
- System SHALL retry failed pages (configurable retries)
- System SHALL timeout long-running requests
- System SHALL log all errors with context
- System SHALL continue collection even if individual lenders fail

## 🚫 Out of Scope

- ❌ Loan applications or eligibility checking
- ❌ Personalized recommendations
- ❌ Credit scoring or financial advice
- ❌ Machine learning predictions
- ❌ Front-end dashboards
- ❌ Real-time rate monitoring
- ❌ CDR (Consumer Data Right) API integration

## 🎯 Use Cases

### UC-1: Daily Product Collection
**Actor**: Scheduler Agent  
**Goal**: Collect latest product data from all enabled lenders

**Flow**:
1. System loads lender configuration
2. For each enabled lender (by priority):
   - Discovers URLs via Google search
   - Scrapes discovered pages
   - Extracts and normalizes data
   - Saves to storage
3. Updates collection index
4. Reports results

**Success**: All enabled lenders processed, data saved

### UC-2: API Data Query
**Actor**: External System (property-finance-ai)  
**Goal**: Retrieve loan product data

**Flow**:
1. Client sends GET request to `/api/v1/products/CBA`
2. System reads from `data/current/by_lender/CBA.json`
3. Returns products in BIAN schema format

**Success**: Valid JSON response with products

### UC-3: Historical Analysis
**Actor**: Data Analyst  
**Goal**: Compare product changes over time

**Flow**:
1. Load snapshots from `data/snapshots/parsed/{LENDER}/`
2. Compare across timestamps
3. Identify rate changes, new products, discontinued products

**Success**: Change history available

### UC-4: Add New Lender
**Actor**: System Administrator  
**Goal**: Start collecting data from a new lender

**Flow**:
1. Add lender to `src/configs/lenders.json` with:
   - Name, abbreviation, domain
   - Set `enabled: true`
2. Run collection workflow
3. System discovers URLs automatically
4. System tries all extraction strategies
5. Data collected (if strategies match lender's structure)

**Success**: New lender data in `data/current/by_lender/`

## 📊 Success Metrics

### Coverage
- **Target**: 100% of major banks (CBA, Westpac, NAB, ANZ)
- **Current**: 25% (ANZ only)

### Data Quality
- **Required Fields**: product_id, name, rate
- **Completeness**: >80% of available fields populated
- **Accuracy**: Matches lender website

### Performance
- **Collection Time**: <5 minutes for all enabled lenders
- **API Response**: <500ms for product queries
- **Storage Size**: <100MB for 15 lenders with 6 months history

### Reliability
- **Uptime**: 99% (handles lender website changes gracefully)
- **Error Recovery**: Continues collection even if individual lenders fail

## 🔄 Future Enhancements

### Phase 2:
- Change detection with deepdiff
- Alert notifications (Slack/Email)
- Rate change monitoring

### Phase 3:
- PDF extraction for rate cards
- Automated scheduler (APScheduler/cron)
- API authentication

### Phase 4:
- GraphQL API
- Real-time rate monitoring
- Machine learning for prediction
