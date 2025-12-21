# Design Overview

## Key Design Decisions

### LangGraph Workflow
- State machine for complex orchestration
- Built-in error handling and retries
- Extensible for future AI features

### Multi-Strategy Extraction
- 5 strategies handle different website structures
- Cascading fallback ensures maximum coverage
- No custom code per bank required

### JSON Storage
- Simple, portable, human-readable
- Sufficient for 15 lenders
- Easy backup and version control

### BIAN Schema
- Industry standard format
- Comprehensive coverage
- Interoperable with other systems

## Module Structure

- **Workflows**: LangGraph orchestration (`collection_workflow.py`)
- **Collector**: Multi-strategy extraction (`playwright_collector.py`)
- **Discovery**: URL discovery via search (`web_search_discovery.py`)
- **Storage**: JSON persistence (`json_storage.py`)
- **Models**: BIAN schema (`product.py`)

**Detailed module documentation**: See docstrings in each module file.
