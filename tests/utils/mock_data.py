"""Mock data for testing purposes."""

from src.models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria


def get_mock_products():
    """Get mock loan products for testing."""
    return [
        LoanProduct(
            product_id="anz-fixed-001",
            version="1.0",
            status="active",
            name="ANZ Fixed Rate Home Loan",
            short_name="ANZ Fixed",
            description="Fixed rate home loan with competitive rates",
            purpose="Owner Occupied",
            channels=["branch", "online", "mobile"],
            interest_components=[
                InterestComponent(
                    name="Fixed Rate",
                    rate_type="Fixed",
                    fixed_term_months=24,
                    comparison_rate_pct_au=6.71,
                    applicability={"min_loan_amount": 100000}
                )
            ],
            fees=FeeStructure(
                upfront=[{"name": "Application Fee", "amount": 600, "currency": "AUD"}],
                ongoing=[],
                event_driven=[]
            ),
            features=ProductFeatures(
                offset_account={"available": True, "fee": 0},
                redraw={"available": True, "fee": 0},
                extra_repayments={"allowed": True, "fee": 0}
            ),
            eligibility=EligibilityCriteria(
                min_loan_amount_aud=100000,
                max_loan_amount_aud=2000000,
                min_age_years=18,
                residency=["Australian Citizen", "Permanent Resident"],
                borrower_types=["Individual"],
                occupancy=["Owner Occupied"],
                max_lvr_by_segment=[{"segment": "Owner Occupied", "maxLVR": 0.95}],
                property_types_allowed=["House", "Apartment", "Townhouse"]
            ),
            lender="ANZ",
            source_url="https://www.anz.com.au/personal/home-loans/",
        ),
        LoanProduct(
            product_id="cba-variable-001", 
            version="1.0",
            status="active",
            name="CommBank Variable Home Loan",
            short_name="CBA Variable",
            description="Variable rate home loan with flexible features",
            purpose="Owner Occupied",
            channels=["branch", "online", "mobile"],
            interest_components=[
                InterestComponent(
                    name="Variable Rate",
                    rate_type="Variable",
                    comparison_rate_pct_au=7.05,
                    margin_pct=2.5,
                    applicability={"min_loan_amount": 100000}
                )
            ],
            fees=FeeStructure(
                upfront=[],
                ongoing=[{"name": "Monthly Fee", "amount": 10, "currency": "AUD"}],
                event_driven=[]
            ),
            features=ProductFeatures(
                offset_account={"available": True, "fee": 0},
                redraw={"available": True, "fee": 0},
                extra_repayments={"allowed": True, "fee": 0},
                package={"available": True, "name": "Complete Home Loan Package"}
            ),
            eligibility=EligibilityCriteria(
                min_loan_amount_aud=100000,
                max_loan_amount_aud=2000000,
                min_age_years=18,
                residency=["Australian Citizen", "Permanent Resident"],
                borrower_types=["Individual"],
                occupancy=["Owner Occupied"],
                max_lvr_by_segment=[{"segment": "Owner Occupied", "maxLVR": 0.95}],
                property_types_allowed=["House", "Apartment", "Townhouse"]
            ),
            lender="CBA",
            source_url="https://www.commbank.com.au/personal/home-loans/",
        ),
    ]
