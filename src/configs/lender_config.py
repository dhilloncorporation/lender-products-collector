"""Lender configuration loader and manager."""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LenderConfig:
    """Configuration for a single lender."""
    name: str
    display_name: str
    base_url: str
    collection_urls: List[str]
    agent_prompt: str
    collection_frequency: str
    volatile: bool
    enabled: bool


class LenderConfigManager:
    """Manager for lender configurations."""
    
    def __init__(self, config_path: str = "src/configs/lenders.json"):
        self.config_path = Path(config_path)
        self.lenders: List[LenderConfig] = []
        self.collection_settings: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self):
        """Load lender configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Check if it's the new format (list of dicts) or old format (dict with lenders key)
            if isinstance(config_data, list):
                # New simplified format - just list of lenders
                lenders_list = config_data
            else:
                # Old format with lenders key
                lenders_list = config_data.get("lenders", [])
            
            # Load lenders
            self.lenders = []
            self.lenders_raw = []  # Store raw data for get_lender_by_abbreviation
            
            for lender_data in lenders_list:
                self.lenders_raw.append(lender_data)
                
                # Handle both old and new formats
                lender = LenderConfig(
                    name=lender_data.get("abbreviation", lender_data.get("name", "")),
                    display_name=lender_data.get("lender_name", lender_data.get("display_name", "")),
                    base_url=lender_data.get("base_url", ""),
                    collection_urls=lender_data.get("collection_urls", []),
                    agent_prompt=lender_data.get("agent_prompt", ""),
                    collection_frequency=lender_data.get("collection_frequency", "daily"),
                    volatile=lender_data.get("volatile", False),
                    enabled=lender_data.get("enabled", True)
                )
                self.lenders.append(lender)
            
            # Load collection settings
            if isinstance(config_data, dict):
                self.collection_settings = config_data.get("collection_settings", {})
            else:
                self.collection_settings = {}
            
            logger.info(f"Loaded configuration for {len(self.lenders)} lenders")
            
        except Exception as e:
            logger.error(f"Failed to load lender configuration: {str(e)}")
            # Fallback to default configuration
            self._create_default_config()
    
    def get_enabled_lenders(self) -> List[LenderConfig]:
        """Get all enabled lenders."""
        return [lender for lender in self.lenders if lender.enabled]
    
    def get_volatile_lenders(self) -> List[LenderConfig]:
        """Get volatile lenders that need frequent collection."""
        return [lender for lender in self.lenders if lender.enabled and lender.volatile]
    
    def get_lender_by_name(self, name: str) -> Optional[LenderConfig]:
        """Get lender configuration by name."""
        for lender in self.lenders:
            if lender.name.lower() == name.lower():
                return lender
        return None
    
    def get_lender_by_abbreviation(self, abbreviation: str) -> Optional[Dict[str, Any]]:
        """Get raw lender data by abbreviation."""
        for lender_data in self.lenders_raw:
            if lender_data.get("abbreviation", "").lower() == abbreviation.lower():
                return lender_data
        return None
    
    def get_daily_lenders(self) -> List[LenderConfig]:
        """Get lenders that should be collected daily."""
        return [lender for lender in self.lenders 
                if lender.enabled and lender.collection_frequency == "daily"]
    
    def get_hourly_lenders(self) -> List[LenderConfig]:
        """Get lenders that should be collected hourly."""
        return [lender for lender in self.lenders 
                if lender.enabled and lender.collection_frequency == "hourly"]
    
    def add_lender(self, lender: LenderConfig):
        """Add a new lender configuration."""
        # Check if lender already exists
        existing = self.get_lender_by_name(lender.name)
        if existing:
            logger.warning(f"Lender {lender.name} already exists, updating instead")
            self.update_lender(lender)
        else:
            self.lenders.append(lender)
            logger.info(f"Added new lender: {lender.name}")
    
    def update_lender(self, lender: LenderConfig):
        """Update an existing lender configuration."""
        for i, existing_lender in enumerate(self.lenders):
            if existing_lender.name.lower() == lender.name.lower():
                self.lenders[i] = lender
                logger.info(f"Updated lender: {lender.name}")
                return
        logger.warning(f"Lender {lender.name} not found for update")
    
    def disable_lender(self, name: str):
        """Disable a lender."""
        lender = self.get_lender_by_name(name)
        if lender:
            lender.enabled = False
            logger.info(f"Disabled lender: {name}")
        else:
            logger.warning(f"Lender {name} not found for disable")
    
    def enable_lender(self, name: str):
        """Enable a lender."""
        lender = self.get_lender_by_name(name)
        if lender:
            lender.enabled = True
            logger.info(f"Enabled lender: {name}")
        else:
            logger.warning(f"Lender {name} not found for enable")
    
    def save_config(self):
        """Save current configuration to JSON file."""
        try:
            config_data = {
                "lenders": [
                    {
                        "name": lender.name,
                        "display_name": lender.display_name,
                        "base_url": lender.base_url,
                        "collection_urls": lender.collection_urls,
                        "agent_prompt": lender.agent_prompt,
                        "collection_frequency": lender.collection_frequency,
                        "volatile": lender.volatile,
                        "enabled": lender.enabled
                    }
                    for lender in self.lenders
                ],
                "collection_settings": self.collection_settings,
                "last_updated": "2024-09-30T10:45:00Z",
                "version": "1.0.0"
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved configuration to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
    
    def _create_default_config(self):
        """Create default configuration if loading fails."""
        self.lenders = [
            LenderConfig(
                name="ANZ",
                display_name="ANZ Bank",
                base_url="https://www.anz.com.au",
                collection_urls=["https://www.anz.com.au/personal/home-loans/"],
                agent_prompt="Extract ANZ home loan products",
                collection_frequency="daily",
                volatile=True,
                enabled=True
            )
        ]
        # Initialize lenders_raw for get_lender_by_abbreviation to work
        self.lenders_raw = [
            {
                "abbreviation": "ANZ",
                "lender_name": "ANZ Bank",
                "collection_urls": ["https://www.anz.com.au/personal/home-loans/"]
            }
        ]
        self.collection_settings = {
            "default_frequency": "daily",
            "max_retries": 3,
            "retry_delay_seconds": 60
        }
        logger.warning("Using default configuration due to load failure")
