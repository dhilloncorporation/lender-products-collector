"""Loan preference models."""

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class LoanPreferences(BaseModel):
    """Borrower loan preferences."""
    
    rate_type: Literal["fixed", "variable", "split"] = Field(..., description="Preferred rate type")
    term_years: int = Field(default=30, description="Loan term in years", ge=1, le=50)
    offset_required: bool = Field(default=False, description="Requires offset account")
    redraw_ok: bool = Field(default=False, description="Accepts redraw facility")
    fee_sensitivity: Literal["low", "medium", "high"] = Field(default="medium", description="Fee sensitivity")
    cashback_ok: bool = Field(default=False, description="Interested in cashback offers")
    max_lvr: Decimal = Field(default=Decimal("95"), description="Maximum LVR %", ge=0, le=100)
    max_dti: Decimal = Field(default=Decimal("6"), description="Maximum debt-to-income ratio", ge=0)
