"""Settings manager for loading and managing configuration files."""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CollectionSettings:
    """Collection operation settings."""
    default_frequency: str
    volatile_lenders_hourly: bool
    max_retries: int
    retry_delay_seconds: int
    timeout_seconds: int
    concurrent_collections: int
    rate_limit_per_minute: int
    user_agent: str
    respect_robots_txt: bool
    follow_redirects: bool
    max_redirects: int


@dataclass
class SchedulerSettings:
    """Scheduler operation settings."""
    daily_collection_time: str
    hourly_collection_enabled: bool
    timezone: str
    job_coalesce: bool
    max_instances: int


@dataclass
class StorageSettings:
    """Storage operation settings."""
    data_path: str
    index_file: str
    backup_enabled: bool
    backup_retention_days: int
    compression_enabled: bool


@dataclass
class MonitoringSettings:
    """Monitoring operation settings."""
    log_level: str
    metrics_retention_days: int
    alert_on_failure_rate: float
    alert_on_stale_data_hours: int
    health_check_interval_minutes: int


@dataclass
class APISettings:
    """API operation settings."""
    host: str
    port: int
    cors_origins: list
    rate_limit_per_minute: int
    max_response_size_mb: int


@dataclass
class LangChainSettings:
    """LangChain model and configuration settings."""
    model_provider: str
    model_name: str
    temperature: float
    max_tokens: int
    api_key_env: str
    streaming: bool
    timeout_seconds: int


@dataclass
class LangGraphSettings:
    """LangGraph orchestration settings."""
    state_management: str
    max_iterations: int
    checkpointer_type: str
    checkpointer_config: dict
    interrupt_before: list
    interrupt_after: list


