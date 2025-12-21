"""Loan product models based on BIAN financial product schema.

Reference Schema: src/schemas/bian_financial_product_schema.json

These Pydantic models are created from the BIAN (Banking Industry Architecture Network) 
financial product schema. When the schema evolves, these models should be updated to match.

Schema Mapping:
- LoanProduct -> Main product structure
- InterestComponent -> pricing.interestComponents
- FeeStructure -> pricing.fees  
- ProductFeatures -> features
- EligibilityCriteria -> eligibility
"""

from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class InterestComponent(BaseModel):
    """Interest rate component for split loans."""
    name: str = Field(..., description="Component name")
    rate_type: Literal["Fixed", "VariableIndex", "Variable"] = Field(..., description="Rate type")
    fixed_term_months: Optional[int] = Field(None, description="Fixed term in months")
    comparison_rate_pct_au: Decimal = Field(..., description="Comparison rate %")
    margin_pct: Optional[Decimal] = Field(None, description="Margin above index")
    floor_pct: Optional[Decimal] = Field(None, description="Floor rate %")
    applicability: Dict[str, Any] = Field(default_factory=dict, description="Applicability rules")


class FeeStructure(BaseModel):
    """Fee structure breakdown."""
    upfront: List[Dict[str, Any]] = Field(default_factory=list, description="Upfront fees")
    ongoing: List[Dict[str, Any]] = Field(default_factory=list, description="Ongoing fees")
    event_driven: List[Dict[str, Any]] = Field(default_factory=list, description="Event-driven fees")


class ProductFeatures(BaseModel):
    """Product features and benefits."""
    offset_account: Dict[str, Any] = Field(default_factory=dict, description="Offset account details")
    redraw: Dict[str, Any] = Field(default_factory=dict, description="Redraw facility")
    extra_repayments: Dict[str, Any] = Field(default_factory=dict, description="Extra repayment rules")
    split_loans: Dict[str, Any] = Field(default_factory=dict, description="Split loan options")
    rate_lock: Dict[str, Any] = Field(default_factory=dict, description="Rate lock facility")
    package: Dict[str, Any] = Field(default_factory=dict, description="Package details")


class EligibilityCriteria(BaseModel):
    """Eligibility criteria for the product."""
    min_loan_amount_aud: Decimal = Field(..., description="Minimum loan amount")
    max_loan_amount_aud: Decimal = Field(..., description="Maximum loan amount")
    min_age_years: int = Field(..., description="Minimum age")
    residency: List[str] = Field(default_factory=list, description="Residency requirements")
    borrower_types: List[str] = Field(default_factory=list, description="Eligible borrower types")
    occupancy: List[str] = Field(default_factory=list, description="Occupancy types")
    max_lvr_by_segment: List[Dict[str, Any]] = Field(default_factory=list, description="LVR limits by segment")
    property_types_allowed: List[str] = Field(default_factory=list, description="Allowed property types")


