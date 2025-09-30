"""Pydantic models for loan product data collection."""

from .product import (
    LoanProduct,
    InterestComponent,
    FeeStructure,
    ProductFeatures,
    EligibilityCriteria,
    ProductMatch
)

__all__ = [
    "LoanProduct",
    "InterestComponent", 
    "FeeStructure",
    "ProductFeatures",
    "EligibilityCriteria",
    "ProductMatch",
]
