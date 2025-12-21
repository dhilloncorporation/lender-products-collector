# Agent Test Organization

This document describes how test cases are organized for each agent in the project.

## Test Structure

Tests are organized to mirror the source code structure, with each agent having its test cases in the corresponding folder under `tests/unit/agents/`.

```
tests/
├── unit/
│   ├── agents/                          # Agent tests (mirrors src/agents/)
│   │   ├── api/
│   │   │   └── test_product_api_agent.py
│   │   ├── collector/
│   │   │   └── test_playwright_collector_agent.py
│   │   ├── discovery/
│   │   │   └── test_discovery_agents.py
│   │   ├── monitoring/
│   │   │   └── test_collection_monitor_agent.py
│   │   ├── normalizer/
│   │   │   └── test_product_normalizer_agent.py
│   │   ├── scheduler/
│   │   │   └── test_collection_scheduler_agent.py
│   │   ├── storage/
│   │   │   └── test_product_storage_agent.py
│   │   └── workflows/
│   │       └── test_collection_workflow.py
│   │
│   └── services/                        # Service tests
│       └── test_json_storage_service.py
│
└── integration/                         # Integration tests
    ├── test_collector_discovery_integration.py
    ├── test_api_integration.py
    └── ...
```

## Test Coverage by Agent

### 1. **API Agent** (`agents/api/`)
- **Test File**: `test_product_api_agent.py`
- **Coverage**:
  - REST API endpoints
  - Query parameter validation
  - Error handling
  - Response model validation

### 2. **Collector Agent** (`agents/collector/`)
- **Test File**: `test_playwright_collector_agent.py`
- **Coverage**:
  - Multi-strategy extraction (Network, JSON-LD, Embedded State, Select Dropdowns, DOM)
  - Context manager lifecycle
  - Error handling and timeouts
  - Product parsing and validation

### 3. **Discovery Agents** (`agents/discovery/`)
- **Test File**: `test_discovery_agents.py`
- **Coverage**:
  - WebSearchDiscovery: Query generation, URL building, search engine fallbacks
  - GoogleCustomSearchAPI: API integration, rate limiting, error handling
  - URL validation and extraction

### 4. **Monitoring Agent** (`agents/monitoring/`)
- **Test File**: `test_collection_monitor_agent.py`
- **Coverage**:
  - Collection logging and metrics tracking
  - Data freshness monitoring
  - System health assessment
  - Alert management

### 5. **Normalizer Agent** (`agents/normalizer/`)
- **Test File**: `test_product_normalizer_agent.py`
- **Coverage**:
  - Data extraction from raw product data
  - Rate parsing with multiple patterns
  - Feature detection and fee normalization
  - Error handling

### 6. **Scheduler Agent** (`agents/scheduler/`)
- **Test File**: `test_collection_scheduler_agent.py`
- **Coverage**:
  - Scheduler lifecycle management
  - Daily and hourly collection workflows
  - Concurrent collection handling
  - Error handling

### 7. **Storage Agent** (`agents/storage/`)
- **Test File**: `test_product_storage_agent.py`
- **Coverage**:
  - Product storage and retrieval
  - Deduplication logic
  - Product filtering (lender, rate type, rate range)
  - Storage statistics
  - Change detection

### 8. **Workflow** (`agents/workflows/`)
- **Test File**: `test_collection_workflow.py`
- **Coverage**:
  - LangGraph state machine
  - Collection workflow orchestration
  - Error handling and state transitions

## Running Tests

### Run all agent tests
```bash
pytest tests/unit/agents/
```

### Run tests for specific agent
```bash
# Collector agent
pytest tests/unit/agents/collector/

# Discovery agents
pytest tests/unit/agents/discovery/

# All discovery-related tests
pytest tests/unit/agents/discovery/ tests/integration/test_collector_discovery_integration.py
```

### Run with coverage
```bash
pytest tests/unit/agents/ --cov=src/agents --cov-report=html
```

### Run specific test class
```bash
pytest tests/unit/agents/collector/test_playwright_collector_agent.py::TestPlaywrightCollectorAgent
```

## Test Conventions

1. **Naming**: Test files are named `test_<agent_name>_agent.py`
2. **Structure**: Test classes are named `Test<AgentName>`
3. **Fixtures**: Shared fixtures are in `tests/conftest.py`
4. **Mock Data**: Reusable mock data is in `tests/utils/mock_data.py`
5. **Async Tests**: Use `@pytest.mark.asyncio` decorator for async tests

## Integration Tests

Integration tests that test multiple agents together are in `tests/integration/`:
- `test_collector_discovery_integration.py` - Tests discovery + collector together
- `test_api_integration.py` - Tests API with real data
- Other end-to-end workflow tests

## Benefits of This Organization

✅ **Clear Structure**: Easy to locate tests for specific agents
✅ **Mirrors Source**: Test structure matches source code structure
✅ **Scalable**: Easy to add new test files as agents are added
✅ **Maintainable**: Changes to source structure can be reflected in tests
✅ **IDE Support**: Better navigation and auto-completion

