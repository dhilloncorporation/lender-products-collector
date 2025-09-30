# Lender Products Collector

> AI-powered loan product data collection system using LangGraph and Playwright

## 🎯 Overview

Automatically collects, normalizes, and serves Australian loan product data from 15+ lenders using a multi-strategy AI agent architecture.

**Key Features**:
- ✅ **Dynamic URL Discovery** - Google search finds pages automatically
- ✅ **Multi-Strategy Extraction** - 5 different extraction methods
- ✅ **BIAN Schema Compliance** - Industry-standard data format
- ✅ **LangGraph Orchestration** - AI agent workflow management
- ✅ **Self-Healing** - Adapts to website changes
- ✅ **Full Automation** - No manual data entry

**Current Status**: ✅ ANZ working (8 products) | ⚠️ Other banks in progress

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Git

### Installation

```bash
# Clone repository
cd C:\SourceCode\AIProject-WS\lender-products-collector

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # PowerShell
# or
source .venv/Scripts/activate  # Git Bash

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Configuration

```bash
# Optional: Set OpenAI API key (for future LangChain features)
$env:OPENAI_API_KEY="your-key"  # PowerShell
export OPENAI_API_KEY="your-key"  # Git Bash
```

### Run Collection

```bash
# Run the complete collection workflow
python run_collection.py
```

### Check Results

```bash
# View collected products
cat data/current/by_lender/ANZ.json

# View collection catalog
cat data/index.json

# Start API server
uvicorn src.api.main:app --reload
# Access at: http://localhost:8000
```

---

## 📁 Project Structure

```
lender-products-collector/
├── src/                          # Source code
│   ├── agents/                   # LangGraph agents
│   │   ├── workflows/           # Workflow orchestration
│   │   ├── collector/           # Data collection agents
│   │   ├── discovery/           # URL discovery agents
│   │   ├── scheduler/           # Scheduling agents
│   │   └── ...
│   ├── api/                     # FastAPI application
│   ├── models/                  # BIAN schema Pydantic models
│   ├── schemas/                 # Reference schemas
│   ├── configs/                 # Configuration files
│   └── services/                # Business services
│
├── data/                         # Data directory (git-ignored)
│   ├── current/                 # Latest collected data
│   ├── snapshots/               # Historical backups
│   └── index.json               # Collection catalog
│
├── tests/                        # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── utils/                   # Test utilities
│
├── debug/                        # Debug tools
│   ├── scraper/                 # Scraping debug tools
│   └── discovery/               # Discovery debug tools
│
├── project-docs/                 # Documentation
│   ├── REQUIREMENTS.md          # Functional requirements
│   ├── ARCHITECTURE.md          # System architecture
│   ├── DESIGN.md                # Detailed design
│   ├── TESTING.md               # Testing strategy
│   ├── CODING_STANDARDS.md      # Development standards
│   └── TECHNICAL_STACK.md       # Technology choices
│
├── run_collection.py             # Main entry point
├── test.py                       # Test script
└── requirements.txt              # Dependencies
```

---

## 🔄 How It Works

### 1. Load Configuration
Loads lenders from `src/configs/lenders.json`:
```json
{
  "lender_name": "ANZ",
  "abbreviation": "ANZ",
  "domain": "anz.com.au",
  "enabled": true,
  "priority": 1
}
```

### 2. Discover URLs (Google Search)
For each lender, searches Google:
```
site:anz.com.au intitle:"home loan" interest rates
```
Returns top 3 relevant pages.

### 3. Extract Data (Multi-Strategy)
For each URL, tries 5 extraction strategies:
1. **Network Introspection** - Capture JSON APIs
2. **JSON-LD** - Structured data
3. **Embedded State** - JavaScript state objects
4. **Select Dropdowns** - ✅ Working for ANZ!
5. **DOM Parsing** - Fallback

### 4. Save Results
- Current: `data/current/by_lender/{LENDER}.json`
- Snapshot: `data/snapshots/parsed/{LENDER}/{timestamp}.json`
- Catalog: `data/index.json`

### 5. Serve via API
```bash
GET /api/v1/products/       # All products
GET /api/v1/products/ANZ    # ANZ products only
```

---

## 📊 Current Results

### Collection Status
- ✅ **ANZ**: 8 products (select dropdown strategy)
- ⚠️ **CBA**: 0 products (Google search needs fixing)
- ⚠️ **Westpac**: 0 products
- ⚠️ **NAB**: 0 products

### Data Quality
- ✅ BIAN schema compliant
- ✅ Proper validation
- ✅ Source URL tracked
- ✅ Collection timestamp recorded

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Debug specific bank
python debug/scraper/batch_analyze_banks.py
```

---

## 📚 Documentation

See `project-docs/` for complete documentation:

- **[REQUIREMENTS.md](project-docs/REQUIREMENTS.md)** - What we're building
- **[ARCHITECTURE.md](project-docs/ARCHITECTURE.md)** - How it's structured
- **[DESIGN.md](project-docs/DESIGN.md)** - Module details
- **[TESTING.md](project-docs/TESTING.md)** - Testing approach
- **[CODING_STANDARDS.md](project-docs/CODING_STANDARDS.md)** - Development practices

---

## 🐛 Troubleshooting

### Issue: No products collected
**Solution**: Run debug tools to inspect page structure
```bash
python debug/scraper/debug_page_inspector.py
```

### Issue: Google search returns 0 URLs
**Solution**: Test search and check regex pattern
```bash
python debug/discovery/test_google_search.py
```

### Issue: Playwright timeout
**Solution**: Increase timeout or use 'domcontentloaded' wait

---

## 🤝 Contributing

1. Follow [CODING_STANDARDS.md](project-docs/CODING_STANDARDS.md)
2. Write tests for new features
3. Update documentation
4. No mock data in main application files

---

## 📝 License

[To be defined]

---

## 🔗 Related Projects

- **[property-finance-ai](../property-finance-ai/)** - Mortgage finder agent (consumes this data)
- **[stock-analysis-ai](../stock-analysis-ai/)** - Stock analysis project

---

## 📧 Contact

[To be defined]

---

**Built with** ❤️ **using LangGraph, Playwright, and FastAPI**
