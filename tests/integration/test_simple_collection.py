#!/usr/bin/env python3
"""
Simple collection test without the complex workflow.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.configs.settings_manager import YamlSettingsManager
from src.configs.lender_config import LenderConfigManager
from src.agents.discovery.search_discovery import SearchDiscovery
from src.agents.collector.playwright_collector import PlaywrightCollectorAgent

# Load .env file
import load_env

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simple_collection():
    """Test basic collection functionality."""
    logger.info("🚀 Starting simple collection test...")
    
    # Initialize managers
    settings_manager = YamlSettingsManager()
    lender_config_manager = LenderConfigManager()
    
    # Test web search discovery
    logger.info("🔍 Testing web search discovery...")
    discovery = SearchDiscovery(settings_manager)
    
    # Test with ANZ (known working lender)
    try:
        # Show the search URLs that will be used
        logger.info("🔗 Search URLs that will be used:")
        for category, template in discovery.search_templates.items():
            query = template.format(domain="anz.com.au")
            # Get the primary engine to build URL
            if discovery.engines:
                primary_engine = list(discovery.engines.values())[0]
                search_url = primary_engine.build_search_url(query, 3)
                logger.info(f"  {category}: {search_url}")
        
        discovered_urls = await discovery.discover_lender_pages(
            lender_name="ANZ",
            lender_domain="anz.com.au"
        )
        logger.info(f"✅ Discovered {len(discovered_urls)} URL categories for ANZ")
        for category, urls in discovered_urls.items():
            logger.info(f"  {category}: {len(urls)} URLs")
    except Exception as e:
        logger.error(f"❌ Discovery failed: {e}")
    
    # Test Playwright collector
    logger.info("🎭 Testing Playwright collector...")
    try:
        async with PlaywrightCollectorAgent(headless=True) as collector:
            # Test with a simple URL
            test_url = "https://www.anz.com.au/personal/home-loans/"
            products = await collector.collect_from_url(
                url=test_url,
                lender_name="ANZ"
            )
            logger.info(f"✅ Collected {len(products)} products from {test_url}")
            for product in products[:3]:  # Show first 3 products
                logger.info(f"  - {product.name}: {product.rate}%")
    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
    
    logger.info("🎉 Simple collection test completed!")

if __name__ == "__main__":
    asyncio.run(test_simple_collection())
