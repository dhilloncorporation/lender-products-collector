#!/usr/bin/env python3
"""
Test URL discovery - show what URLs we find from different search engines.
"""

import asyncio
import logging
from src.configs.settings_manager import YamlSettingsManager
from src.agents.discovery.web_search_discovery import WebSearchDiscovery

# Load .env file
import load_env

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_url_discovery():
    """Test URL discovery and show results."""
    logger.info("🔍 Testing URL Discovery")
    logger.info("=" * 50)
    
    # Initialize managers
    settings_manager = YamlSettingsManager()
    web_search = settings_manager.get_web_search()
    
    # Show configuration
    logger.info(f"🔍 Primary search engine: {web_search.primary_engine}")
    logger.info(f"🔍 Available engines: {list(web_search.engines.keys())}")
    logger.info(f"🔍 Fallback order: {web_search.fallback_order}")
    
    # Initialize discovery
    discovery = WebSearchDiscovery(settings_manager)
    
    # Test with different lenders
    test_lenders = [
        {"name": "ANZ", "domain": "anz.com.au"},
        {"name": "Commonwealth Bank", "domain": "commbank.com.au"},
        {"name": "Westpac", "domain": "westpac.com.au"},
    ]
    
    for lender in test_lenders:
        logger.info(f"\n🏦 Testing {lender['name']}...")
        logger.info("-" * 30)
        
        try:
            # Discover URLs
            discovered_urls = await discovery.discover_lender_pages(
                lender_name=lender["name"],
                lender_domain=lender["domain"]
            )
            
            # Show results
            total_urls = sum(len(urls) for urls in discovered_urls.values())
            logger.info(f"✅ Found {total_urls} total URLs for {lender['name']}")
            
            for category, urls in discovered_urls.items():
                if urls:
                    logger.info(f"\n📂 {category.upper()} ({len(urls)} URLs):")
                    for i, url in enumerate(urls, 1):
                        logger.info(f"  {i}. {url}")
                else:
                    logger.warning(f"📂 {category.upper()}: No URLs found")
            
        except Exception as e:
            logger.error(f"❌ Failed to discover URLs for {lender['name']}: {e}")
        
        # Wait between lenders
        logger.info(f"⏱️  Waiting 5 seconds before next lender...")
        await asyncio.sleep(5)
    
    logger.info("\n🎉 URL discovery test completed!")

if __name__ == "__main__":
    asyncio.run(test_url_discovery())
