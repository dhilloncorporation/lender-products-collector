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
import re


def slugify(text: str) -> str:
    """
    FIX 3: Centralized ID normalization utility.
    
    Converts any string to a canonical slug format:
    - Lowercase only
    - Alphanumeric + hyphens
    - No spaces, underscores, or special chars
    - No leading/trailing/duplicate hyphens
    
    Examples:
        "Australia and New Zealand Banking Group" -> "australia-and-new-zealand-banking-group"
        "Simplicity PLUS" -> "simplicity-plus"
        "Owner_Occupied / Investment" -> "owner-occupied-investment"
    """
    if not text:
        return ""
    
    # Lowercase
    slug = text.lower()
    
    # Replace common separators with hyphens
    slug = slug.replace(" ", "-").replace("_", "-").replace("/", "-")
    
    # Replace & with "and"
    slug = slug.replace("&", "-and-")
    
    # Remove all non-alphanumeric except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Remove duplicate hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug


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
    max_loan_amount_aud: Optional[Decimal] = Field(None, description="Maximum loan amount")
    min_age_years: int = Field(..., description="Minimum age")
    residency: List[str] = Field(default_factory=list, description="Residency requirements")
    borrower_types: List[str] = Field(default_factory=list, description="Eligible borrower types")
    occupancy: List[str] = Field(default_factory=list, description="Occupancy types")
    
    # LVR limits - v2.0.0 uses loan type dict, v1.0.0 uses segment list
    max_lvr_by_loan_type: Optional[Dict[str, float]] = Field(
        None, 
        description="Maximum LVR by loan type for v2.0.0 (e.g., {'OwnerOccupied': 0.90, 'Investment': 0.90})"
    )
    max_lvr_by_segment: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="LVR limits by segment for v1.0.0 backward compatibility"
    )
    
    property_types_allowed: List[str] = Field(default_factory=list, description="Allowed property types")
    
    # Filter-based eligibility (from UI enumeration)
    product_segment: Optional[str] = Field(None, description="Product segment (e.g., Premium, Standard, Basic)")
    region_restrictions: Optional[List[str]] = Field(None, description="Geographic regions where product is available")
    borrower_category: Optional[str] = Field(None, description="Borrower category (e.g., Personal, Business, First Home Buyer)")


class RateTier(BaseModel):
    """Rate tier within a pricing state (v2.0.0 schema)."""
    lvr_min: float = Field(..., description="Minimum LVR for this tier (decimal, e.g., 0.60)")
    lvr_max: float = Field(..., description="Maximum LVR for this tier (decimal, e.g., 0.80)")
    interest_rate: Decimal = Field(..., description="Interest rate % p.a.")
    comparison_rate: Decimal = Field(..., description="Comparison rate % p.a.")


