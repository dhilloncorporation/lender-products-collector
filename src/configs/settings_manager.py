"""YAML-based settings manager with environment variable substitution."""

import os
import re
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def substitute_env_vars(data: Any) -> Any:
    """
    Recursively substitute environment variables in YAML data.
    
    Supports syntax: ${VAR_NAME} or ${VAR_NAME:-default_value}
    """
    if isinstance(data, dict):
        return {key: substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r'\$\{([^:}]+)(?::-([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, data)
    else:
        return data


@dataclass
class CollectionSettings:
    """Collection operation settings."""
    max_retries: int
    timeout_seconds: int
    concurrent_collections: int
    rate_limit_per_minute: int
    default_frequency: str
    volatile_lenders_hourly: bool


@dataclass
class Features:
    """Feature flags."""
    google_search_enabled: bool
    notifications_enabled: bool
    debug_mode: bool
    firecrawl_enabled: bool


@dataclass
class Environment:
    """Environment-specific settings."""
    log_level: str
    api_port: int
    data_path: str
    timezone: str


@dataclass
class RateLimits:
    """Rate limiting and timing settings."""
    # Web Search timing
    search_delay_seconds: int
    search_between_queries_seconds: int
    search_daily_limit: int
    
    # Per-lender timing
    per_lender_delay_seconds: int
    per_url_delay_seconds: int
    
    # Request-level timing
    request_delay_ms: int
    global_requests_per_minute: int
    
    # Backoff strategy
    backoff_enabled: bool
    backoff_initial_delay_seconds: int
    backoff_max_delay_seconds: int
    backoff_multiplier: float
    backoff_max_attempts: int
    
    # Human-like behavior timing (with defaults)
    human_like_delays: bool = True
    min_delay_seconds: int = 10
    max_delay_seconds: int = 30
    random_jitter: bool = True


@dataclass
class SearchEngine:
    """Individual search engine configuration."""
    name: str
    base_url: str
    params: str
    user_agent: str
    timeout_seconds: int
    rate_limit_per_hour: int


@dataclass
class GoogleCustomSearch:
    """Google Custom Search API configuration."""
    name: str
    enabled: bool
    priority: int
    api_key_env: str
    search_engine_id_env: str
    base_url: str
    daily_limit: int
    cost_per_1000: float
    timeout_seconds: int
    search_delay_seconds: int
    between_queries_delay_seconds: int
    human_like_delays: bool
    random_jitter: bool


@dataclass
class WebSearch:
    """Web search configuration."""
    primary_engine: str
    google_custom_search: Optional[GoogleCustomSearch]
    engines: Dict[str, SearchEngine]
    fallback_enabled: bool
    fallback_order: List[str]
    search_templates: Dict[str, str]


@dataclass
class Debug:
    """Debug settings."""
    save_html: bool
    save_screenshots: bool
    output_path: str


@dataclass
class Notifications:
    """Notification settings."""
    email: Dict[str, Any]
    slack: Dict[str, str]


@dataclass
class AI:
    """AI/LLM settings."""
    openai_model: str
    openai_api_key_env: str
    temperature: float
    max_tokens: int


@dataclass
class Validation:
    """Data validation settings."""
    enabled: bool
    min_rate: float
    max_rate: float
    max_age_hours: int


class YamlSettingsManager:
    """Manager for loading and accessing YAML configuration settings with env var substitution."""
    
    def __init__(self, config_dir: str = "src/configs"):
        self.config_dir = Path(config_dir)
        self.collection_settings: Optional[CollectionSettings] = None
        self.features: Optional[Features] = None
        self.environment: Optional[Environment] = None
        self.rate_limits: Optional[RateLimits] = None
        self.web_search: Optional[WebSearch] = None
        self.debug: Optional[Debug] = None
        self.notifications: Optional[Notifications] = None
        self.ai: Optional[AI] = None
        self.validation: Optional[Validation] = None
        self._raw_config: Optional[Dict[str, Any]] = None  # Store raw config for access
        
        self._load_all_settings()
    
    def _load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """Load and parse a YAML file with environment variable substitution."""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
            
            # Substitute environment variables
            processed_data = substitute_env_vars(raw_data)
            
            logger.info(f"Loaded configuration from {file_path}")
            return processed_data
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load {file_path}: {e}")
    
    def _load_all_settings(self):
        """Load all configuration settings from YAML files."""
        try:
            # Load main configuration
            config_data = self._load_yaml_file("collection_settings.yaml")
            
            # Store raw config for access
            self._raw_config = config_data
            
            # Load each settings section
            self.collection_settings = CollectionSettings(**config_data["collection_settings"])
            self.features = Features(**config_data["features"])
            self.environment = Environment(**config_data["environment"])
            
            # Load rate limits with fallback for new fields
            rate_limits_data = config_data["rate_limits"]
            self.rate_limits = RateLimits(
                search_delay_seconds=rate_limits_data.get("search_delay_seconds", 15),
                search_between_queries_seconds=rate_limits_data.get("search_between_queries_seconds", 20),
                search_daily_limit=rate_limits_data.get("search_daily_limit", 50),
                human_like_delays=rate_limits_data.get("human_like_delays", True),
                min_delay_seconds=rate_limits_data.get("min_delay_seconds", 10),
                max_delay_seconds=rate_limits_data.get("max_delay_seconds", 30),
                random_jitter=rate_limits_data.get("random_jitter", True),
                per_lender_delay_seconds=rate_limits_data.get("per_lender_delay_seconds", 3),
                per_url_delay_seconds=rate_limits_data.get("per_url_delay_seconds", 2),
                request_delay_ms=rate_limits_data.get("request_delay_ms", 100),
                global_requests_per_minute=rate_limits_data.get("global_requests_per_minute", 60),
                backoff_enabled=rate_limits_data.get("backoff_enabled", True),
                backoff_initial_delay_seconds=rate_limits_data.get("backoff_initial_delay_seconds", 60),
                backoff_max_delay_seconds=rate_limits_data.get("backoff_max_delay_seconds", 1800),
                backoff_multiplier=rate_limits_data.get("backoff_multiplier", 2.0),
                backoff_max_attempts=rate_limits_data.get("backoff_max_attempts", 5)
            )
            
            # Load web search configuration
            web_search_data = config_data["web_search"]
            engines = {}
            for engine_name, engine_data in web_search_data["engines"].items():
                engines[engine_name] = SearchEngine(**engine_data)
            
            # Load Google Custom Search configuration if present
            google_custom_search = None
            if "google_custom_search" in web_search_data:
                google_custom_search = GoogleCustomSearch(**web_search_data["google_custom_search"])
            
            self.web_search = WebSearch(
                primary_engine=web_search_data["primary_engine"],
                google_custom_search=google_custom_search,
                engines=engines,
                fallback_enabled=web_search_data["fallback_enabled"],
                fallback_order=web_search_data["fallback_order"],
                search_templates=web_search_data["search_templates"]
            )
            
            self.debug = Debug(**config_data["debug"])
            self.notifications = Notifications(**config_data["notifications"])
            self.ai = AI(**config_data["ai"])
            self.validation = Validation(**config_data["validation"])
            
            logger.info("All configuration settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    # Getter methods for each settings section
    def get_collection_settings(self) -> CollectionSettings:
        """Get collection operation settings."""
        return self.collection_settings
    
    def get_features(self) -> Features:
        """Get feature flags."""
        return self.features
    
    def get_environment(self) -> Environment:
        """Get environment-specific settings."""
        return self.environment
    
    def get_rate_limits(self) -> RateLimits:
        """Get rate limiting settings."""
        return self.rate_limits
    
    def get_debug(self) -> Debug:
        """Get debug settings."""
        return self.debug
    
    def get_notifications(self) -> Notifications:
        """Get notification settings."""
        return self.notifications
    
    def get_ai(self) -> AI:
        """Get AI/LLM settings."""
        return self.ai
    
    def get_validation(self) -> Validation:
        """Get data validation settings."""
        return self.validation
    
    def get_schema(self) -> Dict[str, Any]:
        """Get schema configuration (version, format)."""
        return self._raw_config.get('schema', {'version': '2.0.0', 'format': 'state_explicit'})
    
    def get_web_search(self) -> WebSearch:
        """Get web search settings."""
        return self.web_search
    
    def get_web_search_config(self) -> Dict[str, Any]:
        """Get web search configuration as dictionary for compatibility."""
        from dataclasses import asdict
        return asdict(self.web_search)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return {
            "collection_settings": self.collection_settings,
            "features": self.features,
            "environment": self.environment,
            "rate_limits": self.rate_limits,
            "debug": self.debug,
            "notifications": self.notifications,
            "ai": self.ai,
            "validation": self.validation,
        }
    
    def reload_settings(self):
        """Reload all settings from configuration files."""
        logger.info("Reloading all configuration settings...")
        self._load_all_settings()
        logger.info("Configuration settings reloaded successfully")
