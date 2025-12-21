#!/usr/bin/env python3
"""
Test different search engines to see which ones work.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.configs.settings_manager import YamlSettingsManager
from src.agents.discovery.search_discovery import SearchDiscovery

# Load .env file
import load_env

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_search_engines():
    """Test different search engines."""
    logger.info("🔍 Testing Different Search Engines")
    logger.info("=" * 50)
    
    settings_manager = YamlSettingsManager()
    web_search = settings_manager.get_web_search()
    
    # Show available engines
    logger.info(f"Available engines: {list(web_search.engines.keys())}")
    logger.info(f"Primary engine: {web_search.primary_engine}")
    logger.info(f"Fallback order: {web_search.fallback_order}")
    
    # Test each engine individually
    discovery = SearchDiscovery(settings_manager)
    
    test_query = "site:anz.com.au home loan interest rates"
    
    # Test only engines that are actually implemented
    implemented_engines = ['yahoo', 'google', 'bing']
    
    for engine_name in implemented_engines:
        if engine_name in discovery.engines:
            logger.info(f"\n🧪 Testing {engine_name.upper()}...")
            try:
                engine = discovery.engines[engine_name]
                
                # Log the search URL for manual testing
                search_url = engine.build_search_url(test_query, 3)
                logger.info(f"  🔗 Search URL: {search_url}")
                logger.info(f"  💡 Try this URL manually in your browser!")
                
                urls = await engine.search(test_query, 3)
                
                if urls:
                    logger.info(f"  ✅ {engine_name} found {len(urls)} results")
                    for url in urls[:2]:  # Show first 2 URLs
                        logger.info(f"    - {url}")
                else:
                    logger.warning(f"  ⚠️  {engine_name} returned no results")
                    
            except Exception as e:
                logger.error(f"  ❌ {engine_name} failed: {e}")
            
            # Wait between engines
            await asyncio.sleep(2)
    
    logger.info("\n🎉 Search engine testing completed!")

if __name__ == "__main__":
    asyncio.run(test_search_engines())
