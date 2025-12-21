"""
Discovery Agent - URL Discovery and Search

ROLE: Worker Agent (URL Discovery)
PURPOSE: Discovers lender product pages using web search engines

This agent finds relevant URLs for loan product pages by searching across
multiple search engines. It uses Google Custom Search API (preferred) or
falls back to Playwright-based scraping of search engines.

SEARCH STRATEGY:
1. Google Custom Search API (preferred) - Fast, compliant, reliable
2. Multi-engine fallback - Yahoo, Google, Bing, DuckDuckGo, Yandex
3. Configurable search templates for different content types
4. Anti-blocking with rate limiting and delays

FEATURES:
- Multi-engine support with automatic fallback
- Google Custom Search API integration (when configured)
- Configurable search templates (interest_rates, products, comparison, fees)
- Rate limiting and anti-blocking measures
- URL validation and filtering

SEARCH ENGINES SUPPORTED:
- Google Custom Search API (preferred)
- Google (Playwright-based)
- Yahoo
- Bing
- DuckDuckGo
- Yandex

DEPENDENCIES:
- Google Custom Search API (optional, preferred)
- Playwright (for fallback engines)
- Settings Manager (for configuration)

USAGE:
    discovery = WebSearchDiscovery(settings_manager)
    pages = await discovery.discover_lender_pages(
        lender_name="ANZ",
        lender_domain="anz.com.au"
    )
"""

import asyncio
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

from .google_custom_search import GoogleCustomSearchAPI

logger = logging.getLogger(__name__)


