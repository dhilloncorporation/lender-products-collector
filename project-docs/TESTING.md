# Testing

## Structure

```
tests/
├── unit/          # Fast, isolated tests
├── integration/   # Component interaction tests
└── utils/         # Mock data and fixtures
```

## Run Tests

```bash
pytest tests/ -v                    # All tests
pytest tests/unit/ -v              # Unit tests only
pytest tests/ --cov=src            # With coverage
```

## Guidelines

- Test one thing per test
- Mock external dependencies
- Use `tests/utils/mock_data.py` for test data
- No mock data in main application files

**Detailed testing docs**: See test files and `tests/AGENT_TEST_ORGANIZATION.md`