class LoanProduct(BaseModel):
    """Comprehensive loan product based on BIAN schema."""
    
    # Basic product info
    schema_version: str = Field(default="1.0.0", description="Schema version")
    product_id: str = Field(..., description="Unique product identifier")
    version: str = Field(..., description="Product version")
    status: str = Field(..., description="Product status")
    name: str = Field(..., description="Product name")
    short_name: str = Field(..., description="Short product name")
    description: str = Field(..., description="Product description")
    jurisdiction: str = Field(default="AU", description="Jurisdiction")
    category: str = Field(default="Mortgage", description="Product category")
    purpose: str = Field(..., description="Loan purpose")
    channels: List[str] = Field(default_factory=list, description="Distribution channels")
    
    # Pricing and rates
    interest_components: List[InterestComponent] = Field(default_factory=list, description="Interest rate components")
    fees: FeeStructure = Field(default_factory=FeeStructure, description="Fee structure")
    
    # Features
    features: ProductFeatures = Field(default_factory=ProductFeatures, description="Product features")
    
    # Eligibility
    eligibility: EligibilityCriteria = Field(..., description="Eligibility criteria")
    
    # Repayment terms
    repayment_type: str = Field(default="PrincipalAndInterest", description="Repayment type")
    amortization_term_months: int = Field(default=360, description="Amortization term")
    frequency_options: List[str] = Field(default_factory=list, description="Repayment frequency options")
    
    # Security
    security: Dict[str, Any] = Field(default_factory=dict, description="Security requirements")
    
    # Policy
    policy: Dict[str, Any] = Field(default_factory=dict, description="Lending policy")
    
    # Compliance
    compliance: Dict[str, Any] = Field(default_factory=dict, description="Compliance information")
    
    # Collection metadata
    lender: str = Field(..., description="Lender name")
    source_url: str = Field(..., description="Source URL")
    collected_at: datetime = Field(default_factory=datetime.now, description="Collection timestamp")
    
    # Legacy fields for backward compatibility
    @property
    def rate_percent(self) -> Decimal:
        """Get primary interest rate for backward compatibility."""
        if self.interest_components:
            return self.interest_components[0].comparison_rate_pct_au
        return Decimal("0.0")
    
    @property
    def comparison_rate_percent(self) -> Decimal:
        """Get comparison rate for backward compatibility."""
        return self.rate_percent
    
    @property
    def rate_type(self) -> str:
        """Get rate type for backward compatibility."""
        if self.interest_components:
            return self.interest_components[0].rate_type.lower()
        return "variable"
    
    @property
    def lvr_max(self) -> Decimal:
        """Get maximum LVR for backward compatibility."""
        if self.eligibility.max_lvr_by_segment:
            return max(segment.get("maxLVR", 0) * 100 for segment in self.eligibility.max_lvr_by_segment)
        return Decimal("95.0")
    
    def get_rate_by_lvr(self, lvr: Decimal) -> Optional[Decimal]:
        """
        Get interest rate for a specific LVR.
        
        Args:
            lvr: Loan-to-Value Ratio as decimal (e.g., 0.80 for 80%)
            
        Returns:
            Comparison rate for the LVR tier, or None if not found
        """
        # Normalize LVR to decimal (handle percentage input)
        if lvr > 1.0:
            lvr = lvr / 100
        
        # Find matching LVR tier
        for component in self.interest_components:
            applicability = component.applicability
            if "lvr_min" in applicability and "lvr_max" in applicability:
                lvr_min = Decimal(str(applicability["lvr_min"]))
                lvr_max = Decimal(str(applicability["lvr_max"]))
                lvr_exclusive_max = applicability.get("lvr_exclusive_max", False)
                
                # Check if LVR falls within this tier
                if lvr_exclusive_max:
                    if lvr_min <= lvr < lvr_max:
                        return component.comparison_rate_pct_au
                else:
                    if lvr_min <= lvr <= lvr_max:
                        return component.comparison_rate_pct_au
        
        # Fallback to first component if no LVR tier matches
        return self.rate_percent
    
    def get_lvr_tiers(self) -> List[Dict[str, Any]]:
        """
        Get all LVR tiers for this product.
        
        Returns:
            List of dictionaries with tier information:
            [
                {
                    "tier": "≤80%",
                    "rate": Decimal("6.49"),
                    "lvr_min": 0.0,
                    "lvr_max": 0.80
                },
                ...
            ]
        """
        tiers = []
        for component in self.interest_components:
            applicability = component.applicability
            if "lvr_tier" in applicability or ("lvr_min" in applicability and "lvr_max" in applicability):
                tier_info = {
                    "tier": applicability.get("lvr_tier", ""),
                    "rate": component.comparison_rate_pct_au,
                    "lvr_min": applicability.get("lvr_min"),
                    "lvr_max": applicability.get("lvr_max"),
                    "rate_type": component.rate_type,
                    "component_name": component.name
                }
                tiers.append(tier_info)
        
        # Sort by LVR min if available
        tiers.sort(key=lambda x: x.get("lvr_min", 0) or 0)
        return tiers
    
    def has_lvr_tiers(self) -> bool:
        """Check if product has multiple LVR tiers."""
        return len(self.get_lvr_tiers()) > 1


class ProductMatch(BaseModel):
    """Product match with scoring and explanation."""
    
    product: LoanProduct = Field(..., description="Matched product")
    score: int = Field(..., description="Match score 0-100", ge=0, le=100)
    monthly_payment: Decimal = Field(..., description="Calculated monthly payment")
    explanation: str = Field(..., description="Plain English explanation")
    trade_offs: List[str] = Field(default_factory=list, description="Trade-offs to consider")
