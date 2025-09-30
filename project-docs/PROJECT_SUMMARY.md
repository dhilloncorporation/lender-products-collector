# Lender Products Collector - Project Summary

## 🎯 Project Overview

An **AI-powered loan product collection system** that automatically collects, normalizes, and stores loan product data from Australian lenders using a **LangGraph agent architecture**.

## 🏗️ Architecture

### Agent-Based System (LangGraph)
```
┌─────────────────────────────────────────────────────────┐
│              LangGraph Workflow Orchestration            │
│                  (collection_workflow.py)                │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Collector  │   │ Normalizer  │   │   Storage   │
│    Agent    │──▶│    Agent    │──▶│    Agent    │
└─────────────┘   └─────────────┘   └─────────────┘
        │                                    │
        ▼                                    ▼
┌─────────────┐                     ┌─────────────┐
│  Playwright │                     │JSON Storage │
│   Browser   │                     │   Service   │
└─────────────┘                     └─────────────┘
```

## 📁 Project Structure

```
lender-products-collector/
├── src/
│   ├── agents/
│   │   ├── collector/
│   │   │   ├── playwright_collector.py    # Web scraping agent
│   │   │   └── __init__.py
│   │   ├── scheduler/
│   │   │   ├── collection_scheduler.py    # Scheduling agent
│   │   │   └── __init__.py
│   │   ├── normalizer/
│   │   │   ├── product_normalizer.py      # Data normalization agent
│   │   │   └── __init__.py
│   │   ├── storage/
│   │   │   ├── product_storage.py         # Storage agent
│   │   │   └── __init__.py
│   │   ├── monitoring/
│   │   │   ├── collection_monitor.py      # Monitoring agent
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   ├── product_api.py             # API agent
│   │   │   └── __init__.py
│   │   └── workflows/
│   │       ├── collection_workflow.py     # ⭐ Main LangGraph workflow
│   │       └── __init__.py
│   │
│   ├── api/
│   │   ├── main.py                        # FastAPI application
│   │   └── routers/
│   │       ├── products.py                # Product endpoints
│   │       └── matches.py                 # Matching endpoints
│   │
│   ├── configs/
│   │   ├── lenders.json                   # ⚙️ Lender configuration
│   │   ├── collection_settings.json       # ⚙️ System settings
│   │   ├── lender_config.py               # Config manager
│   │   └── settings_manager.py            # Settings manager
│   │
│   ├── models/
│   │   ├── product.py                     # ⭐ BIAN schema models
│   │   ├── borrower.py
│   │   ├── property.py
│   │   └── loan_preferences.py
│   │
│   ├── schemas/
│   │   ├── bian_financial_product_schema.json  # 📋 Reference schema
│   │   ├── README.md
│   │   └── __init__.py
│   │
│   └── services/
│       ├── json_storage.py                # ⭐ JSON storage service
│       └── __init__.py
│
├── data/                                  # 📦 Data directory (git-ignored)
│   ├── current/                           # Latest collected data
│   │   ├── products.json
│   │   └── by_lender/
│   │       ├── CBA.json
│   │       ├── ANZ.json
│   │       └── ...
│   ├── snapshots/                         # Historical data
│   │   ├── raw/                          # Original HTML
│   │   └── parsed/                       # Normalized BIAN JSON
│   ├── diffs/                            # Change detection
│   ├── index.json                        # Collection catalog
│   └── README.md
│
├── tests/
│   ├── unit/
│   │   └── test_collection_workflow.py
│   ├── integration/
│   │   └── test_api_integration.py
│   ├── utils/
│   │   ├── mock_data.py
│   │   └── __init__.py
│   └── conftest.py
│
├── requirements/
│   ├── UseCases.md                        # Use cases & agent flow
│   ├── TechnicalApproach.md              # Technical stack
│   ├── DataCollectionStrategy.md         # Collection strategy
│   └── ProjectScope.md
│
├── run_collection.py                      # ⭐ Main entry point
├── test.py                                # Test scraper
├── main.py                                # FastAPI entry point
├── requirements.txt                       # Dependencies
├── CODING_STANDARDS.md                   # Code standards
└── README.md                             # Setup guide
```

## 🔑 Key Components

### 1. LangGraph Workflow (`src/agents/workflows/collection_workflow.py`)
**Purpose**: Orchestrates the entire collection process

**Flow**:
1. Initialize → Load lender list from config
2. Select Lender → Choose next lender by priority
3. Collect Products → Use Playwright to scrape website
4. Process Results → Validate and transform data
5. Check Completion → Continue or finish
6. Finalize → Save results and update index

**State Management**: Uses LangGraph's TypedDict state with SQLite checkpointer

### 2. Playwright Collector (`src/agents/collector/playwright_collector.py`)
**Purpose**: Web scraping using headless browser

**Features**:
- Async/await architecture
- CSS selector-based extraction
- BIAN schema output
- Error handling and logging
- **No LLM usage** (cost-effective)

### 3. JSON Storage Service (`src/services/json_storage.py`)
**Purpose**: Persist collected data

