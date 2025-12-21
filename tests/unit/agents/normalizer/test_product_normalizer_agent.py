"""Test cases for ProductNormalizerAgent."""

import pytest
import re
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch

from src.agents.normalizer.product_normalizer import ProductNormalizerAgent
from src.models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria


class TestProductNormalizerAgent:
    """Test cases for ProductNormalizerAgent."""

    @pytest.fixture
    def normalizer(self):
        """Create ProductNormalizerAgent instance."""
        return ProductNormalizerAgent()

    @pytest.fixture
    def sample_raw_product(self):
        """Sample raw product data for testing."""
        return {
            "lender": "ANZ",
            "name": "ANZ Standard Variable Home Loan",
            "rate_line": "6.49% p.a",
            "comparison_rate": "6.79%",
            "term": "30 years",
            "rate_type": "variable",
            "description": "Standard variable home loan with offset account",
            "features": ["offset account", "redraw facility"],
            "fees_breakdown": {
                "application": 600,
                "ongoing": 0,
                "valuation": 330
            },
            "lvr_max": "95%",
            "dti_max": "6.0",
            "postcode_flags": ["metro", "regional"],
            "source_url": "https://anz.com.au/home-loans"
        }

    def test_init(self, normalizer):
        """Test normalizer initialization."""
        assert "rate_patterns" in normalizer.normalization_rules
        assert "term_patterns" in normalizer.normalization_rules
        assert "feature_keywords" in normalizer.normalization_rules
        
        # Check rate patterns
        assert len(normalizer.normalization_rules["rate_patterns"]) == 3
        assert r"(\d+\.?\d*)\s*%" in normalizer.normalization_rules["rate_patterns"]
        
        # Check feature keywords
        assert "offset" in normalizer.normalization_rules["feature_keywords"]
        assert "redraw" in normalizer.normalization_rules["feature_keywords"]

    def test_normalize_products_success(self, normalizer, sample_raw_product):
        """Test successful normalization of multiple products."""
        raw_products = [sample_raw_product, sample_raw_product.copy()]
        raw_products[1]["name"] = "ANZ Fixed Rate Home Loan"
        raw_products[1]["rate_line"] = "5.99% p.a"
        
        normalized = normalizer.normalize_products(raw_products)
        
        assert len(normalized) == 2
        assert all(isinstance(p, LoanProduct) for p in normalized)
        assert normalized[0].name == "ANZ Standard Variable Home Loan"
        assert normalized[1].name == "ANZ Fixed Rate Home Loan"

    def test_normalize_products_with_errors(self, normalizer):
        """Test normalization with some products failing."""
        raw_products = [
            {"lender": "ANZ", "name": "Valid Product", "rate_line": "6.5%"},
            {"lender": "CBA"},  # Missing required fields
            {"lender": "NAB", "name": "Another Valid", "rate_line": "6.0%"}
        ]
        
        normalized = normalizer.normalize_products(raw_products)
        
        # Should normalize 2 out of 3 products
        assert len(normalized) == 2
        assert normalized[0].name == "Valid Product"
        assert normalized[1].name == "Another Valid"

    def test_normalize_single_product_success(self, normalizer, sample_raw_product):
        """Test successful single product normalization."""
        normalized = normalizer.normalize_single_product(sample_raw_product)
        
        assert normalized is not None
        assert isinstance(normalized, LoanProduct)
        assert normalized.lender == "ANZ"
        assert normalized.name == "ANZ Standard Variable Home Loan"
        assert normalized.interest_components[0].comparison_rate_pct_au == Decimal("6.49")
        assert normalized.interest_components[0].rate_type == "Variable"

    def test_normalize_single_product_failure(self, normalizer):
        """Test single product normalization failure."""
        invalid_product = {"invalid": "data"}
        
        normalized = normalizer.normalize_single_product(invalid_product)
        
        assert normalized is None

    def test_extract_lender(self, normalizer):
        """Test lender extraction."""
        # Valid lender
        assert normalizer._extract_lender({"lender": "ANZ"}) == "ANZ"
        
        # Missing lender
        assert normalizer._extract_lender({}) == "Unknown"

    def test_extract_product_name(self, normalizer):
        """Test product name extraction."""
        # From 'name' field
        assert normalizer._extract_product_name({"name": "Test Product"}) == "Test Product"
        
        # From 'product_name' field
        assert normalizer._extract_product_name({"product_name": "Test Product"}) == "Test Product"
        
        # Clean up whitespace
        assert normalizer._extract_product_name({"name": "  Test   Product  "}) == "Test Product"
        
        # Missing name
        assert normalizer._extract_product_name({}) == "Unknown Product"

    def test_extract_rate_success(self, normalizer):
        """Test successful rate extraction."""
        # Standard percentage format
        assert normalizer._extract_rate({"rate_line": "6.49%"}) == Decimal("6.49")
        
        # With p.a.
        assert normalizer._extract_rate({"rate_line": "6.49% p.a"}) == Decimal("6.49")
        
        # From 'rate' field
        assert normalizer._extract_rate({"rate": "6.5%"}) == Decimal("6.5")
        
        # Per cent format
        assert normalizer._extract_rate({"rate_line": "6.49 per cent"}) == Decimal("6.49")

    def test_extract_rate_failure(self, normalizer):
        """Test rate extraction failure."""
        # Invalid rate text
        assert normalizer._extract_rate({"rate_line": "invalid rate"}) == Decimal("6.5")
        
        # Missing rate
        assert normalizer._extract_rate({}) == Decimal("6.5")

    def test_extract_comparison_rate_success(self, normalizer):
        """Test successful comparison rate extraction."""
        base_rate = Decimal("6.5")
        
        # Valid comparison rate
        assert normalizer._extract_comparison_rate({"comparison_rate": "6.8%"}, base_rate) == Decimal("6.8")
        
        # Missing comparison rate - should fallback to base + 0.3
        assert normalizer._extract_comparison_rate({}, base_rate) == Decimal("6.8")

    def test_extract_term_months_success(self, normalizer):
        """Test successful term extraction."""
        # Years format
        assert normalizer._extract_term_months({"term": "30 years"}) == 360
        assert normalizer._extract_term_months({"term": "2 years"}) == 24
        
        # Months format
        assert normalizer._extract_term_months({"term": "24 months"}) == 24
        
        # From 'term_line' field
        assert normalizer._extract_term_months({"term_line": "25 years"}) == 300

    def test_extract_term_months_failure(self, normalizer):
        """Test term extraction failure."""
        # Invalid term
        assert normalizer._extract_term_months({"term": "invalid"}) == 360
        
        # Missing term
        assert normalizer._extract_term_months({}) == 360

    def test_extract_rate_type(self, normalizer):
        """Test rate type extraction."""
        # Fixed rate
        assert normalizer._extract_rate_type({"rate_type": "fixed"}) == "fixed"
        assert normalizer._extract_rate_type({"name": "Fixed Rate Loan"}) == "fixed"
        
        # Variable rate
        assert normalizer._extract_rate_type({"rate_type": "variable"}) == "variable"
        assert normalizer._extract_rate_type({"name": "Variable Rate Loan"}) == "variable"
        
        # Split rate
        assert normalizer._extract_rate_type({"rate_type": "split"}) == "split"
        
        # Default to variable
        assert normalizer._extract_rate_type({}) == "variable"

    def test_extract_features_success(self, normalizer):
        """Test feature extraction."""
        product_data = {
            "name": "Home Loan with Offset Account",
            "description": "Includes redraw facility",
            "features": ["cashback offer", "premium package"]
        }
        
        features = normalizer._extract_features(product_data)
        
        assert "offset" in features
        assert "redraw" in features
        assert "cashback" in features
        assert "package" in features

    def test_extract_features_no_features(self, normalizer):
        """Test feature extraction with no features."""
        product_data = {"name": "Basic Home Loan"}
        
        features = normalizer._extract_features(product_data)
        
        assert features == []

    def test_extract_fees_success(self, normalizer):
        """Test fee extraction."""
        product_data = {
            "fees_breakdown": {
                "application": 600,
                "ongoing": 0,
                "valuation": 330
            }
        }
        
        fees = normalizer._extract_fees(product_data)
        
        assert fees["application"] == 600
        assert fees["ongoing"] == 0
        assert fees["valuation"] == 330

    def test_extract_fees_with_defaults(self, normalizer):
        """Test fee extraction with defaults."""
        product_data = {"fees_breakdown": {}}
        
        fees = normalizer._extract_fees(product_data)
        
        assert fees["application"] == 0
        assert fees["ongoing"] == 0

    def test_extract_fees_invalid_values(self, normalizer):
        """Test fee extraction with invalid values."""
        product_data = {
            "fees_breakdown": {
                "application": "invalid",
                "ongoing": "not_a_number"
            }
        }
        
        fees = normalizer._extract_fees(product_data)
        
        assert fees["application"] == 0
        assert fees["ongoing"] == 0

    def test_extract_lvr_max_success(self, normalizer):
        """Test LVR extraction."""
        # Valid LVR
        assert normalizer._extract_lvr_max({"lvr_max": "95%"}) == Decimal("95")
        assert normalizer._extract_lvr_max({"lvr": "80%"}) == Decimal("80")
        assert normalizer._extract_lvr_max({"lvr_max": "90.5"}) == Decimal("90.5")

    def test_extract_lvr_max_failure(self, normalizer):
        """Test LVR extraction failure."""
        # Invalid LVR
        assert normalizer._extract_lvr_max({"lvr_max": "invalid"}) == Decimal("95")
        
        # Missing LVR
        assert normalizer._extract_lvr_max({}) == Decimal("95")

    def test_extract_dti_max_success(self, normalizer):
        """Test DTI extraction."""
        # Valid DTI
        assert normalizer._extract_dti_max({"dti_max": "6.0"}) == Decimal("6.0")
        assert normalizer._extract_dti_max({"dti": "5.5"}) == Decimal("5.5")

    def test_extract_dti_max_failure(self, normalizer):
        """Test DTI extraction failure."""
        # Invalid DTI
        assert normalizer._extract_dti_max({"dti_max": "invalid"}) is None
        
        # Missing DTI
        assert normalizer._extract_dti_max({}) is None

    def test_extract_postcode_flags_success(self, normalizer):
        """Test postcode flags extraction."""
        # List format
        assert normalizer._extract_postcode_flags({"postcode_flags": ["metro", "regional"]}) == ["metro", "regional"]
        
        # String format
        assert normalizer._extract_postcode_flags({"postcode_flags": "metro"}) == ["metro"]
        
        # Invalid format
        assert normalizer._extract_postcode_flags({"postcode_flags": 123}) == []

    def test_normalize_products_with_logging(self, normalizer, sample_raw_product, caplog):
        """Test normalization with logging."""
        raw_products = [sample_raw_product]
        
        with caplog.at_level("INFO"):
            normalized = normalizer.normalize_products(raw_products)
        
        assert len(normalized) == 1
        assert "Normalized 1 out of 1 products" in caplog.text

    def test_normalize_single_product_with_logging(self, normalizer, caplog):
        """Test single product normalization with error logging."""
        invalid_product = {"invalid": "data"}
        
        with caplog.at_level("ERROR"):
            normalized = normalizer.normalize_single_product(invalid_product)
        
        assert normalized is None
        assert "Failed to normalize product" in caplog.text

    def test_rate_patterns_comprehensive(self, normalizer):
        """Test all rate patterns comprehensively."""
        test_cases = [
            ("6.49%", Decimal("6.49")),
            ("6.49 %", Decimal("6.49")),
            ("6.49% p.a", Decimal("6.49")),
            ("6.49 per cent", Decimal("6.49")),
            ("6.49 per cent p.a", Decimal("6.49")),
            ("6.49% p.a.", Decimal("6.49")),
        ]
        
        for rate_text, expected in test_cases:
            result = normalizer._extract_rate({"rate_line": rate_text})
            assert result == expected, f"Failed for '{rate_text}': expected {expected}, got {result}"

    def test_term_patterns_comprehensive(self, normalizer):
        """Test all term patterns comprehensively."""
        test_cases = [
            ("30 years", 360),
            ("2 years", 24),
            ("24 months", 24),
            ("12 months", 12),
            ("30 yr", 360),
            ("2 yr", 24),
        ]
        
        for term_text, expected in test_cases:
            result = normalizer._extract_term_months({"term": term_text})
            assert result == expected, f"Failed for '{term_text}': expected {expected}, got {result}"

    def test_feature_keywords_comprehensive(self, normalizer):
        """Test all feature keywords comprehensively."""
        test_cases = [
            ("offset account", ["offset"]),
            ("redraw facility", ["redraw"]),
            ("cashback offer", ["cashback"]),
            ("premium package", ["package"]),
            ("offset account and redraw facility", ["offset", "redraw"]),
            ("cashback and premium package", ["cashback", "package"]),
        ]
        
        for description, expected_features in test_cases:
            product_data = {"name": description, "description": "", "features": []}
            result = normalizer._extract_features(product_data)
            
            for expected_feature in expected_features:
                assert expected_feature in result, f"Failed for '{description}': expected {expected_feature} in {result}"

    def test_normalize_with_minimal_data(self, normalizer):
        """Test normalization with minimal required data."""
        minimal_product = {
            "lender": "TEST",
            "name": "Test Product",
            "rate_line": "6.5%"
        }
        
        normalized = normalizer.normalize_single_product(minimal_product)
        
        assert normalized is not None
        assert normalized.lender == "TEST"
        assert normalized.name == "Test Product"
        assert normalized.interest_components[0].comparison_rate_pct_au == Decimal("6.5")
        assert normalized.interest_components[0].rate_type == "Variable"
        assert normalized.eligibility.max_lvr_by_segment[0]["maxLVR"] == Decimal("0.95")

    def test_normalize_with_complex_data(self, normalizer):
        """Test normalization with complex product data."""
        complex_product = {
            "lender": "ANZ",
            "name": "ANZ Premium Package Home Loan with Offset Account",
            "rate_line": "6.49% p.a",
            "comparison_rate": "6.79%",
            "term": "30 years",
            "rate_type": "variable",
            "description": "Premium package with offset account, redraw facility, and cashback offer",
            "features": ["offset account", "redraw facility", "cashback", "premium package"],
            "fees_breakdown": {
                "application": 600,
                "ongoing": 395,
                "valuation": 330,
                "settlement": 200
            },
            "lvr_max": "95%",
            "dti_max": "6.0",
            "postcode_flags": ["metro", "regional", "remote"],
            "source_url": "https://anz.com.au/premium-loans"
        }
        
        normalized = normalizer.normalize_single_product(complex_product)
        
        assert normalized is not None
        assert normalized.lender == "ANZ"
        assert normalized.name == "ANZ Premium Package Home Loan with Offset Account"
        assert normalized.interest_components[0].comparison_rate_pct_au == Decimal("6.49")
        assert normalized.interest_components[0].rate_type == "Variable"
        assert normalized.amortization_term_months == 360
        
        # Check features
        features_text = " ".join([normalized.name, normalized.description]).lower()
        assert "offset" in features_text or "offset" in normalized.features.offset_account
        assert "redraw" in features_text or "redraw" in normalized.features.redraw
        
        # Check fees
        assert len(normalized.fees.upfront) > 0
        assert len(normalized.fees.ongoing) > 0
        
        # Check eligibility
        assert normalized.eligibility.max_lvr_by_segment[0]["maxLVR"] == Decimal("0.95")
        assert normalized.source_url == "https://anz.com.au/premium-loans"

