"""Product matching endpoints."""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ...models import BorrowerProfile, PropertyDetails, LoanPreferences, ProductMatch

router = APIRouter()


class MatchRequest(BaseModel):
    """Request for product matching."""
    borrower: BorrowerProfile
    property: PropertyDetails
    preferences: LoanPreferences


@router.post("/", response_model=List[ProductMatch])
async def find_matches(request: MatchRequest):
    """Find matching loan products based on criteria."""
    # TODO: Implement actual matching logic
    # For now, return mock matches
    return [
        ProductMatch(
            product=request.borrower,  # This will be replaced with actual logic
            score=85,
            monthly_payment=2500.00,
            explanation="Good rate with offset account",
            trade_offs=["Higher fees", "Limited redraw"]
        )
    ]


@router.get("/health")
async def health():
    """Health check for matching service."""
    return {"status": "healthy", "service": "matcher"}