class WebSearchDiscovery:
    """
    Multi-engine web search discovery agent with fallback strategy.
    
    This agent discovers lender product pages by searching across multiple
    search engines. It prioritizes Google Custom Search API (when available)
    and falls back to Playwright-based scraping of other search engines.
    
    Search Strategy:
        1. Try Google Custom Search API (preferred - fast, compliant)
        2. Fallback to multi-engine search (Yahoo, Google, Bing, etc.)
        3. Use configurable search templates for different content types
        4. Apply rate limiting and anti-blocking measures
    
    Attributes:
        settings_manager: Configuration manager for search settings
        primary_engine: Primary search engine to use
        fallback_order: List of engines to try in order
        search_templates: Templates for different search categories
        delay_between_searches: Delay between search operations
    
    Example:
        >>> discovery = WebSearchDiscovery(settings_manager)
        >>> pages = await discovery.discover_lender_pages(
        ...     lender_name="ANZ",
        ...     lender_domain="anz.com.au"
        ... )
        >>> print(f"Found {len(pages['interest_rates'])} rate pages")
    """
    
    def __init__(self, settings_manager=None):
        """Initialize the discovery agent."""
        self.settings_manager = settings_manager
        
        if settings_manager:
            self.rate_limits = settings_manager.get_rate_limits()
            self.web_search = settings_manager.get_web_search()
            
            # Timing controls
            self.delay_between_searches = self.rate_limits.search_delay_seconds
            self.delay_between_queries = self.rate_limits.search_between_queries_seconds
            self.daily_limit = self.rate_limits.search_daily_limit
            
            # Backoff strategy
            self.backoff_enabled = self.rate_limits.backoff_enabled
            self.backoff_initial_delay = self.rate_limits.backoff_initial_delay_seconds
            self.backoff_max_delay = self.rate_limits.backoff_max_delay_seconds
            self.backoff_multiplier = self.rate_limits.backoff_multiplier
            self.backoff_max_attempts = self.rate_limits.backoff_max_attempts
            
            # Search configuration
            self.primary_engine = self.web_search.primary_engine
            self.engines = self.web_search.engines
            self.fallback_enabled = self.web_search.fallback_enabled
            self.fallback_order = self.web_search.fallback_order
            self.search_templates = self.web_search.search_templates
            
            # Initialize Google Custom Search API if configured
            self.google_custom_search = None
            if hasattr(self.web_search, 'google_custom_search') and self.web_search.google_custom_search.enabled:
                try:
                    self.google_custom_search = GoogleCustomSearchAPI(settings_manager)
                    logger.info("✅ Google Custom Search API initialized")
                except Exception as e:
                    logger.warning(f"⚠️  Google Custom Search API not available: {e}")
                    self.google_custom_search = None
        else:
            # Fallback defaults
            self.delay_between_searches = 8
            self.delay_between_queries = 10
            self.daily_limit = 50
            self.backoff_enabled = True
            self.backoff_initial_delay = 60
            self.backoff_max_delay = 1800
            self.backoff_multiplier = 2.0
            self.backoff_max_attempts = 5
            self.primary_engine = "yahoo"
            self.fallback_enabled = True
            self.fallback_order = ["yahoo", "google", "bing", "duckduckgo"]
            self.search_templates = {
                "interest_rates": 'site:{domain} intitle:"home loan" interest rates',
                "products": 'site:{domain} intitle:"home loans" products',
                "comparison": 'site:{domain} intitle:"home loans" compare',
                "fees": 'site:{domain} "home loan" fees OR charges',
                "rates_alt": 'site:{domain} intitle:"home loan" rate',
            }
    
    async def discover_lender_pages(
        self, 
        lender_name: str,
        lender_domain: str = None
    ) -> Dict[str, List[str]]:
        """
        Discover lender pages using Google Custom Search API first, then fallback engines.
        
        Args:
            lender_name: Name of the lender
            lender_domain: Domain to search within (optional)
            
        Returns:
            Dictionary with categories as keys and lists of URLs as values
        """
        logger.debug("=" * 60)
        logger.debug(f"🌐 [DISCOVERY AGENT] Starting URL discovery")
        logger.debug(f"   Lender: {lender_name}")
        logger.debug(f"   Domain: {lender_domain}")
        logger.info(f"🔍 Starting search for {lender_name}")
        
        # Try Google Custom Search API first (preferred method)
        if self.google_custom_search and lender_domain:
            try:
                logger.debug("   [METHOD] Using Google Custom Search API (fast, compliant)")
                logger.info("🚀 Using Google Custom Search API (fast, compliant)")
                discovered_pages = await self.google_custom_search.discover_lender_pages(
                    lender_name=lender_name,
                    lender_domain=lender_domain
                )
                
                # Check if we got good results
                total_urls = sum(len(urls) for urls in discovered_pages.values())
                if total_urls > 0:
                    logger.debug(f"   ✅ [SUCCESS] Google Custom Search API found {total_urls} URLs")
                    logger.info(f"✅ Google Custom Search API found {total_urls} URLs")
                    return discovered_pages
                else:
                    logger.debug("   ⚠️  [FALLBACK] Google Custom Search API returned no results")
                    logger.warning("⚠️  Google Custom Search API returned no results, trying fallback engines")
            except Exception as e:
                logger.debug(f"   ❌ [ERROR] Google Custom Search API failed: {e}")
                logger.warning(f"⚠️  Google Custom Search API failed: {e}, trying fallback engines")
        
        # Fallback to multi-engine search
        logger.debug("   [METHOD] Falling back to multi-engine search (Playwright-based)")
        logger.info("🔄 Falling back to multi-engine search")
        
        # Generate search queries
        search_queries = self._generate_search_queries(lender_name, lender_domain)
        discovered_pages = {}
        
        # Try each search query
        for i, (category, query) in enumerate(search_queries.items()):
            try:
                # Add delay between searches
                if i > 0:
                    logger.info(f"⏱️  Waiting {self.delay_between_queries}s between search queries...")
                    await asyncio.sleep(self.delay_between_queries)
                
                logger.info(f"🔍 Searching for {lender_name} {category}...")
                
                # Try primary engine first, then fallback
                urls = await self._search_with_fallback(query, max_results=3)
                discovered_pages[category] = urls
                
                if urls:
                    logger.info(f"  ✅ Found {len(urls)} {category} pages")
                    for url in urls:
                        logger.info(f"     - {url}")
                else:
                    logger.warning(f"  ⚠️  No {category} pages found")
                    
            except Exception as e:
                logger.error(f"  ❌ Search failed for {category}: {e}")
                discovered_pages[category] = []
        
        return discovered_pages
    
    def _generate_search_queries(self, lender_name: str, lender_domain: str = None) -> Dict[str, str]:
        """Generate search queries for different content types."""
        domain = lender_domain or f"{lender_name.lower()}.com.au"
        
        queries = {}
        for category, template in self.search_templates.items():
            queries[category] = template.format(domain=domain)
        
        return queries
    
    async def _search_with_fallback(self, query: str, max_results: int = 3) -> List[str]:
        """Search using primary engine with fallback to other engines."""
        engines_to_try = [self.primary_engine] + self.fallback_order
        
        for engine_name in engines_to_try:
            if engine_name not in self.engines:
                continue
                
            try:
                logger.debug(f"  Trying {engine_name}...")
                urls = await self._search_with_engine(engine_name, query, max_results)
                
                if urls:
                    logger.info(f"  ✅ {engine_name} found {len(urls)} results")
                    return urls
                else:
                    logger.debug(f"  ⚠️  {engine_name} returned no results")
                    
            except Exception as e:
                logger.warning(f"  ❌ {engine_name} failed: {e}")
                continue
        
        logger.warning("  🚫 All search engines failed")
        return []
    
    async def _search_with_engine(self, engine_name: str, query: str, max_results: int) -> List[str]:
        """Search using a specific engine."""
        engine = self.engines[engine_name]
        
        # Build search URL
        search_url = self._build_search_url(engine, query, max_results)
        logger.debug(f"Search URL: {search_url}")
        
        urls = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent
                await page.set_extra_http_headers({"User-Agent": engine.user_agent})
                
                try:
                    # Navigate to search page
                    await page.goto(search_url, wait_until='domcontentloaded', timeout=engine.timeout_seconds * 1000)
                    await page.wait_for_timeout(2000)  # Wait for dynamic content
                    
                    # Check for blocking/CAPTCHA and diagnose
                    page_content = await page.content()
                    diagnosis = self._diagnose_search_failure(page_content, engine_name)
                    
                    if "BLOCKED" in diagnosis:
                        logger.warning(f"  🚫 {engine_name}: {diagnosis}")
                        return []
                    elif "NO_RESULTS" in diagnosis:
                        logger.info(f"  ℹ️  {engine_name}: {diagnosis}")
                        return []
                    elif "ERROR" in diagnosis or "TIMEOUT" in diagnosis:
                        logger.error(f"  ❌ {engine_name}: {diagnosis}")
                        return []
                    
                    # Extract URLs based on engine
                    urls = await self._extract_urls_from_page(page, engine_name)
                    
                    # Save debug info
                    await self._save_debug_info(page, engine_name, query)
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Playwright search failed with {engine_name}: {e}")
        
        return urls[:max_results]
    
    def _build_search_url(self, engine: Any, query: str, max_results: int) -> str:
        """Build search URL for specific engine."""
        encoded_query = quote_plus(query)
        
        # Engine-specific parameters
        if engine.name.lower() == "yahoo":
            params = engine.params.format(
                query=encoded_query,
                start=1,
                num=max_results
            )
        elif engine.name.lower() == "google":
            params = engine.params.format(
                query=encoded_query,
                num=max_results,
                hl="en",
                gl="au"
            )
        elif engine.name.lower() == "bing":
            params = engine.params.format(
                query=encoded_query,
                num=max_results,
                mkt="en-AU"
            )
        elif engine.name.lower() == "duckduckgo":
            params = engine.params.format(
                query=encoded_query,
                kl="au-en"
            )
        elif engine.name.lower() == "yandex":
            params = engine.params.format(
                query=encoded_query,
                lr="84"  # Australia
            )
        else:
            params = f"q={encoded_query}"
        
        return f"{engine.base_url}?{params}"
    
    async def _extract_urls_from_page(self, page: Any, engine_name: str) -> List[str]:
        """Extract URLs from search results page."""
        urls = []
        
        try:
            # Engine-specific selectors
            if engine_name.lower() == "yahoo":
                selectors = [
                    '.compTitle a[href*="http"]',
                    '.dd.algo a[href*="http"]',
                    '.ac-algo a[href*="http"]'
                ]
            elif engine_name.lower() == "google":
                selectors = [
                    'a[href*="http"]:not([href*="google.com"])',
                    'a[data-ved]',
                    '.g a[href*="http"]'
                ]
            elif engine_name.lower() == "bing":
                selectors = [
                    '.b_algo a[href*="http"]',
                    '.b_title a[href*="http"]'
                ]
            elif engine_name.lower() == "duckduckgo":
                selectors = [
                    '.result__url',
                    '.result__title a[href*="http"]'
                ]
            elif engine_name.lower() == "yandex":
                selectors = [
                    '.serp-item a[href*="http"]',
                    '.organic a[href*="http"]'
                ]
            else:
                selectors = ['a[href*="http"]']
            
            # Try each selector
            for selector in selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and self._is_valid_url(href):
                            urls.append(href)
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            return unique_urls
            
        except Exception as e:
            logger.error(f"URL extraction failed: {e}")
            return []
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid for our purposes."""
        if not url or not isinstance(url, str):
            return False
        
        # Must be HTTP/HTTPS
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Skip common non-content URLs
        skip_patterns = [
            'google.com', 'bing.com', 'duckduckgo.com', 'yandex.com', 'yahoo.com',
            'facebook.com', 'twitter.com', 'linkedin.com',
            'youtube.com', 'instagram.com'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False
        
        return True
    
    def _is_blocked(self, content: str) -> bool:
        """Check if we're being blocked by the search engine."""
        blocking_keywords = [
            "captcha", "unusual traffic", "robot", "verify you are human",
            "blocked", "access denied", "rate limit", "too many requests",
            "suspicious activity", "automated requests", "bot detection"
        ]
        
        content_lower = content.lower()
        for keyword in blocking_keywords:
            if keyword in content_lower:
                return True
        
        return False
    
    def _diagnose_search_failure(self, content: str, engine_name: str) -> str:
        """Diagnose why a search failed."""
        content_lower = content.lower()
        
        # Check for blocking
        if self._is_blocked(content):
            return "BLOCKED - Search engine is blocking requests"
        
        # Check for no results
        no_results_indicators = [
            "no results", "no matches", "didn't find", "0 results",
            "try again", "refine your search", "no pages found"
        ]
        
        for indicator in no_results_indicators:
            if indicator in content_lower:
                return "NO_RESULTS - Search returned no results"
        
        # Check for connection issues
        if "connection" in content_lower and ("error" in content_lower or "failed" in content_lower):
            return "CONNECTION_ERROR - Network connection failed"
        
        # Check for timeout
        if "timeout" in content_lower or "timed out" in content_lower:
            return "TIMEOUT - Request timed out"
        
        # Check for rate limiting
        if "rate limit" in content_lower or "too many" in content_lower:
            return "RATE_LIMITED - Too many requests"
        
        # Check if page loaded but no search results
        if "search" in content_lower and len(content) < 1000:
            return "INCOMPLETE_PAGE - Page loaded but appears incomplete"
        
        return "UNKNOWN - Unknown failure reason"
    
    async def _save_debug_info(self, page: Any, engine_name: str, query: str):
        """Save debug information for troubleshooting."""
        try:
            debug_dir = Path("debug/discovery/outputs")
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            # Save HTML
            html_file = debug_dir / f"{engine_name}_last_search.html"
            content = await page.content()
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Save screenshot
            screenshot_file = debug_dir / f"{engine_name}_last_search.png"
            await page.screenshot(path=str(screenshot_file))
            
            logger.debug(f"  💾 Saved debug info: {html_file}, {screenshot_file}")
            
        except Exception as e:
            logger.debug(f"Failed to save debug info: {e}")


# Example usage
async def test_web_search():
    """Test the web search discovery."""
    from src.configs.settings_manager import YamlSettingsManager
    
    settings_manager = YamlSettingsManager()
    discovery = WebSearchDiscovery(settings_manager)
    
    # Test with ANZ
    results = await discovery.discover_lender_pages(
        lender_name="ANZ",
        lender_domain="anz.com.au"
    )
    
    print("Search Results:")
    for category, urls in results.items():
        print(f"\n{category}:")
        for url in urls:
            print(f"  - {url}")


if __name__ == "__main__":
    asyncio.run(test_web_search())
