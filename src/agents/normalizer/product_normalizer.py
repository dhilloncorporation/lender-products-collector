"""
Normalizer Agent - Data Standardization

ROLE: Worker Agent (Data Transformation)
PURPOSE: Normalizes raw loan product data into standardized BIAN schema format

This agent transforms raw, unstructured product data from various sources into
a consistent, standardized format following the BIAN (Banking Industry
Architecture Network) schema. It handles parsing, validation, and mapping
of product attributes.

NORMALIZATION TASKS:
- Extract lender information
- Parse product names and descriptions
- Extract interest rates (comparison rate, variable, fixed)
- Parse loan terms and amounts
- Extract product features (offset, redraw, etc.)
- Parse fees and charges
- Extract eligibility criteria (LVR, DTI, postcode restrictions)
- Validate and standardize data formats

FEATURES:
- Pattern-based extraction (regex for rates, terms, etc.)
- Feature detection (offset accounts, redraw facilities)
- Rate type classification (Variable, Fixed, etc.)
- LVR extraction and validation
- Postcode restriction parsing
- Data validation and error handling

DEPENDENCIES:
- LoanProduct models (BIAN schema)
- Regular expressions for pattern matching

USAGE:
    normalizer = ProductNormalizerAgent()
    normalized = normalizer.normalize_products(raw_products)
    # Returns List[LoanProduct] in standardized format
"""

import logging
import re
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from ...models import LoanProduct

logger = logging.getLogger(__name__)


