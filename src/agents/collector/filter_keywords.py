"""
Filter Detection Keywords Configuration (Hybrid Approach)

Centralized keyword definitions loaded from YAML for easy updates.
Helper methods in Python for complex matching logic.

Keywords are organized by category in YAML for easy maintenance.
Matching logic stays in Python for type safety and performance.
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class FilterType(Enum):
    """Filter type enumeration."""
    LOAN_TYPE = "loan_type"
    REPAYMENT_TYPE = "repayment_type"
    LVR_TIER = "lvr_tier"
    LOAN_TERM = "loan_term"
    UNKNOWN = "unknown"


class FilterKeywords:
    """
    Hybrid keyword configuration: YAML for data, Python for logic.
    
    Keywords are loaded from YAML file for easy updates.
    Helper methods provide type-safe matching logic.
    """
    
    _instance: Optional['FilterKeywords'] = None
    _keywords: Dict = {}
    
    def __new__(cls):
        """Singleton pattern - load YAML once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_keywords()
        return cls._instance
    
    def _load_keywords(self):
        """Load keywords from YAML configuration file."""
        try:
            # Find config file (relative to project root)
            config_path = Path(__file__).parent.parent.parent / "configs" / "filter_keywords.yaml"
            
            if not config_path.exists():
                # Fallback: try relative to current file
                config_path = Path(__file__).parent.parent / "configs" / "filter_keywords.yaml"
            
            if not config_path.exists():
                logger.warning(f"Filter keywords YAML not found at {config_path}, using defaults")
                self._keywords = self._get_default_keywords()
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self._keywords = yaml.safe_load(f)
            
            logger.debug(f"Loaded filter keywords from {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load filter keywords YAML: {e}, using defaults")
            self._keywords = self._get_default_keywords()
    
    def _get_default_keywords(self) -> Dict:
        """Fallback default keywords if YAML loading fails."""
        return {
            "loan_type": {
                "phrases": ["home to live", "owner occup", "investment property"],
                "patterns": ["home", "investment", "owner"],
                "exclusions": ["home loan rates", "institutional"],
                "label_keywords": ["loan type", "loan purpose"],
                "max_words": 4
            },
            "repayment_type": {
                "phrases": ["principal & interest", "interest only"],
                "patterns": ["principal", "interest", "p&i"],
                "exclusions": ["institutional", "additional charges"],
                "label_keywords": ["repayment type"],
                "max_words": 5
            },
            "lvr_tier": {
                "keywords": ["lvr", "loan to value", "ltv"]
            },
            "loan_term": {
                "keywords": ["term", "fixed", "year", "month"]
            }
        }
    
    # ============================================================================
    # PROPERTY ACCESSORS (for backward compatibility)
    # ============================================================================
    
    @property
    def LOAN_TYPE_PHRASES(self) -> List[str]:
        """Get loan type phrases from YAML."""
        return self._keywords.get("loan_type", {}).get("phrases", [])
    
    @property
    def LOAN_TYPE_PATTERNS(self) -> List[str]:
        """Get loan type patterns from YAML."""
        return self._keywords.get("loan_type", {}).get("patterns", [])
    
    @property
    def LOAN_TYPE_EXCLUSIONS(self) -> List[str]:
        """Get loan type exclusions from YAML."""
        return self._keywords.get("loan_type", {}).get("exclusions", [])
    
    @property
    def LOAN_TYPE_LABEL_KEYWORDS(self) -> List[str]:
        """Get loan type label keywords from YAML."""
        return self._keywords.get("loan_type", {}).get("label_keywords", [])
    
    @property
    def REPAYMENT_TYPE_PHRASES(self) -> List[str]:
        """Get repayment type phrases from YAML."""
        return self._keywords.get("repayment_type", {}).get("phrases", [])
    
    @property
    def REPAYMENT_TYPE_PATTERNS(self) -> List[str]:
        """Get repayment type patterns from YAML."""
        return self._keywords.get("repayment_type", {}).get("patterns", [])
    
    @property
    def REPAYMENT_TYPE_EXCLUSIONS(self) -> List[str]:
        """Get repayment type exclusions from YAML."""
        return self._keywords.get("repayment_type", {}).get("exclusions", [])
    
    @property
    def REPAYMENT_TYPE_LABEL_KEYWORDS(self) -> List[str]:
        """Get repayment type label keywords from YAML."""
        return self._keywords.get("repayment_type", {}).get("label_keywords", [])
    
    @property
    def LVR_KEYWORDS(self) -> List[str]:
        """Get LVR tier keywords from YAML."""
        return self._keywords.get("lvr_tier", {}).get("keywords", [])
    
    @property
    def LOAN_TERM_KEYWORDS(self) -> List[str]:
        """Get loan term keywords from YAML."""
        return self._keywords.get("loan_term", {}).get("keywords", [])
    
    # ============================================================================
    # NEW FILTER TYPES - Property Accessors
    # ============================================================================
    
    @property
    def RATE_TYPE_PHRASES(self) -> List[str]:
        """Get rate type phrases from YAML."""
        return self._keywords.get("rate_type", {}).get("phrases", [])
    
    @property
    def RATE_TYPE_PATTERNS(self) -> List[str]:
        """Get rate type patterns from YAML."""
        return self._keywords.get("rate_type", {}).get("patterns", [])
    
    @property
    def RATE_TYPE_LABEL_KEYWORDS(self) -> List[str]:
        """Get rate type label keywords from YAML."""
        return self._keywords.get("rate_type", {}).get("label_keywords", [])
    
    @property
    def LOAN_PURPOSE_PHRASES(self) -> List[str]:
        """Get loan purpose phrases from YAML."""
        return self._keywords.get("loan_purpose", {}).get("phrases", [])
    
    @property
    def LOAN_PURPOSE_PATTERNS(self) -> List[str]:
        """Get loan purpose patterns from YAML."""
        return self._keywords.get("loan_purpose", {}).get("patterns", [])
    
    @property
    def LOAN_PURPOSE_LABEL_KEYWORDS(self) -> List[str]:
        """Get loan purpose label keywords from YAML."""
        return self._keywords.get("loan_purpose", {}).get("label_keywords", [])
    
    @property
    def PRODUCT_SEGMENT_PHRASES(self) -> List[str]:
        """Get product segment phrases from YAML."""
        return self._keywords.get("product_segment", {}).get("phrases", [])
    
    @property
    def PRODUCT_SEGMENT_PATTERNS(self) -> List[str]:
        """Get product segment patterns from YAML."""
        return self._keywords.get("product_segment", {}).get("patterns", [])
    
    @property
    def PRODUCT_SEGMENT_LABEL_KEYWORDS(self) -> List[str]:
        """Get product segment label keywords from YAML."""
        return self._keywords.get("product_segment", {}).get("label_keywords", [])
    
    @property
    def REGION_RESIDENCY_PHRASES(self) -> List[str]:
        """Get region/residency phrases from YAML."""
        return self._keywords.get("region_residency", {}).get("phrases", [])
    
    @property
    def REGION_RESIDENCY_PATTERNS(self) -> List[str]:
        """Get region/residency patterns from YAML."""
        return self._keywords.get("region_residency", {}).get("patterns", [])
    
    @property
    def REGION_RESIDENCY_LABEL_KEYWORDS(self) -> List[str]:
        """Get region/residency label keywords from YAML."""
        return self._keywords.get("region_residency", {}).get("label_keywords", [])
    
    @property
    def RATE_TIER_PHRASES(self) -> List[str]:
        """Get rate tier phrases from YAML."""
        return self._keywords.get("rate_tier", {}).get("phrases", [])
    
    @property
    def RATE_TIER_PATTERNS(self) -> List[str]:
        """Get rate tier patterns from YAML."""
        return self._keywords.get("rate_tier", {}).get("patterns", [])
    
    @property
    def RATE_TIER_LABEL_KEYWORDS(self) -> List[str]:
        """Get rate tier label keywords from YAML."""
        return self._keywords.get("rate_tier", {}).get("label_keywords", [])
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    @classmethod
    def get_loan_type_keywords(cls) -> Dict[str, List[str]]:
        """Get all loan type keywords organized by category."""
        return {
            "phrases": cls.LOAN_TYPE_PHRASES,
            "patterns": cls.LOAN_TYPE_PATTERNS,
            "exclusions": cls.LOAN_TYPE_EXCLUSIONS,
            "labels": cls.LOAN_TYPE_LABEL_KEYWORDS,
        }
    
    @classmethod
    def get_repayment_type_keywords(cls) -> Dict[str, List[str]]:
        """Get all repayment type keywords organized by category."""
        return {
            "phrases": cls.REPAYMENT_TYPE_PHRASES,
            "patterns": cls.REPAYMENT_TYPE_PATTERNS,
            "exclusions": cls.REPAYMENT_TYPE_EXCLUSIONS,
            "labels": cls.REPAYMENT_TYPE_LABEL_KEYWORDS,
        }
    
    # ============================================================================
    # UI INTERACTION KEYWORDS (externalized button/input patterns)
    # ============================================================================
    
    @property
    def SHOW_MORE_PATTERNS(self) -> List[str]:
        """Get 'Show More' button patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("show_more_patterns", [])
    
    @property
    def RESET_PATTERNS(self) -> List[str]:
        """Get 'Reset Filters' button patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("reset_patterns", [])
    
    @property
    def NUMERIC_INPUT_FIELDS(self) -> List[Dict[str, Any]]:
        """Get numeric input field definitions from YAML."""
        return self._keywords.get("ui_interactions", {}).get("numeric_input_fields", [])
    
    @property
    def CALCULATOR_INDICATORS(self) -> List[str]:
        """Get calculator widget indicator patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("calculator_indicators", [])
    
    @property
    def ELIGIBILITY_CHECKER_INDICATORS(self) -> List[str]:
        """Get eligibility checker widget indicator patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("eligibility_checker_indicators", [])
    
    @property
    def COMPARISON_TOOL_INDICATORS(self) -> List[str]:
        """Get comparison tool widget indicator patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("comparison_tool_indicators", [])
    
    @property
    def SIMULATOR_INDICATORS(self) -> List[str]:
        """Get interactive simulator widget indicator patterns from YAML."""
        return self._keywords.get("ui_interactions", {}).get("simulator_indicators", [])
    
    # ============================================================================
    # HELPER METHODS (Logic stays in Python)
    # ============================================================================
    
    def matches_loan_type(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches loan type patterns.
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches loan type patterns
        """
        if max_words is None:
            max_words = self._keywords.get("loan_type", {}).get("max_words", 4)
        
        text_lower = text.lower().strip()
        
        # Check exclusions first
        if any(exclude in text_lower for exclude in self.LOAN_TYPE_EXCLUSIONS):
            return False
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.LOAN_TYPE_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase for filter options)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.LOAN_TYPE_PATTERNS):
                # Exclude if it's clearly a repayment type
                repayment_patterns = self.REPAYMENT_TYPE_PATTERNS + ["principal", "interest only", "p&i", "p and i", "repayment"]
                if any(term in text_lower for term in repayment_patterns):
                    return False
                return True
        
        return False
    
    def matches_repayment_type(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches repayment type patterns.
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches repayment type patterns
        """
        if max_words is None:
            max_words = self._keywords.get("repayment_type", {}).get("max_words", 5)
        
        text_lower = text.lower().strip()
        
        # Check exclusions first
        if any(exclude in text_lower for exclude in self.REPAYMENT_TYPE_EXCLUSIONS):
            return False
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.REPAYMENT_TYPE_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if (('principal' in text_lower and 'interest' in text_lower) or
                any(pattern in text_lower for pattern in self.REPAYMENT_TYPE_PATTERNS)):
                return True
        
        return False
    
    def matches_lvr_tier(self, text: str) -> bool:
        """Check if text matches LVR tier patterns."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.LVR_KEYWORDS)
    
    def matches_loan_term(self, text: str) -> bool:
        """Check if text matches loan term patterns."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.LOAN_TERM_KEYWORDS)
    
    def matches_rate_type(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches rate type patterns (Fixed, Variable, etc.).
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches rate type patterns
        """
        if max_words is None:
            max_words = self._keywords.get("rate_type", {}).get("max_words", 3)
        
        text_lower = text.lower().strip()
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.RATE_TYPE_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.RATE_TYPE_PATTERNS):
                return True
        
        return False
    
    def matches_loan_purpose(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches loan purpose patterns (First Home Buyer, Construction, etc.).
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches loan purpose patterns
        """
        if max_words is None:
            max_words = self._keywords.get("loan_purpose", {}).get("max_words", 4)
        
        text_lower = text.lower().strip()
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.LOAN_PURPOSE_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.LOAN_PURPOSE_PATTERNS):
                return True
        
        return False
    
    def matches_product_segment(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches product segment patterns (Package, Offset, etc.).
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches product segment patterns
        """
        if max_words is None:
            max_words = self._keywords.get("product_segment", {}).get("max_words", 3)
        
        text_lower = text.lower().strip()
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.PRODUCT_SEGMENT_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.PRODUCT_SEGMENT_PATTERNS):
                return True
        
        return False
    
    def matches_region_residency(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches region/residency patterns (State, Resident, etc.).
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches region/residency patterns
        """
        if max_words is None:
            max_words = self._keywords.get("region_residency", {}).get("max_words", 3)
        
        text_lower = text.lower().strip()
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.REGION_RESIDENCY_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.REGION_RESIDENCY_PATTERNS):
                return True
        
        return False
    
    def matches_rate_tier(self, text: str, max_words: Optional[int] = None) -> bool:
        """
        Check if text matches rate tier patterns (Loan Amount, Risk Band, etc.).
        
        Args:
            text: Text to check
            max_words: Maximum number of words allowed (defaults to YAML config)
        
        Returns:
            True if text matches rate tier patterns
        """
        if max_words is None:
            max_words = self._keywords.get("rate_tier", {}).get("max_words", 4)
        
        text_lower = text.lower().strip()
        
        # Check specific phrases (highest priority)
        if any(phrase in text_lower for phrase in self.RATE_TIER_PHRASES):
            return True
        
        # Check generic patterns (must be short phrase)
        if len(text_lower.split()) <= max_words:
            if any(pattern in text_lower for pattern in self.RATE_TIER_PATTERNS):
                return True
        
        return False
    
    # ============================================================================
    # CLASS METHODS (for backward compatibility)
    # ============================================================================
    
    @classmethod
    def get_loan_type_keywords(cls) -> Dict[str, List[str]]:
        """Get all loan type keywords organized by category."""
        instance = cls()
        return {
            "phrases": instance.LOAN_TYPE_PHRASES,
            "patterns": instance.LOAN_TYPE_PATTERNS,
            "exclusions": instance.LOAN_TYPE_EXCLUSIONS,
            "labels": instance.LOAN_TYPE_LABEL_KEYWORDS,
        }
    
    @classmethod
    def get_repayment_type_keywords(cls) -> Dict[str, List[str]]:
        """Get all repayment type keywords organized by category."""
        instance = cls()
        return {
            "phrases": instance.REPAYMENT_TYPE_PHRASES,
            "patterns": instance.REPAYMENT_TYPE_PATTERNS,
            "exclusions": instance.REPAYMENT_TYPE_EXCLUSIONS,
            "labels": instance.REPAYMENT_TYPE_LABEL_KEYWORDS,
        }


# Create singleton instance for easy access
_filter_keywords_instance = FilterKeywords()

# Provide class-level access for backward compatibility
def matches_loan_type(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for loan type matching."""
    return _filter_keywords_instance.matches_loan_type(text, max_words)

def matches_repayment_type(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for repayment type matching."""
    return _filter_keywords_instance.matches_repayment_type(text, max_words)

def matches_lvr_tier(text: str) -> bool:
    """Convenience function for LVR tier matching."""
    return _filter_keywords_instance.matches_lvr_tier(text)

def matches_loan_term(text: str) -> bool:
    """Convenience function for loan term matching."""
    return _filter_keywords_instance.matches_loan_term(text)

def matches_rate_type(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for rate type matching."""
    return _filter_keywords_instance.matches_rate_type(text, max_words)

def matches_loan_purpose(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for loan purpose matching."""
    return _filter_keywords_instance.matches_loan_purpose(text, max_words)

def matches_product_segment(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for product segment matching."""
    return _filter_keywords_instance.matches_product_segment(text, max_words)

def matches_region_residency(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for region/residency matching."""
    return _filter_keywords_instance.matches_region_residency(text, max_words)

def matches_rate_tier(text: str, max_words: Optional[int] = None) -> bool:
    """Convenience function for rate tier matching."""
    return _filter_keywords_instance.matches_rate_tier(text, max_words)

