# Test Structure

This document describes the organization of test files in the project.

## Directory Structure

The test directory structure mirrors the source code structure for better organization and maintainability.

```
tests/
├── conftest.py                          # Pytest configuration and shared fixtures
├── utils/
│   ├── __init__.py
│   └── mock_data.py                     # Mock data for tests
│
├── unit/                                # Unit tests
│   ├── agents/                          # Agent tests (mirrors src/agents/)
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── test_product_api_agent.py
│   │   ├── collector/
│   │   │   ├── __init__.py
│   │   │   └── test_playwright_collector_agent.py
│   │   ├── discovery/
│   │   │   ├── __init__.py
│   │   │   └── test_discovery_agents.py
│   │   ├── monitoring/
│   │   │   ├── __init__.py
│   │   │   └── test_collection_monitor_agent.py
│   │   ├── normalizer/
│   │   │   ├── __init__.py
│   │   │   └── test_product_normalizer_agent.py
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   └── test_collection_scheduler_agent.py
│   │   └── workflows/
│   │       ├── __init__.py
│   │       └── test_collection_workflow.py
│   │
│   ├── services/                        # Service tests (mirrors src/services/)
│   │   ├── __init__.py
│   │   └── test_json_storage_service.py
│   │
│   ├── test_google_custom_search.py     # Legacy integration test
│   ├── test_simple_collection.py        # Legacy integration test
│   └── test_url_discovery.py            # Legacy integration test
│
└── integration/                         # Integration tests
    ├── test_api_integration.py
    ├── test_cba_search.py
    ├── test_google_custom_search_integration.py
    ├── test_google_search.py
    ├── test_search_engines.py
    └── test_simple_collection.py
```

## Test Coverage by Agent

### 1. **Collector Agent** (`agents/collector/`)
- **File**: `test_playwright_collector_agent.py`
- **Coverage**: 
  - Multi-strategy extraction (Network, JSON-LD, Embedded State, Select Dropdowns, DOM)
  - Context manager lifecycle
  - Error handling and timeouts
  - Product parsing and validation

### 2. **Discovery Agents** (`agents/discovery/`)
- **File**: `test_discovery_agents.py`
- **Coverage**:
  - WebSearchDiscovery: Query generation, URL building, search engine fallbacks
  - GoogleCustomSearchAPI: API integration, rate limiting, error handling

### 3. **API Agent** (`agents/api/`)
- **File**: `test_product_api_agent.py`
- **Coverage**:
  - REST API endpoints
  - Query parameter validation
  - Error handling and HTTP status codes
  - Response model validation

### 4. **Monitoring Agent** (`agents/monitoring/`)
- **File**: `test_collection_monitor_agent.py`
- **Coverage**:
  - Collection logging and metrics tracking
  - Data freshness monitoring
  - System health assessment
  - Alert management

### 5. **Normalizer Agent** (`agents/normalizer/`)
- **File**: `test_product_normalizer_agent.py`
- **Coverage**:
  - Data extraction from raw product data
  - Rate parsing with multiple patterns
  - Feature detection and fee normalization

### 6. **Scheduler Agent** (`agents/scheduler/`)
- **File**: `test_collection_scheduler_agent.py`
- **Coverage**:
  - Scheduler lifecycle management
  - Daily and hourly collection workflows
  - Concurrent collection handling

### 7. **Workflow** (`agents/workflows/`)
- **File**: `test_collection_workflow.py`
- **Coverage**:
  - LangGraph state machine
  - Collection workflow orchestration
  - Error handling and state transitions

### 8. **Storage Service** (`services/`)
- **File**: `test_json_storage_service.py`
- **Coverage**:
  - File operations (save/load)
  - Index management
  - Concurrent access handling

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run unit tests only
```bash
pytest tests/unit/
```

### Run specific agent tests
```bash
# Collector agent tests
pytest tests/unit/agents/collector/

# Discovery agent tests
pytest tests/unit/agents/discovery/

# API agent tests
pytest tests/unit/agents/api/

# All agent tests
pytest tests/unit/agents/
```

### Run with coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run with verbose output
```bash
pytest tests/ -v
```

## Test Conventions

1. **Naming**: Test files are named `test_<module_name>.py`
2. **Structure**: Test classes are named `Test<ClassName>`
3. **Fixtures**: Shared fixtures are in `conftest.py`
4. **Mock Data**: Reusable mock data is in `tests/utils/mock_data.py`
5. **Async Tests**: Use `@pytest.mark.asyncio` decorator for async tests

## Benefits of This Structure

✅ **Clear Organization**: Easy to locate tests for specific components
✅ **Mirrors Source**: Test structure matches source code structure
✅ **Scalability**: Easy to add new test files as the project grows
✅ **Maintainability**: Changes to source code structure can be reflected in tests
✅ **IDE Support**: Better navigation and auto-completion in IDEs


