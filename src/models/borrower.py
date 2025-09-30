"""Borrower profile models."""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class BorrowerProfile(BaseModel):
    """Borrower financial profile."""
    
    income: Decimal = Field(..., description="Annual gross income", gt=0)
    employment_type: str = Field(..., description="Full-time, part-time, self-employed, etc.")
    credit_score: int = Field(..., description="Credit score", ge=300, le=850)
    dependents: int = Field(default=0, description="Number of dependents", ge=0)
    existing_debts: Decimal = Field(default=0, description="Monthly debt payments", ge=0)
    deposit_amount: Decimal = Field(..., description="Available deposit", ge=0)
    
    @property
    def net_monthly_income(self) -> Decimal:
        """Calculate net monthly income (simplified)."""
        return (self.income / 12) * Decimal("0.7")  # 30% tax assumption
    
    @property
    def available_monthly_payment(self) -> Decimal:
        """Calculate available monthly payment after existing debts."""
        return self.net_monthly_income - self.existing_debts