class PricingState(BaseModel):
    """
    Explicit pricing state binding for a loan product (v2.0.0 schema).
    
    Each state represents a unique combination of UI filter parameters
    (loan_type, repayment_type, etc.) and contains the rates that apply
    when those filters are active.
    
    This makes pricing state-explicit and audit-safe.
    """
    state_id: str = Field(..., description="Unique state identifier (e.g., OO_PI, INV_IO)")
    state_parameters: Dict[str, str] = Field(
        ..., 
        description="UI state parameters that define this pricing state"
    )
    pricing: Dict[str, Any] = Field(
        ..., 
        description="Pricing data for this state (rate_tiers, index_rate, etc.)"
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extraction metadata (method, strategy, confidence)"
    )


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
    
    def get_rate_by(
        self,
        lvr: Optional[Decimal] = None,
        purpose: Optional[str] = None,
        repayment_type: Optional[str] = None,
        rate_type: Optional[str] = None,
        fixed_term_months: Optional[int] = None
    ) -> Optional[Decimal]:
        """
        Get interest rate for a specific combination of BIAN-aligned dimensions.
        
        Args:
            lvr: Loan-to-Value Ratio as decimal (e.g., 0.80 for 80%)
            purpose: Loan purpose (e.g., "OwnerOccupied_Purchase", "Investment_Purchase")
            repayment_type: Repayment type (e.g., "PrincipalAndInterest", "InterestOnly")
            rate_type: Rate type (e.g., "Fixed", "Variable")
            fixed_term_months: Fixed term in months (for fixed rate products)
            
        Returns:
            Comparison rate for the matching combination, or None if not found
        """
        # Normalize LVR to decimal (handle percentage input)
        if lvr is not None and lvr > 1.0:
            lvr = lvr / 100
        
        # Find matching component
        for component in self.interest_components:
            applicability = component.applicability
            
            # Check LVR match
            if lvr is not None:
                if "lvr_min" in applicability and "lvr_max" in applicability:
                    lvr_min = Decimal(str(applicability["lvr_min"]))
                    lvr_max = Decimal(str(applicability["lvr_max"]))
                    lvr_exclusive_max = applicability.get("lvr_exclusive_max", False)
                    
                    if lvr_exclusive_max:
                        if not (lvr_min <= lvr < lvr_max):
                            continue
                    else:
                        if not (lvr_min <= lvr <= lvr_max):
                            continue
                else:
                    continue  # LVR specified but component doesn't have LVR info
            
            # Check purpose match
            if purpose is not None:
                component_purpose = applicability.get("purpose")
                if component_purpose and component_purpose != purpose:
                    continue
            
            # Check repayment type match
            if repayment_type is not None:
                component_repayment = applicability.get("repayment_type")
                if component_repayment and component_repayment != repayment_type:
                    continue
            
            # Check rate type match
            if rate_type is not None:
                if component.rate_type != rate_type:
                    continue
            
            # Check fixed term match
            if fixed_term_months is not None:
                component_term = component.fixed_term_months
                if component_term and component_term != fixed_term_months:
                    continue
            
            # All criteria matched
            return component.comparison_rate_pct_au
        
        # No match found
        return None
    
    def get_pricing_matrix(self) -> List[Dict[str, Any]]:
        """
        Get all pricing permutations as a matrix of BIAN-aligned dimensions.
        
        Returns:
            List of dictionaries with pricing information:
            [
                {
                    "purpose": "OwnerOccupied_Purchase",
                    "repayment_type": "PrincipalAndInterest",
                    "lvr_tier": "≤80%",
                    "lvr_min": 0.0,
                    "lvr_max": 0.80,
                    "rate_type": "Variable",
                    "fixed_term_months": None,
                    "rate": Decimal("6.49"),
                    "component_name": "Standard Variable"
                },
                ...
            ]
        """
        matrix = []
        for component in self.interest_components:
            applicability = component.applicability
            entry = {
                "purpose": applicability.get("purpose", self.purpose),
                "repayment_type": applicability.get("repayment_type", self.repayment_type),
                "rate_type": component.rate_type,
                "fixed_term_months": component.fixed_term_months,
                "rate": component.comparison_rate_pct_au,
                "component_name": component.name,
                "lvr_tier": applicability.get("lvr_tier"),
                "lvr_min": applicability.get("lvr_min"),
                "lvr_max": applicability.get("lvr_max"),
            }
            matrix.append(entry)
        
        return matrix
    
    def has_permutation(
        self,
        purpose: Optional[str] = None,
        repayment_type: Optional[str] = None,
        rate_type: Optional[str] = None,
        fixed_term_months: Optional[int] = None
    ) -> bool:
        """
        Check if product has a specific permutation.
        
        Args:
            purpose: Loan purpose (e.g., "Investment_Purchase")
            repayment_type: Repayment type (e.g., "InterestOnly")
            rate_type: Rate type (e.g., "Fixed")
            fixed_term_months: Fixed term in months
            
        Returns:
            True if product has matching permutation, False otherwise
        """
        return self.get_rate_by(
            purpose=purpose,
            repayment_type=repayment_type,
            rate_type=rate_type,
            fixed_term_months=fixed_term_months
        ) is not None
    
    def to_hierarchical_json(self) -> Dict[str, Any]:
        """
        Convert LoanProduct to hierarchical JSON structure:
        Product → Loan Type → Repayment Type → LVR Tier
        
        This structure makes state-bound pricing explicit and queryable.
        Each pricing entry is bound to its specific UI state combination.
        
        Returns:
            Dictionary in hierarchical format with state-bound pricing
        """
        # Build hierarchical structure
        loan_types = {}
        
        # Group interest components by state dimensions
        for component in self.interest_components:
            applicability = component.applicability
            
            # Extract state dimensions
            purpose = applicability.get('purpose', self.purpose)
            repayment_type = applicability.get('repayment_type', self.repayment_type)
            
            # Normalize to API format
            # Map purpose to loan type
            if "Investment" in purpose or "Invest" in purpose:
                loan_type = "Investment"
            else:
                loan_type = "OwnerOccupied"
            
            # Map repayment type to API format
            if "InterestOnly" in repayment_type or "Interest Only" in repayment_type or "IO" in repayment_type:
                api_repayment_type = "InterestOnly"
            else:
                api_repayment_type = "PrincipalAndInterest"
            
            # Initialize structure if needed
            if loan_type not in loan_types:
                loan_types[loan_type] = {"repayment_types": {}}
            
            if api_repayment_type not in loan_types[loan_type]["repayment_types"]:
                loan_types[loan_type]["repayment_types"][api_repayment_type] = {"lvr_tiers": []}
            
            # Build LVR tier entry with provenance
            lvr_tier = {
                "lvr_min": applicability.get('lvr_min'),
                "lvr_max": applicability.get('lvr_max'),
                "lvr_tier": applicability.get('lvr_tier'),
                "interest_rate": float(component.comparison_rate_pct_au),
                "comparison_rate": float(component.comparison_rate_pct_au),
                "provenance": {
                    "state_parameters": applicability.get('state_parameters', applicability.get('filter_state', {})),
                    "extraction_method": applicability.get('extraction_method', applicability.get('extraction_strategy', 'unknown')),
                    "extraction_strategy": applicability.get('extraction_strategy', 'unknown'),
                    "strategy_priority": applicability.get('strategy_priority', 0),
                    "confidence_score": applicability.get('confidence_score', 0)
                }
            }
            
            # Add to appropriate tier list
            loan_types[loan_type]["repayment_types"][api_repayment_type]["lvr_tiers"].append(lvr_tier)
        
        # Sort LVR tiers by lvr_max (ascending)
        for loan_type_data in loan_types.values():
            for repayment_data in loan_type_data["repayment_types"].values():
                repayment_data["lvr_tiers"].sort(key=lambda x: (x.get("lvr_max") or 0, x.get("lvr_min") or 0))
        
        # Build final structure
        return {
            "schema_version": self.schema_version,
            "product_id": self.product_id,
            "product_name": self.short_name or self.name,
            "lender": self.lender,
            "rate_type": self.interest_components[0].rate_type if self.interest_components else "Variable",
            "features": {
                "offset_account": bool(self.features.offset_account),
                "redraw": bool(self.features.redraw),
                "package_eligible": bool(self.features.package)
            },
            "eligibility": {
                "min_loan_amount_aud": float(self.eligibility.min_loan_amount_aud),
                "max_loan_amount_aud": float(self.eligibility.max_loan_amount_aud),
                "min_age_years": self.eligibility.min_age_years,
                "residency": self.eligibility.residency,
                "borrower_types": self.eligibility.borrower_types,
                "property_types_allowed": self.eligibility.property_types_allowed,
                "max_lvr_by_segment": [
                    {
                        "segment": seg.get("segment", ""),
                        "maxLVR": seg.get("maxLVR", 0.80)
                    }
                    for seg in self.eligibility.max_lvr_by_segment
                ],
                # Filter-based eligibility (from UI enumeration)
                **({"product_segment": self.eligibility.product_segment} if self.eligibility.product_segment else {}),
                **({"region_restrictions": self.eligibility.region_restrictions} if self.eligibility.region_restrictions else {}),
                **({"borrower_category": self.eligibility.borrower_category} if self.eligibility.borrower_category else {})
            },
            "loan_types": loan_types,
            "metadata": {
                "source_url": self.source_url,
                "collected_at": self.collected_at.isoformat(),
                "schema_version": self.schema_version
            }
        }
    
    def to_state_explicit_json(self) -> Dict[str, Any]:
        """
        Convert LoanProduct to state-explicit JSON structure (Schema v2.0.0).
        
        This structure explicitly binds each pricing state to its UI parameters,
        making it audit-safe and compatible with UI State Enumeration.
        
        Key differences from v1.0.0:
        - Flat array of pricing_states (not nested loan_types → repayment_types)
        - Each state has explicit state_parameters
        - Eligibility and features at product level (invariant across states)
        - Provenance attached to each pricing state
        
        Returns:
            Dictionary in state-explicit format (v2.0.0)
        """
        # Group interest components by state
        state_groups = {}
        
        for component in self.interest_components:
            applicability = component.applicability
            
            # Extract state parameters
            loan_type = applicability.get('purpose', self.purpose)
            repayment_type = applicability.get('repayment_type', self.repayment_type)
            
            # Normalize loan type
            if "Investment" in loan_type or "Invest" in loan_type:
                normalized_loan_type = "Investment"
            else:
                normalized_loan_type = "OwnerOccupied"
            
            # Normalize repayment type
            if "InterestOnly" in repayment_type or "IO" in repayment_type or "Interest Only" in repayment_type:
                normalized_repayment_type = "InterestOnly"
            else:
                normalized_repayment_type = "PrincipalAndInterest"
            
            # Create BIAN-normalized state_id: [Purpose]_[Repayment]_[RateType]
            # This ensures deterministic IDs and prevents collisions
            rate_type_normalized = (self.interest_components[0].rate_type if self.interest_components else "Variable").upper()[:3]
            
            # Map to BIAN standard abbreviations
            purpose_abbrev = "OO" if normalized_loan_type == "OwnerOccupied" else "INV"
            repayment_abbrev = "PI" if normalized_repayment_type == "PrincipalAndInterest" else "IO"
            
            # Composite state ID: PURPOSE_REPAYMENT_RATETYPE (e.g., OO_PI_VAR, INV_IO_FIX)
            state_id = f"{purpose_abbrev}_{repayment_abbrev}_{rate_type_normalized}"
            
            # Initialize state group if needed
            if state_id not in state_groups:
                state_groups[state_id] = {
                    'state_parameters': {
                        'loan_type': normalized_loan_type,
                        'repayment_type': normalized_repayment_type
                    },
                    'rate_tiers': [],
                    'provenance': {
                        'extraction_method': applicability.get('extraction_method', 'unknown'),
                        'extraction_strategy': applicability.get('extraction_strategy', 'unknown'),
                        'confidence_score': applicability.get('confidence_score', 0)
                    }
                }
            
            # Add rate tier
            rate_tier = {
                'lvr_min': float(applicability.get('lvr_min', 0.0)) if applicability.get('lvr_min') is not None else 0.0,
                'lvr_max': float(applicability.get('lvr_max', 0.90)) if applicability.get('lvr_max') is not None else 0.90,
                'interest_rate': float(component.comparison_rate_pct_au),
                'comparison_rate': float(component.comparison_rate_pct_au)
            }
            state_groups[state_id]['rate_tiers'].append(rate_tier)
        
        # Convert state groups to pricing_states array
        pricing_states = []
        for state_id, state_data in state_groups.items():
            # Sort rate tiers by LVR
            state_data['rate_tiers'].sort(key=lambda x: (x['lvr_min'], x['lvr_max']))
            
            # FIX 1: STRICT LVR OVERLAP VALIDATOR (Critical Data Integrity)
            # 
            # Principle: A Pricing State = (Purpose + Repayment + RateType) must have
            # unique pricing for each LVR band. If two different rates exist for same LVR,
            # it's an identification error.
            #
            # Strategy:
            # 1. Check for overlapping (lvr_min, lvr_max) with different rates
            # 2. Look for differentiators (special_offer, package, profession, etc.)
            # 3. If found: split into separate products or add to state_parameters
            # 4. If NOT found: discard lower-quality data (keep most common/conservative)
            
            tier_groups = {}  # Group by (lvr_min, lvr_max)
            for i, tier in enumerate(state_data['rate_tiers']):
                tier_key = (tier['lvr_min'], tier['lvr_max'])
                if tier_key not in tier_groups:
                    tier_groups[tier_key] = []
                tier_groups[tier_key].append((i, tier))
            
            # Check for overlaps with different rates
            validated_tiers = []
            has_overlaps = False
            
            for tier_key, tiers_list in tier_groups.items():
                if len(tiers_list) == 1:
                    # No overlap, add directly
                    validated_tiers.append(tiers_list[0][1])
                else:
                    # Multiple tiers for same LVR band - check if rates differ
                    rates = [t[1]['interest_rate'] for t in tiers_list]
                    if len(set(rates)) == 1:
                        # Same rate, just deduplicate
                        validated_tiers.append(tiers_list[0][1])
                    else:
                        # CRITICAL: Different rates for same LVR band!
                        has_overlaps = True
                        
                        # Try to find differentiator in source components
                        # (This would require access to original components - for now, keep most conservative)
                        # TODO: In future, check component.applicability for 'special_offer', 'package', etc.
                        
                        # STRATEGY: Keep the HIGHEST rate (most conservative/common)
                        # This assumes base rate without discounts is the "true" rate
                        best_tier = max(tiers_list, key=lambda x: x[1]['interest_rate'])
                        validated_tiers.append(best_tier[1])
                        
                        # Log the issue for audit
                        rates_str = ", ".join([f"{t[1]['interest_rate']}%" for t in tiers_list])
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"LVR OVERLAP DETECTED in state {state_id}: "
                            f"LVR [{tier_key[0]:.2f}, {tier_key[1]:.2f}] has {len(tiers_list)} rates ({rates_str}). "
                            f"Kept highest rate {best_tier[1]['interest_rate']}%. "
                            f"This suggests missing state_parameter (e.g., special_offer, package)."
                        )
            
            # Apply strict penalty if overlaps found
            if has_overlaps:
                if 'confidence_score' in state_data['provenance']:
                    state_data['provenance']['confidence_score'] = max(
                        20,  # Floor at 20
                        state_data['provenance']['confidence_score'] - 40  # -40 penalty for overlaps
                    )
                state_data['provenance']['data_quality'] = 'degraded_lvr_overlaps'
            
            # Update with validated tiers (sorted)
            state_data['rate_tiers'] = sorted(
                validated_tiers,
                key=lambda x: (x['lvr_min'], x['lvr_max'])
            )
            
            # Build pricing object
            pricing_obj = {
                'rate_tiers': state_data['rate_tiers']
            }
            
            # Add interest-only period if applicable
            if state_data['state_parameters']['repayment_type'] == 'InterestOnly':
                pricing_obj['interest_only_period_years'] = 5  # Default
            
            pricing_state = {
                'state_id': state_id,
                'state_parameters': state_data['state_parameters'],
                'pricing': pricing_obj,
                'provenance': state_data['provenance']
            }
            
            pricing_states.append(pricing_state)
        
        # Sort pricing states for consistent output (OO before INV, PI before IO)
        pricing_states.sort(key=lambda x: (
            0 if 'OwnerOccupied' in x['state_parameters']['loan_type'] else 1,
            0 if 'PrincipalAndInterest' in x['state_parameters']['repayment_type'] else 1
        ))
        
        # FIX 4 UPGRADED: MATERIALIZE COMPLETE MATRIX (Closed-World Model)
        # Instead of just flagging missing states, we now MATERIALIZE them explicitly
        
        # Step 1: Inventory what we captured
        captured_states = set()
        for state in pricing_states:
            params = state['state_parameters']
            loan_type = params.get('loan_type', 'Unknown')
            repayment_type = params.get('repayment_type', 'Unknown')
            state_sig = f"{loan_type}_{repayment_type}"
            captured_states.add(state_sig)
        
        # Step 2: Define theoretical matrix (all expected combinations)
        # For Variable rate products: OO×PI, OO×IO, INV×PI, INV×IO = 4 states
        # For Fixed rate products: Same 4 states
        expected_states = [
            ('OwnerOccupied', 'PrincipalAndInterest'),
            ('OwnerOccupied', 'InterestOnly'),
            ('Investment', 'PrincipalAndInterest'),
            ('Investment', 'InterestOnly')
        ]
        
        # Step 3: Materialize missing states explicitly
        rate_type_normalized = (self.interest_components[0].rate_type if self.interest_components else "Variable").upper()[:3]
        
        for loan_type, repayment_type in expected_states:
            state_sig = f"{loan_type}_{repayment_type}"
            
            if state_sig not in captured_states:
                # Create EXPLICIT null-state entry
                purpose_abbrev = "OO" if loan_type == "OwnerOccupied" else "INV"
                repayment_abbrev = "PI" if repayment_type == "PrincipalAndInterest" else "IO"
                state_id = f"{purpose_abbrev}_{repayment_abbrev}_{rate_type_normalized}"
                
                # Create a null pricing state
                null_state = {
                    'state_id': state_id,
                    'state_parameters': {
                        'loan_type': loan_type,
                        'repayment_type': repayment_type
                    },
                    'pricing': None,  # Explicitly null - no pricing data
                    'provenance': {
                        'extraction_method': 'not_attempted',
                        'extraction_strategy': 'matrix_materialization',
                        'confidence_score': 0,
                        'capture_status': 'not_available',
                        'reason': 'State not found during UI exploration'
                    }
                }
                
                pricing_states.append(null_state)
        
        # Re-sort after adding materialized states
        pricing_states.sort(key=lambda x: (
            0 if 'OwnerOccupied' in x['state_parameters']['loan_type'] else 1,
            0 if 'PrincipalAndInterest' in x['state_parameters']['repayment_type'] else 1
        ))
        
        # Step 4: Calculate capture completeness for logging
        captured_count = len([s for s in pricing_states if s['pricing'] is not None])
        total_count = len(expected_states)
        is_partial_capture = captured_count < total_count
        missing_states = []
        
        # Identify which TYPES of states are missing (for legacy compatibility)
        captured_purposes = set()
        captured_repayment_types = set()
        
        for state in pricing_states:
            if state['pricing'] is not None:  # Only count states with actual pricing
                params = state['state_parameters']
                if 'loan_type' in params:
                    captured_purposes.add(params['loan_type'])
                if 'repayment_type' in params:
                    captured_repayment_types.add(params['repayment_type'])
        
        if 'OwnerOccupied' not in captured_purposes:
            missing_states.append('OwnerOccupied')
        if 'Investment' not in captured_purposes:
            missing_states.append('Investment')
        if 'PrincipalAndInterest' not in captured_repayment_types:
            missing_states.append('PrincipalAndInterest')
        if 'InterestOnly' not in captured_repayment_types:
            missing_states.append('InterestOnly')
        
        # Reduce confidence for ACTUAL captured states if capture is partial
        # (Don't penalize the materialized null states - they already have confidence=0)
        if is_partial_capture:
            for state in pricing_states:
                if state['pricing'] is not None and 'confidence_score' in state['provenance']:
                    # Apply surface penalty: -20 points for incomplete capture
                    original_confidence = state['provenance']['confidence_score']
                    state['provenance']['confidence_score'] = max(30, original_confidence - 20)
                    state['provenance']['capture_status'] = 'partial'
                    # Note: We don't add 'missing_states' here anymore since the matrix
                    # now explicitly shows which states are null
        
        # FIX 2 & 3: Canonical product ID using centralized slugify()
        # Use short_name or name as the source of truth for both ID and name
        canonical_product_name = self.short_name or self.name
        canonical_lender_name = self.lender
        
        # Generate canonical product_id: [lender]-[product-name]
        # Uses slugify() for consistent, alphanumeric-hyphenated format
        lender_slug = slugify(canonical_lender_name)
        product_slug = slugify(canonical_product_name)
        product_id_canonical = f"{lender_slug}-{product_slug}"
        
        # Build v2.0.0 structure
        return {
            "schema_version": "2.0.0",
            "product": {
                "product_id": product_id_canonical,
                "product_name": canonical_product_name,
                "lender": {
                    "lender_id": slugify(self.lender),  # FIX 3: Use centralized slugify
                    "lender_name": self.lender,
                    "jurisdiction": self.jurisdiction
                },
                "product_type": "HomeLoan",
                "rate_type": self.interest_components[0].rate_type if self.interest_components else "Variable",
                # FIX 5: Add fixed_term_years for Fixed products
                **({"fixed_term_years": self.interest_components[0].fixed_term_months // 12} 
                   if self.interest_components and 
                      self.interest_components[0].rate_type == "Fixed" and 
                      self.interest_components[0].fixed_term_months 
                   else {})
            },
            "features": {
                "offset_account": bool(self.features.offset_account),
                "redraw": bool(self.features.redraw),
                "package_eligible": bool(self.features.package)
            },
            "eligibility": {
                "min_loan_amount_aud": float(self.eligibility.min_loan_amount_aud),
                "max_loan_amount_aud": float(self.eligibility.max_loan_amount_aud) if self.eligibility.max_loan_amount_aud else None,
                "min_age_years": self.eligibility.min_age_years,
                "residency": self.eligibility.residency,
                "borrower_types": self.eligibility.borrower_types,
                "property_types_allowed": self.eligibility.property_types_allowed,
                "max_lvr_by_loan_type": self.eligibility.max_lvr_by_loan_type or {
                    "OwnerOccupied": 0.90,
                    "Investment": 0.90
                },
                # Include filter-based eligibility if present
                **({"product_segment": self.eligibility.product_segment} if self.eligibility.product_segment else {}),
                **({"region_restrictions": self.eligibility.region_restrictions} if self.eligibility.region_restrictions else {}),
                **({"borrower_category": self.eligibility.borrower_category} if self.eligibility.borrower_category else {})
            },
            "pricing_states": pricing_states,
            "governance": {
                "rates_effective_date": self.collected_at.strftime("%Y-%m-%d"),
                "source_url": self.source_url,
                "collected_at": self.collected_at.isoformat()
            }
        }


class ProductMatch(BaseModel):
    """Product match with scoring and explanation."""
    
    product: LoanProduct = Field(..., description="Matched product")
    score: int = Field(..., description="Match score 0-100", ge=0, le=100)
    monthly_payment: Decimal = Field(..., description="Calculated monthly payment")
    explanation: str = Field(..., description="Plain English explanation")
    trade_offs: List[str] = Field(default_factory=list, description="Trade-offs to consider")
