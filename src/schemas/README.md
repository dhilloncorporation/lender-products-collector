# Financial Product Schemas

This directory contains reference schemas for financial product data collection and validation.

## BIAN Financial Product Schema

The `bian_financial_product_schema.json` file contains a comprehensive example of the BIAN (Banking Industry Architecture Network) standard for financial product data.

### Key Components:

- **Product Information**: Basic product details, versioning, status
- **Pricing**: Interest components, fees, calculation methods
- **Features**: Product capabilities (offset, redraw, split loans, etc.)
- **Eligibility**: Borrower requirements, loan limits, property types
- **Security**: Collateral requirements, valuation policies
- **Policy**: Serviceability rules, lending policies
- **Compliance**: Regulatory requirements, APRA codes
- **Distribution**: Target market determination, channels

### Usage:

1. **Reference**: Use as a template for data collection
2. **Validation**: Validate collected data against this structure
3. **Documentation**: Understand required fields and data types
4. **API Design**: Design APIs to match this schema

### Example Usage:

```python
import json
from src.schemas.bian_financial_product_schema import load_reference_schema

# Load reference schema
schema = load_reference_schema()

# Validate collected data
validate_product_data(collected_data, schema)
```

## Schema Evolution

This schema follows BIAN standards and should be updated as:
- New regulatory requirements emerge
- BIAN standards evolve
- Additional product features are needed
- Data collection requirements change

## Related Files:

- `src/models/product.py` - **Pydantic models created from this BIAN schema**
- `src/agents/collector/playwright_collector.py` - Data collection using the models
- `src/configs/lenders.json` - Lender configuration for collection

## Model Generation:

The Pydantic models in `src/models/product.py` are directly based on this BIAN schema:

- `LoanProduct` - Main product model matching the schema structure
- `InterestComponent` - Maps to `pricing.interestComponents`
- `FeeStructure` - Maps to `pricing.fees`
- `ProductFeatures` - Maps to `features`
- `EligibilityCriteria` - Maps to `eligibility`

When the schema evolves, the models should be updated to match.