class ProductNormalizerAgent:
    """
    Product normalizer agent for standardizing loan product data.
    
    This agent transforms raw, unstructured product data into standardized
    BIAN schema-compliant LoanProduct objects. It handles parsing, extraction,
    and validation of product attributes.
    
    Normalization Process:
        1. Extract basic product information (name, description, lender)
        2. Parse interest rates (comparison rate, rate type)
        3. Extract loan terms and amounts
        4. Identify product features (offset, redraw, etc.)
        5. Parse fees and charges
        6. Extract eligibility criteria (LVR, DTI, postcode)
        7. Validate and standardize all data
    
    Attributes:
        normalization_rules: Dictionary of regex patterns and rules for extraction
    
    Example:
        >>> normalizer = ProductNormalizerAgent()
        >>> raw_data = [{"name": "Variable Home Loan", "rate": "5.99%"}]
        >>> normalized = normalizer.normalize_products(raw_data)
        >>> print(f"Normalized {len(normalized)} products")
    """
    
    def __init__(self):
        self.normalization_rules = {
            "rate_patterns": [
                r"(\d+\.?\d*)\s*%",
                r"(\d+\.?\d*)\s*per\s*cent",
                r"(\d+\.?\d*)\s*p\.a\.",
            ],
            "term_patterns": [
                r"(\d+)\s*years?",
                r"(\d+)\s*months?",
                r"(\d+)\s*yr",
            ],
            "feature_keywords": {
                "offset": ["offset", "offset account", "offset facility"],
                "redraw": ["redraw", "redraw facility", "redraw facility"],
                "cashback": ["cashback", "cash back", "bonus"],
                "package": ["package", "premium", "professional"],
            }
        }
    
    def normalize_products(self, raw_products: List[Dict[str, Any]]) -> List[LoanProduct]:
        """Normalize a list of raw products into standardized LoanProduct objects."""
        normalized_products = []
        
        for raw_product in raw_products:
            try:
                normalized = self.normalize_single_product(raw_product)
                if normalized:
                    normalized_products.append(normalized)
            except Exception as e:
                logger.error(f"Failed to normalize product: {str(e)}")
                continue
        
        logger.info(f"Normalized {len(normalized_products)} out of {len(raw_products)} products")
        return normalized_products
    
    def normalize_single_product(self, raw_product: Dict[str, Any]) -> Optional[LoanProduct]:
        """Normalize a single raw product into a LoanProduct object."""
        try:
            # Extract and validate required fields
            lender = self._extract_lender(raw_product)
            product_name = self._extract_product_name(raw_product)
            rate_percent = self._extract_rate(raw_product)
            comparison_rate = self._extract_comparison_rate(raw_product, rate_percent)
            term_months = self._extract_term_months(raw_product)
            rate_type = self._extract_rate_type(raw_product)
            features = self._extract_features(raw_product)
            fees = self._extract_fees(raw_product)
            lvr_max = self._extract_lvr_max(raw_product)
            dti_max = self._extract_dti_max(raw_product)
            postcode_flags = self._extract_postcode_flags(raw_product)
            source_url = raw_product.get("source_url", "")
            
            return LoanProduct(
                lender=lender,
                product_name=product_name,
                rate_percent=rate_percent,
                comparison_rate_percent=comparison_rate,
                term_months=term_months,
                rate_type=rate_type,
                fees_breakdown=fees,
                features=features,
                lvr_max=lvr_max,
                dti_max=dti_max,
                postcode_flags=postcode_flags,
                source_url=source_url,
                collected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to normalize product {raw_product.get('name', 'unknown')}: {str(e)}")
            return None
    
    def _extract_lender(self, raw_product: Dict[str, Any]) -> str:
        """Extract lender name from raw product data."""
        return raw_product.get("lender", "Unknown")
    
    def _extract_product_name(self, raw_product: Dict[str, Any]) -> str:
        """Extract product name from raw product data."""
        name = raw_product.get("name", raw_product.get("product_name", "Unknown Product"))
        # Clean up the name
        name = re.sub(r'\s+', ' ', name.strip())
        return name
    
    def _extract_rate(self, raw_product: Dict[str, Any]) -> Decimal:
        """Extract interest rate from raw product data."""
        rate_text = raw_product.get("rate_line", raw_product.get("rate", ""))
        
        for pattern in self.normalization_rules["rate_patterns"]:
            match = re.search(pattern, rate_text, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1))
                except:
                    continue
        
        # Fallback to default rate
        logger.warning(f"Could not extract rate from: {rate_text}")
        return Decimal("6.5")
    
    def _extract_comparison_rate(self, raw_product: Dict[str, Any], base_rate: Decimal) -> Decimal:
        """Extract comparison rate, fallback to base_rate + 0.3 if not found."""
        comparison_text = raw_product.get("comparison_rate", "")
        
        for pattern in self.normalization_rules["rate_patterns"]:
            match = re.search(pattern, comparison_text, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1))
                except:
                    continue
        
        # Fallback to base rate + 0.3
        return base_rate + Decimal("0.3")
    
    def _extract_term_months(self, raw_product: Dict[str, Any]) -> int:
        """Extract loan term in months from raw product data."""
        term_text = raw_product.get("term", raw_product.get("term_line", ""))
        
        for pattern in self.normalization_rules["term_patterns"]:
            match = re.search(pattern, term_text, re.IGNORECASE)
            if match:
                try:
                    term_value = int(match.group(1))
                    # Convert years to months if needed
                    if "year" in term_text.lower():
                        return term_value * 12
                    return term_value
                except:
                    continue
        
        # Default to 30 years (360 months)
        return 360
    
    def _extract_rate_type(self, raw_product: Dict[str, Any]) -> str:
        """Extract rate type from raw product data."""
        text = raw_product.get("rate_type", raw_product.get("name", "")).lower()
        
        if "fixed" in text:
            return "fixed"
        elif "variable" in text:
            return "variable"
        elif "split" in text:
            return "split"
        else:
            return "variable"  # Default
    
    def _extract_features(self, raw_product: Dict[str, Any]) -> List[str]:
        """Extract product features from raw product data."""
        features = []
        text = " ".join([
            raw_product.get("name", ""),
            raw_product.get("description", ""),
            " ".join(raw_product.get("features", []))
        ]).lower()
        
        for feature, keywords in self.normalization_rules["feature_keywords"].items():
            if any(keyword in text for keyword in keywords):
                features.append(feature)
        
        return features
    
    def _extract_fees(self, raw_product: Dict[str, Any]) -> Dict[str, int]:
        """Extract fee breakdown from raw product data."""
        fees = raw_product.get("fees_breakdown", {})
        
        # Ensure numeric values
        normalized_fees = {}
        for key, value in fees.items():
            try:
                normalized_fees[key] = int(float(value))
            except:
                normalized_fees[key] = 0
        
        # Add default fees if not present
        if "application" not in normalized_fees:
            normalized_fees["application"] = 0
        if "ongoing" not in normalized_fees:
            normalized_fees["ongoing"] = 0
        
        return normalized_fees
    
    def _extract_lvr_max(self, raw_product: Dict[str, Any]) -> Decimal:
        """Extract maximum LVR from raw product data."""
        lvr_text = raw_product.get("lvr_max", raw_product.get("lvr", ""))
        
        if lvr_text:
            match = re.search(r"(\d+\.?\d*)", str(lvr_text))
            if match:
                try:
                    return Decimal(match.group(1))
                except:
                    pass
        
        # Default to 95%
        return Decimal("95")
    
    def _extract_dti_max(self, raw_product: Dict[str, Any]) -> Optional[Decimal]:
        """Extract maximum DTI from raw product data."""
        dti_text = raw_product.get("dti_max", raw_product.get("dti", ""))
        
        if dti_text:
            match = re.search(r"(\d+\.?\d*)", str(dti_text))
            if match:
                try:
                    return Decimal(match.group(1))
                except:
                    pass
        
        return None
    
    def _extract_postcode_flags(self, raw_product: Dict[str, Any]) -> List[str]:
        """Extract postcode restrictions from raw product data."""
        flags = raw_product.get("postcode_flags", [])
        if isinstance(flags, list):
            return flags
        elif isinstance(flags, str):
            return [flags]
        else:
            return []
