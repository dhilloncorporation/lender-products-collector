"""Product data endpoints - serves collected loan products."""

from typing import List
from fastapi import APIRouter, HTTPException
from ...models import LoanProduct

router = APIRouter()


@router.get("/", response_model=List[LoanProduct])
async def get_products():
    """Get all collected loan products."""
    # TODO: Implement product service to fetch from storage
    # For now, return empty list until storage service is implemented
    return []


@router.get("/{lender}", response_model=List[LoanProduct])
async def get_products_by_lender(lender: str):
    """Get products by lender from collected data."""
    # TODO: Implement product service to query by lender
    # For now, return empty list until storage service is implemented
    return []
