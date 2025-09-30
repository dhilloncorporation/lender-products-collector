# Testing Strategy and Guidelines

## 🧪 Testing Approach

### Test Pyramid

```
        ╱╲
       ╱E2E╲         Few (slow, comprehensive)
      ╱──────╲
     ╱Integration╲    Some (medium speed)
    ╱────────────╲
   ╱  Unit Tests  ╲   Many (fast, focused)
  ╱────────────────╲
```

## 📁 Test Structure

```
tests/
├── unit/                          # Unit tests (fast)
│   ├── test_collection_workflow.py
│   ├── test_extraction_strategies.py
│   └── test_models.py
├── integration/                   # Integration tests
│   ├── test_api_integration.py
│   └── test_storage_integration.py
├── e2e/                          # End-to-end tests
│   └── test_full_collection.py
├── utils/                        # Test utilities
│   ├── mock_data.py             # Mock BIAN products
│   └── fixtures.py
└── conftest.py                   # pytest configuration
```

## ✅ Unit Testing Guidelines

### What to Test
- Each extraction strategy independently
- BIAN schema validation
- Configuration loading
- URL construction
- Data transformation logic

### Example: Test Extraction Strategy
```python
import pytest
from src.agents.collector.playwright_collector import PlaywrightCollectorAgent

@pytest.mark.asyncio
async def test_select_dropdown_extraction(mock_page):
    """Test Strategy 3: Select dropdown extraction."""
    # Arrange
    mock_page.query_selector_all.return_value = [mock_select_element]
    collector = PlaywrightCollectorAgent()
    
    # Act
    products = await collector._extract_from_select_dropdowns(
        mock_page, "ANZ", "https://test.com"
    )
    
    # Assert
    assert len(products) > 0
    assert products[0].lender == "ANZ"
    assert products[0].interest_components[0].comparison_rate_pct_au > 0
```

### Mocking Guidelines
- Mock Playwright `Page` object
- Mock HTTP responses for Google search
- Use `tests/utils/mock_data.py` for sample products
- Don't mock Pydantic models (test real validation)

---

## 🔗 Integration Testing Guidelines

### What to Test
- API endpoints with real FastAPI TestClient
- Workflow coordination between agents
- Storage read/write operations
- Configuration loading

### Example: Test API
```python
from fastapi.testclient import TestClient
from src.api.main import app

def test_get_products_endpoint():
    """Test products API endpoint."""
    client = TestClient(app)
    response = client.get("/api/v1/products/")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
```

---

## 🌐 End-to-End Testing Guidelines

### What to Test
- Complete collection workflow from start to finish
- Real Playwright browser (headless)
- Actual file system operations
- Real network calls (with rate limiting)

### Example: Test Full Collection
```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_full_collection_workflow():
    """Test complete collection for one lender."""
    # This actually hits the real ANZ website
    # Use sparingly due to network dependency
    
    # Run collection for ANZ only
    # Verify data is saved to data/current/by_lender/ANZ.json
    # Verify BIAN schema compliance
```

---

## 🛠️ Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run Integration Tests
```bash
pytest tests/integration/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run E2E Tests (Slow)
```bash
pytest tests/e2e/ -v --slow
```

---

## 🐛 Debug Tools (Not pytest)

### Scraper Debugging
```bash
# Inspect single page
python debug/scraper/debug_page_inspector.py

# Batch analyze all banks
python debug/scraper/batch_analyze_banks.py

# Test specific extraction
python debug/scraper/extract_anz_products.py
```

### Discovery Debugging
```bash
# Test Google search
python debug/discovery/test_google_search.py
```

### Manual Testing
```bash
# Test full workflow
python run_collection.py

# Test single collector
python test.py
```

---

## ✅ Testing Checklist

Before committing code:

- [ ] All unit tests pass
- [ ] New code has unit tests (>80% coverage)
- [ ] Integration tests pass
- [ ] No mock data in main application files
- [ ] Linter errors fixed
- [ ] Type hints present
- [ ] Docstrings written
- [ ] Manual smoke test performed

---

## 📊 Test Coverage Goals

| Module | Target Coverage | Current |
|--------|----------------|---------|
| Extraction Strategies | 90% | 40% |
| Workflow | 80% | 60% |
| Storage | 90% | 50% |
| Models | 100% | 80% |
| API | 80% | 70% |
| **Overall** | **85%** | **60%** |

---

## 🎯 Testing Best Practices

### DO:
- ✅ Test one thing per test function
- ✅ Use descriptive test names (`test_select_dropdown_extracts_anz_products`)
- ✅ Arrange-Act-Assert pattern
- ✅ Mock external dependencies (network, filesystem)
- ✅ Test edge cases (empty data, malformed HTML, timeouts)
- ✅ Use fixtures for common setup
- ✅ Keep tests independent (no shared state)

### DON'T:
- ❌ Put test data in main application code
- ❌ Make tests depend on external services (unless E2E)
- ❌ Test implementation details (test behavior)
- ❌ Use sleeps (use proper async waits)
- ❌ Ignore failing tests
- ❌ Test third-party libraries (trust Playwright, FastAPI, etc.)

---

## 🔍 Debugging Failed Tests

### Test Fails Locally
1. Run with `-v` for verbose output
2. Use `pytest --pdb` to drop into debugger
3. Check test logs in `.pytest_cache/`
4. Verify test data and mocks

### Test Passes Locally but Fails in CI
1. Check environment differences
2. Verify dependencies are same versions
3. Check for timing issues (race conditions)
4. Use `pytest-xdist` for parallel test isolation

---

## 📝 Writing New Tests

### Template: Unit Test
```python
import pytest
from src.module import ClassToTest

class TestClassName:
    """Test cases for ClassToTest."""
    
    @pytest.fixture
    def instance(self):
        """Create test instance."""
        return ClassToTest()
    
    def test_specific_behavior(self, instance):
        """Test specific behavior description."""
        # Arrange
        input_data = {...}
        
        # Act
        result = instance.method(input_data)
        
        # Assert
        assert result == expected
```

### Template: Async Test
```python
@pytest.mark.asyncio
async def test_async_method():
    """Test async method."""
    result = await async_function()
    assert result is not None
```

---

## 🎯 Future Testing Enhancements

- [ ] Automated E2E tests in CI
- [ ] Visual regression testing (screenshot comparison)
- [ ] Performance benchmarks
- [ ] Load testing for API
- [ ] Contract testing for BIAN schema
- [ ] Mutation testing
- [ ] Property-based testing with Hypothesis
