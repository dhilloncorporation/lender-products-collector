# Project Summary - Quick Start

## Overview

AI-powered loan product collection system using LangGraph agent architecture.

## Quick Start

```bash
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install

# Run collection
python run_collection.py

# Start API
uvicorn src.api.main:app --reload
```

## Agents

| Agent | File | Role |
|-------|------|------|
| CollectionWorkflow | `src/agents/workflows/collection_workflow.py` | Orchestrator |
| PlaywrightCollectorAgent | `src/agents/collector/playwright_collector.py` | Data Collection |
| WebSearchDiscovery | `src/agents/discovery/web_search_discovery.py` | URL Discovery |
| ProductNormalizerAgent | `src/agents/normalizer/product_normalizer.py` | Data Normalization |
| ProductStorageAgent | `src/agents/storage/product_storage.py` | Data Storage |
| ProductAPIAgent | `src/agents/api/product_api.py` | API Service |

**Detailed documentation**: See docstrings in each agent file.

## Data Location

- Current products: `data/current/by_lender/{LENDER}.json`
- Snapshots: `data/snapshots/parsed/{LENDER}/`
- Index: `data/index.json`

## Configuration

- Lenders: `src/configs/lenders.json`
- Settings: `src/configs/collection_settings.yaml`

**For detailed architecture, design, and requirements**: See ARCHITECTURE.md, DESIGN.md, REQUIREMENTS.md
