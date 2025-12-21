"""Collection scheduler agent for managing data collection schedules."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..collector.firecrawl_collector import FirecrawlCollectorAgent
from ...configs import LenderConfigManager
from ...configs.yaml_settings_manager import YamlSettingsManager
from ..workflows.collection_workflow import CollectionWorkflow

logger = logging.getLogger(__name__)


class CollectionSchedulerAgent:
    """Agent that manages collection schedules and triggers connector agents."""
    
    def __init__(self, config_path: str = "src/configs/lenders.json"):
        self.scheduler = AsyncIOScheduler()
        self.collector_agent = FirecrawlCollectorAgent()
        self.config_manager = LenderConfigManager(config_path)
        self.collection_results: Dict[str, Any] = {}
    
    def start_scheduler(self):
        """Start the scheduler with configured jobs."""
        # Daily collection at 2:00 AM
        self.scheduler.add_job(
            self.run_daily_collection,
            CronTrigger(hour=2, minute=0),
            id="daily_collection",
            name="Daily Loan Product Collection"
        )
        
        # Hourly collection for volatile lenders (if needed)
        self.scheduler.add_job(
            self.run_hourly_collection,
            IntervalTrigger(hours=1),
            id="hourly_collection", 
            name="Hourly Collection for Volatile Lenders"
        )
        
        self.scheduler.start()
        logger.info("Collection scheduler started")
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Collection scheduler stopped")
    
    async def run_daily_collection(self):
        """Run daily collection for all lenders."""
        logger.info("Starting daily collection")
        start_time = datetime.now()
        
        try:
            # Run collection for all enabled lenders in parallel
            enabled_lenders = self.config_manager.get_enabled_lenders()
            tasks = []
            for lender_config in enabled_lenders:
                task = asyncio.create_task(self.collect_from_lender(lender_config))
                tasks.append(task)
            
            # Wait for all collections to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful_collections = 0
            failed_collections = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Collection failed for {enabled_lenders[i].name}: {result}")
                    failed_collections += 1
                else:
                    successful_collections += 1
            
            # Store collection results
            self.collection_results["daily"] = {
                "timestamp": start_time.isoformat(),
                "duration": (datetime.now() - start_time).total_seconds(),
                "successful": successful_collections,
                "failed": failed_collections,
                "total_products": len(self.collector_agent.get_collected_products())
            }
            
            logger.info(f"Daily collection completed: {successful_collections} successful, {failed_collections} failed")
            
        except Exception as e:
            logger.error(f"Daily collection failed: {str(e)}")
            self.collection_results["daily"] = {
                "timestamp": start_time.isoformat(),
                "error": str(e),
                "successful": 0,
                "failed": len(self.lender_adapters)
            }
    
    async def run_hourly_collection(self):
        """Run hourly collection for volatile lenders."""
        logger.info("Starting hourly collection for volatile lenders")
        
        # Only collect from volatile lenders
        volatile_lenders = self.config_manager.get_volatile_lenders()
        
        for lender_config in volatile_lenders:
            try:
                await self.collect_from_lender(lender_config)
                logger.info(f"Hourly collection completed for {lender_config.name}")
            except Exception as e:
                logger.error(f"Hourly collection failed for {lender_config.name}: {str(e)}")
    
    async def collect_from_lender(self, adapter: LenderAdapter) -> Dict[str, Any]:
        """Collect data from a specific lender using its adapter."""
        logger.info(f"Collecting data from {adapter.lender_name}")
        
        try:
            urls = adapter.get_collection_urls()
            agent_prompt = adapter.get_agent_prompt()
            
            collected_products = []
            
            # Collect from each URL for this lender
            for url in urls:
                products = self.collector_agent.collect_from_url(
                    url=url,
                    lender_name=adapter.lender_name,
                    agent_prompt=agent_prompt
                )
                collected_products.extend(products)
            
            # Normalize products using lender-specific adapter
            normalized_products = adapter.normalize_products({
                "products": collected_products,
                "lender": adapter.lender_name
            })
            
            return {
                "lender": adapter.lender_name,
                "urls_processed": len(urls),
                "products_collected": len(collected_products),
                "products_normalized": len(normalized_products),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Collection failed for {adapter.lender_name}: {str(e)}")
            return {
                "lender": adapter.lender_name,
                "error": str(e),
                "success": False
            }
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status and results."""
        return {
            "scheduler_running": self.scheduler.running,
            "active_jobs": len(self.scheduler.get_jobs()),
            "collection_results": self.collection_results,
            "total_products_collected": len(self.collector_agent.get_collected_products())
        }
    
    def trigger_manual_collection(self, lender_name: Optional[str] = None):
        """Trigger manual collection for specific lender or all lenders."""
        if lender_name:
            # Collect from specific lender
            adapter = next((a for a in self.lender_adapters if a.lender_name == lender_name), None)
            if adapter:
                asyncio.create_task(self.collect_from_lender(adapter))
            else:
                logger.error(f"Lender adapter not found: {lender_name}")
        else:
            # Collect from all lenders
            asyncio.create_task(self.run_daily_collection())