**Features**:
- Current products storage (`data/current/`)
- Historical snapshots (`data/snapshots/`)
- Index catalog (`data/index.json`)
- Async file operations
- Auto-creates directory structure

### 4. BIAN Schema Models (`src/models/product.py`)
**Purpose**: Standardized data structure

**Based on**: BIAN (Banking Industry Architecture Network) schema

**Models**:
- `LoanProduct` - Main product structure
- `InterestComponent` - Interest rate details
- `FeeStructure` - Fee breakdown
- `ProductFeatures` - Features (offset, redraw, etc.)
- `EligibilityCriteria` - Eligibility rules

## ⚙️ Configuration

### Lenders (`src/configs/lenders.json`)
List of all lenders with basic info:
```json
[
  {
    "lender_name": "Commonwealth Bank of Australia",
    "abbreviation": "CBA",
    "lender_type": "major_bank",
    "headquarters": "Sydney, NSW"
  }
]
```

### Collection Settings (`src/configs/collection_settings.json`)
System-wide settings:
- Collection frequency
- Retry logic
- Rate limiting
- LangChain/LangGraph configuration
- API settings
- Monitoring settings

## 🚀 How to Run

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # PowerShell

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Set API key (if using LangChain features)
$env:OPENAI_API_KEY="your-key"
```

### 2. Run Collection
```bash
# Run the LangGraph workflow
python run_collection.py
```

### 3. Check Results
```bash
# View collected data
cat data/current/by_lender/CBA.json

# View collection catalog
cat data/index.json
```

### 4. Start API Server
```bash
# Start FastAPI
uvicorn src.api.main:app --reload

# Access API
http://localhost:8000/api/v1/products/
```

## 📊 Data Flow

```
1. run_collection.py
   └─▶ CollectionWorkflow (LangGraph)
       └─▶ For each lender:
           ├─▶ PlaywrightCollectorAgent
           │   └─▶ Scrape website → BIAN models
           └─▶ JSONStorageService
               ├─▶ Save to data/current/by_lender/{LENDER}.json
               ├─▶ Save snapshot to data/snapshots/parsed/
               └─▶ Update data/index.json

2. FastAPI serves data from data/current/
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Orchestration | LangGraph | Agent workflow management |
| Web Scraping | Playwright | Headless browser automation |
| Data Models | Pydantic | Schema validation |
| Storage | JSON files | Data persistence |
| API | FastAPI | REST endpoints |
| Scheduling | APScheduler | Automated collection |
| Testing | pytest | Unit & integration tests |

## 📝 Key Design Decisions

### ✅ Why LangGraph?
- Agent-based architecture for complex workflows
- State management for collection progress
- Retry and error handling built-in
- Extensible for future AI features

### ✅ Why Playwright (not LLM extraction)?
- **Cost-effective**: No API calls per page
- **Reliable**: Direct DOM access
- **Fast**: No LLM inference latency
- **Scalable**: Can scrape 100s of pages

### ✅ Why JSON Storage (not PostgreSQL)?
- **Simple**: No database setup required
- **Portable**: Easy to backup and version
- **Transparent**: Human-readable files
- **Sufficient**: For 15 lenders, JSON is fine
- **Future-proof**: Can migrate to DB later

### ✅ Why BIAN Schema?
- **Industry standard**: Used by financial institutions
- **Comprehensive**: Covers all loan product aspects
- **Interoperable**: Easy integration with other systems
- **Future-proof**: Evolves with industry needs

## 🎯 Current Status

### ✅ Completed
- LangGraph workflow architecture
- Playwright collector agent
- JSON storage service
- BIAN schema models
- Configuration management
- FastAPI endpoints
- Test framework
- Documentation

### ⏳ TODO
- Fix Playwright selectors for each lender (currently getting empty results)
- Add lender-specific URL and selector configs
- Implement normalizer agent logic
- Implement storage agent logic
- Implement monitoring agent logic
- Add change detection with deepdiff
- Enhance API with search/filter capabilities
- Add scheduler for automated runs

## 🔧 Next Steps

1. **Debug Playwright Selectors**
   - Inspect actual HTML structure of lender websites
   - Update selectors in `playwright_collector.py`
   - Add lender-specific selector configs

2. **Test Collection Workflow**
   - Run `python run_collection.py`
   - Verify data in `data/current/`
   - Check quality of extracted data

3. **Iterate on Data Quality**
   - Compare with manual extraction (like ChatGPT output)
   - Improve selectors and parsing logic
   - Add validation rules

## 📚 Documentation

- **UseCases.md**: Agent architecture and use cases
- **TechnicalApproach.md**: Technology stack and best practices
- **DataCollectionStrategy.md**: Collection strategy options
- **CODING_STANDARDS.md**: Python development best practices
- **README.md**: Environment setup guide

## 🤝 Contributing

Follow the coding standards in `CODING_STANDARDS.md`:
- No mock data in main application files
- Use proper separation of concerns
- Test all business logic
- Document all major functions

---

**Project Type**: AI Agent System  
**Framework**: LangGraph + LangChain  
**Language**: Python 3.11+  
**License**: [To be defined]  
**Status**: Active Development
