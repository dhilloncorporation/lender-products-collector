"""
Multi-engine search discovery orchestrator.

This module imports and coordinates individual search engine implementations.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from .yahoo_search import YahooSearchEngine
from .google_search import GoogleSearchEngine
from .bing_search import BingSearchEngine

logger = logging.getLogger(__name__)


class MultiEngineSearchDiscovery:
    """Multi-engine search discovery with fallback support."""
    
    def __init__(self, settings_manager=None):
        """Initialize multi-engine search discovery."""
        self.settings_manager = settings_manager
        
        # Get search configuration
        if settings_manager:
            web_search_config = settings_manager.get_web_search_config()
            self.primary_engine = web_search_config.get('primary_engine', 'yahoo')
            self.engines_config = web_search_config.get('engines', {})
            self.fallback_enabled = web_search_config.get('fallback_enabled', True)
            self.fallback_order = web_search_config.get('fallback_order', ['yahoo', 'google', 'bing'])
            
            # Get rate limits
            rate_limits = settings_manager.get_rate_limits()
            self.delay_between_searches = rate_limits.search_delay_seconds
            self.delay_between_queries = rate_limits.search_between_queries_seconds
            self.backoff_enabled = rate_limits.backoff_enabled
            self.backoff_initial_delay = rate_limits.backoff_initial_delay_seconds
            self.backoff_max_delay = rate_limits.backoff_max_delay_seconds
            self.backoff_multiplier = rate_limits.backoff_multiplier
            self.backoff_max_attempts = rate_limits.backoff_max_attempts
        else:
            # Fallback defaults
            self.primary_engine = 'yahoo'
            self.engines_config = {}
            self.fallback_enabled = True
            self.fallback_order = ['yahoo', 'google', 'bing']
            self.delay_between_searches = 8
            self.delay_between_queries = 10
            self.backoff_enabled = True
            self.backoff_initial_delay = 60
            self.backoff_max_delay = 1800
            self.backoff_multiplier = 2.0
            self.backoff_max_attempts = 5
        
        # Initialize engines
        self.engines = {}
        self._initialize_engines()
        
        # Search templates
        self.search_templates = {
            "interest_rates": 'site:{domain} intitle:"home loan" interest rates',
            "products": 'site:{domain} intitle:"home loans" products',
            "comparison": 'site:{domain} intitle:"home loans" compare',
            "fees": 'site:{domain} "home loan" fees OR charges',
            "rates_alt": 'site:{domain} intitle:"home loan" rate',
        }
    
    def _initialize_engines(self):
        """Initialize available search engines."""
        # Yahoo engine
        if 'yahoo' in self.engines_config:
            self.engines['yahoo'] = YahooSearchEngine(self.engines_config['yahoo'])
        
        # Google engine
        if 'google' in self.engines_config:
            self.engines['google'] = GoogleSearchEngine(self.engines_config['google'])
        
        # Bing engine
        if 'bing' in self.engines_config:
            self.engines['bing'] = BingSearchEngine(self.engines_config['bing'])
        
        logger.info(f"Initialized {len(self.engines)} search engines: {list(self.engines.keys())}")
    
    async def discover_lender_pages(
        self, 
        lender_name: str,
        lender_domain: str = None
    ) -> Dict[str, List[str]]:
        """
        Discover relevant pages for a lender using multi-engine search.
        
        Args:
            lender_name: Name of the lender (e.g., "Commonwealth Bank")
            lender_domain: Optional domain to restrict search (e.g., "commbank.com.au")
        
        Returns:
            Dict with discovered URLs by category
        """
        discovered_pages = {
            "interest_rates": [],
            "products": [],
            "fees": [],
            "comparison": []
        }
        
        # Build search queries
        search_queries = {}
        
        if lender_domain:
            for key, template in self.search_templates.items():
                search_queries[key] = template.format(domain=lender_domain)
        else:
            search_queries = {
                "interest_rates": f"{lender_name} home loan interest rates",
                "products": f"{lender_name} home loan products",
                "fees": f"{lender_name} home loan fees charges",
                "comparison": f"{lender_name} compare home loans"
            }
        
        # Search each category
        for i, (category, query) in enumerate(search_queries.items()):
            try:
                # Add delay between searches
                if i > 0:
                    delay = self.delay_between_queries
                    logger.info(f"⏱️  Waiting {delay}s before next search query...")
                    await asyncio.sleep(delay)
                
                logger.info(f"🔍 Searching for {lender_name} {category}...")
                urls = await self._search_with_fallback(query, max_results=3)
                discovered_pages[category] = urls
                
                if urls:
                    logger.info(f"  ✅ Found {len(urls)} {category} pages")
                    for url in urls:
                        logger.info(f"     - {url}")
                else:
                    logger.warning(f"  ⚠️  No {category} pages found")
            
            except Exception as e:
                logger.error(f"Search failed for {category}: {e}")
        
        return discovered_pages
    
    async def _search_with_fallback(self, query: str, max_results: int = 5) -> List[str]:
        """Search using primary engine with fallback to other engines."""
        # Try engines in order
        engines_to_try = [self.primary_engine] + [e for e in self.fallback_order if e != self.primary_engine]
        
        for engine_name in engines_to_try:
            if engine_name not in self.engines:
                logger.warning(f"Engine {engine_name} not available, skipping...")
                continue
            
            engine = self.engines[engine_name]
            logger.info(f"🔍 Trying {engine.name} search...")
            
            try:
                urls = await engine.search(query, max_results)
                if urls:
                    logger.info(f"✅ {engine.name} found {len(urls)} results")
                    return urls
                else:
                    logger.warning(f"⚠️  {engine.name} returned no results")
            
            except Exception as e:
                logger.error(f"❌ {engine.name} search failed: {e}")
                continue
        
        logger.warning("🚫 All search engines failed")
        return []
