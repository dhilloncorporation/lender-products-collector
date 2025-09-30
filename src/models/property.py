"""Property details models."""

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class PropertyDetails(BaseModel):
    """Property information."""
    
    value: Decimal = Field(..., description="Property value", gt=0)
    postcode: str = Field(..., description="Property postcode", min_length=4, max_length=10)
    property_type: Literal["house", "apartment", "townhouse", "land"] = Field(..., description="Property type")
    occupancy: Literal["owner_occupied", "investment"] = Field(..., description="Occupancy type")
    
    @property
    def lvr(self, loan_amount: Decimal) -> Decimal:
        """Calculate Loan-to-Value Ratio."""
        return (loan_amount / self.value) * 100
