# Python Development Best Practices

## Code Organization

### 1. Separation of Concerns
- **API Routers**: Only contain endpoint logic, no business logic or mock data
- **Service Layer**: Handle business logic and data operations
- **Models**: Pure data structures with validation
- **Tests**: All mock data and test utilities in `tests/` directory

### 2. File Structure
```
src/
├── api/           # API endpoints only
├── services/      # Business logic layer
├── models/        # Data models
├── agents/        # Agent implementations
└── utils/         # Utility functions

tests/
├── unit/          # Unit tests
├── integration/   # Integration tests
└── utils/         # Test utilities and mock data
```

### 3. Mock Data Rules
- ❌ **NEVER** put mock data in main application files
- ✅ **ALWAYS** put mock data in `tests/utils/mock_data.py`
- ✅ Use dependency injection for testable code
- ✅ Keep production code clean and mock-free

### 4. API Design
- Endpoints should be thin - delegate to service layer
- Use proper HTTP status codes
- Include comprehensive error handling
- Document all endpoints with clear docstrings

### 5. Error Handling
- Use specific exception types
- Provide meaningful error messages
- Log errors appropriately
- Don't expose internal details in API responses

### 6. Testing
- Write tests for all business logic
- Use dependency injection for testability
- Mock external dependencies
- Keep test data separate from production code

## Example: Clean API Router

```python
# ❌ BAD - Mock data in main file
@router.get("/products")
async def get_products():
    return [{"id": 1, "name": "Test Product"}]  # Mock data here

# ✅ GOOD - Clean separation
@router.get("/products")
async def get_products():
    return await product_service.get_all_products()
```

## Example: Proper Test Structure

```python
# tests/utils/mock_data.py
def get_mock_products():
    return [LoanProduct(...)]

# tests/unit/test_products.py
def test_get_products(mock_product_service):
    mock_product_service.get_all_products.return_value = get_mock_products()
    # Test logic here
```

## Code Quality Checklist

- [ ] No mock data in main application files
- [ ] API routers are thin and delegate to services
- [ ] All business logic is in service layer
- [ ] Tests use proper mocking and test utilities
- [ ] Error handling is comprehensive
- [ ] Code is properly documented
- [ ] Dependencies are injected for testability
