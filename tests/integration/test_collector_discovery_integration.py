#!/usr/bin/env python3
"""
Simple collection test - test the multi-engine web search system.
"""

import asyncio
import logging
from src.configs.settings_manager import YamlSettingsManager
from src.configs.lender_config import LenderConfigManager
from src.agents.discovery.web_search_discovery import WebSearchDiscovery
from src.agents.collector.playwright_collector import PlaywrightCollectorAgent

# Load .env file
import load_env

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simple_collection():
    """Test basic collection functionality with multi-engine search."""
    logger.info("🚀 Starting Simple Collection Test")
    logger.info("=" * 50)
    
    # Initialize managers
    settings_manager = YamlSettingsManager()
    lender_config_manager = LenderConfigManager()
    
    # Show search engine configuration
    web_search = settings_manager.get_web_search()
    logger.info(f"🔍 Primary search engine: {web_search.primary_engine}")
    logger.info(f"🔍 Available engines: {list(web_search.engines.keys())}")
    logger.info(f"🔍 Fallback order: {web_search.fallback_order}")
    
    # Test web search discovery
    logger.info("\n🔍 Testing multi-engine web search discovery...")
    discovery = WebSearchDiscovery(settings_manager)
    
    # Test with ANZ (known working lender)
    try:
        logger.info("Testing ANZ search...")
        discovered_urls = await discovery.discover_lender_pages(
            lender_name="ANZ",
            lender_domain="anz.com.au"
        )
        logger.info(f"✅ Discovered {len(discovered_urls)} URL categories for ANZ")
        for category, urls in discovered_urls.items():
            logger.info(f"  {category}: {len(urls)} URLs")
            for url in urls[:2]:  # Show first 2 URLs
                logger.info(f"    - {url}")
    except Exception as e:
        logger.error(f"❌ Discovery failed: {e}")
    
    # Test Playwright collector
    logger.info("\n🎭 Testing Playwright collector...")
    try:
        async with PlaywrightCollectorAgent(headless=True) as collector:
            # Test with a simple URL
            test_url = "https://www.anz.com.au/personal/home-loans/"
            logger.info(f"Collecting from: {test_url}")
            products = await collector.collect_from_url(
                url=test_url,
                lender_name="ANZ"
            )
            logger.info(f"✅ Collected {len(products)} products from {test_url}")
            for product in products[:3]:  # Show first 3 products
                logger.info(f"  📋 {product.name}: {product.rate}%")
    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
    
    logger.info("\n🎉 Simple collection test completed!")

if __name__ == "__main__":
    asyncio.run(test_simple_collection())