class SettingsManager:
    """Manager for loading and accessing configuration settings."""
    
    def __init__(self, config_dir: str = "src/configs"):
        self.config_dir = Path(config_dir)
        self.collection_settings: Optional[CollectionSettings] = None
        self.scheduler_settings: Optional[SchedulerSettings] = None
        self.storage_settings: Optional[StorageSettings] = None
        self.monitoring_settings: Optional[MonitoringSettings] = None
        self.api_settings: Optional[APISettings] = None
        self.langchain_settings: Optional[LangChainSettings] = None
        self.langgraph_settings: Optional[LangGraphSettings] = None
        
        self.load_all_settings()
    
    def load_all_settings(self):
        """Load all configuration settings."""
        self.load_collection_settings()
        self.load_scheduler_settings()
        self.load_storage_settings()
        self.load_monitoring_settings()
        self.load_api_settings()
        self.load_langchain_settings()
        self.load_langgraph_settings()
    
    def load_collection_settings(self):
        """Load collection settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            collection_data = data["collection_settings"]
            self.collection_settings = CollectionSettings(
                default_frequency=collection_data["default_frequency"],
                volatile_lenders_hourly=collection_data["volatile_lenders_hourly"],
                max_retries=collection_data["max_retries"],
                retry_delay_seconds=collection_data["retry_delay_seconds"],
                timeout_seconds=collection_data["timeout_seconds"],
                concurrent_collections=collection_data["concurrent_collections"],
                rate_limit_per_minute=collection_data["rate_limit_per_minute"],
                user_agent=collection_data["user_agent"],
                respect_robots_txt=collection_data["respect_robots_txt"],
                follow_redirects=collection_data["follow_redirects"],
                max_redirects=collection_data["max_redirects"]
            )
            
            logger.info("Collection settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load collection settings: {str(e)}")
            self._create_default_collection_settings()
    
    def load_scheduler_settings(self):
        """Load scheduler settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            scheduler_data = data["scheduler_settings"]
            self.scheduler_settings = SchedulerSettings(
                daily_collection_time=scheduler_data["daily_collection_time"],
                hourly_collection_enabled=scheduler_data["hourly_collection_enabled"],
                timezone=scheduler_data["timezone"],
                job_coalesce=scheduler_data["job_coalesce"],
                max_instances=scheduler_data["max_instances"]
            )
            
            logger.info("Scheduler settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load scheduler settings: {str(e)}")
            self._create_default_scheduler_settings()
    
    def load_storage_settings(self):
        """Load storage settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            storage_data = data["storage_settings"]
            self.storage_settings = StorageSettings(
                data_path=storage_data["data_path"],
                index_file=storage_data["index_file"],
                backup_enabled=storage_data["backup_enabled"],
                backup_retention_days=storage_data["backup_retention_days"],
                compression_enabled=storage_data["compression_enabled"]
            )
            
            logger.info("Storage settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load storage settings: {str(e)}")
            self._create_default_storage_settings()
    
    def load_monitoring_settings(self):
        """Load monitoring settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            monitoring_data = data["monitoring_settings"]
            self.monitoring_settings = MonitoringSettings(
                log_level=monitoring_data["log_level"],
                metrics_retention_days=monitoring_data["metrics_retention_days"],
                alert_on_failure_rate=monitoring_data["alert_on_failure_rate"],
                alert_on_stale_data_hours=monitoring_data["alert_on_stale_data_hours"],
                health_check_interval_minutes=monitoring_data["health_check_interval_minutes"]
            )
            
            logger.info("Monitoring settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load monitoring settings: {str(e)}")
            self._create_default_monitoring_settings()
    
    def load_api_settings(self):
        """Load API settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            api_data = data["api_settings"]
            self.api_settings = APISettings(
                host=api_data["host"],
                port=api_data["port"],
                cors_origins=api_data["cors_origins"],
                rate_limit_per_minute=api_data["rate_limit_per_minute"],
                max_response_size_mb=api_data["max_response_size_mb"]
            )
            
            logger.info("API settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load API settings: {str(e)}")
            self._create_default_api_settings()
    
    def load_langchain_settings(self):
        """Load LangChain settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            langchain_data = data["langchain_settings"]
            self.langchain_settings = LangChainSettings(
                model_provider=langchain_data["model_provider"],
                model_name=langchain_data["model_name"],
                temperature=langchain_data["temperature"],
                max_tokens=langchain_data["max_tokens"],
                api_key_env=langchain_data["api_key_env"],
                streaming=langchain_data["streaming"],
                timeout_seconds=langchain_data["timeout_seconds"]
            )
            
            logger.info("LangChain settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load LangChain settings: {str(e)}")
            self._create_default_langchain_settings()
    
    def load_langgraph_settings(self):
        """Load LangGraph settings from JSON file."""
        try:
            settings_file = self.config_dir / "collection_settings.json"
            with open(settings_file, 'r') as f:
                data = json.load(f)
            
            langgraph_data = data["langgraph_settings"]
            self.langgraph_settings = LangGraphSettings(
                state_management=langgraph_data["state_management"],
                max_iterations=langgraph_data["max_iterations"],
                checkpointer_type=langgraph_data["checkpointer_type"],
                checkpointer_config=langgraph_data["checkpointer_config"],
                interrupt_before=langgraph_data["interrupt_before"],
                interrupt_after=langgraph_data["interrupt_after"]
            )
            
            logger.info("LangGraph settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load LangGraph settings: {str(e)}")
            self._create_default_langgraph_settings()
    
    def _create_default_collection_settings(self):
        """Create default collection settings."""
        self.collection_settings = CollectionSettings(
            default_frequency="daily",
            volatile_lenders_hourly=True,
            max_retries=3,
            retry_delay_seconds=60,
            timeout_seconds=30,
            concurrent_collections=5,
            rate_limit_per_minute=60,
            user_agent="LenderProductsCollector/1.0",
            respect_robots_txt=True,
            follow_redirects=True,
            max_redirects=5
        )
        logger.warning("Using default collection settings")
    
    def _create_default_scheduler_settings(self):
        """Create default scheduler settings."""
        self.scheduler_settings = SchedulerSettings(
            daily_collection_time="02:00",
            hourly_collection_enabled=True,
            timezone="Australia/Sydney",
            job_coalesce=True,
            max_instances=1
        )
        logger.warning("Using default scheduler settings")
    
    def _create_default_storage_settings(self):
        """Create default storage settings."""
        self.storage_settings = StorageSettings(
            data_path="data/products",
            index_file="index.json",
            backup_enabled=True,
            backup_retention_days=30,
            compression_enabled=False
        )
        logger.warning("Using default storage settings")
    
    def _create_default_monitoring_settings(self):
        """Create default monitoring settings."""
        self.monitoring_settings = MonitoringSettings(
            log_level="INFO",
            metrics_retention_days=90,
            alert_on_failure_rate=0.2,
            alert_on_stale_data_hours=48,
            health_check_interval_minutes=15
        )
        logger.warning("Using default monitoring settings")
    
    def _create_default_api_settings(self):
        """Create default API settings."""
        self.api_settings = APISettings(
            host="0.0.0.0",
            port=8000,
            cors_origins=["*"],
            rate_limit_per_minute=100,
            max_response_size_mb=10
        )
        logger.warning("Using default API settings")
    
    def _create_default_langchain_settings(self):
        """Create default LangChain settings."""
        self.langchain_settings = LangChainSettings(
            model_provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.1,
            max_tokens=4000,
            api_key_env="OPENAI_API_KEY",
            streaming=False,
            timeout_seconds=30
        )
        logger.warning("Using default LangChain settings")
    
    def _create_default_langgraph_settings(self):
        """Create default LangGraph settings."""
        self.langgraph_settings = LangGraphSettings(
            state_management="memory",
            max_iterations=10,
            checkpointer_type="sqlite",
            checkpointer_config={"db_path": "langgraph_state.db"},
            interrupt_before=[],
            interrupt_after=[]
        )
        logger.warning("Using default LangGraph settings")
    
    def get_collection_settings(self) -> CollectionSettings:
        """Get collection settings."""
        return self.collection_settings
    
    def get_scheduler_settings(self) -> SchedulerSettings:
        """Get scheduler settings."""
        return self.scheduler_settings
    
    def get_storage_settings(self) -> StorageSettings:
        """Get storage settings."""
        return self.storage_settings
    
    def get_monitoring_settings(self) -> MonitoringSettings:
        """Get monitoring settings."""
        return self.monitoring_settings
    
    def get_api_settings(self) -> APISettings:
        """Get API settings."""
        return self.api_settings
    
    def get_langchain_settings(self) -> LangChainSettings:
        """Get LangChain settings."""
        return self.langchain_settings
    
    def get_langgraph_settings(self) -> LangGraphSettings:
        """Get LangGraph settings."""
        return self.langgraph_settings
