"""
Yahoo search engine implementation.
"""

import logging
from typing import List, Dict, Any
from urllib.parse import quote_plus
import re
from pathlib import Path
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class YahooSearchEngine:
    """Yahoo search engine implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Yahoo search engine with configuration."""
        self.config = config
        self.name = config.get('name', 'Yahoo')
        self.base_url = config.get('base_url', 'https://search.yahoo.com/search')
        self.params = config.get('params', 'p={query}&n={num}')
        self.user_agent = config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        self.timeout_seconds = config.get('timeout_seconds', 15)
        self.rate_limit_per_hour = config.get('rate_limit_per_hour', 120)
    
    def build_search_url(self, query: str, max_results: int = 5) -> str:
        """Build Yahoo search URL."""
        encoded_query = quote_plus(query)
        return f"{self.base_url}?p={encoded_query}&n={max_results}"
    
    async def extract_results(self, page) -> List[str]:
        """Extract URLs from Yahoo search results."""
        urls = []
        
        # Yahoo uses different selectors
        result_links = await page.query_selector_all('a[href]')
        logger.debug(f"Found {len(result_links)} total links on Yahoo page")
        
        for link in result_links:
            href = await link.get_attribute('href')
            if not href:
                continue
            
            # Yahoo result format: /search?p=...&fr=...&u=ACTUAL_URL
            if '/u=' in href:
                match = re.search(r'/u=(https?://[^&]+)', href)
                if match:
                    from urllib.parse import unquote
                    url = unquote(match.group(1))
                    if not any(domain in url for domain in ['yahoo.com', 'google.com', 'youtube.com', 'facebook.com']):
                        urls.append(url)
                        logger.debug(f"Extracted Yahoo URL: {url}")
            
            # Direct URLs
            elif href.startswith('http') and 'yahoo.com' not in href:
                urls.append(href)
                logger.debug(f"Extracted direct Yahoo URL: {href}")
        
        # Remove duplicates
        return list(dict.fromkeys(urls))
    
    async def search(self, query: str, max_results: int = 5) -> List[str]:
        """Perform search using Playwright."""
        urls = []
        
        try:
            search_url = self.build_search_url(query, max_results)
            logger.debug(f"{self.name} search URL: {search_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent
                await page.set_extra_http_headers({"User-Agent": self.user_agent})
                
                try:
                    # Navigate to search page
                    logger.debug(f"Navigating to {self.name}...")
                    response = await page.goto(search_url, wait_until='domcontentloaded', timeout=self.timeout_seconds * 1000)
                    
                    logger.debug(f"Response status: {response.status}")
                    logger.debug(f"Final URL: {page.url}")
                    
                    # Wait for results to load
                    await page.wait_for_timeout(2000)
                    
                    # Save HTML for debugging
                    html_file = Path(f"debug/discovery/outputs/{self.name.lower()}_last_search.html")
                    html_file.parent.mkdir(parents=True, exist_ok=True)
                    page_content = await page.content()
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(page_content)
                    logger.debug(f"💾 Saved {self.name} response to: {html_file}")
                    
                    # Take screenshot
                    screenshot_file = Path(f"debug/discovery/outputs/{self.name.lower()}_last_search.png")
                    await page.screenshot(path=str(screenshot_file))
                    logger.debug(f"📸 Saved screenshot to: {screenshot_file}")
                    
                    # Extract results
                    urls = await self.extract_results(page)
                    logger.info(f"Extracted {len(urls)} URLs from {self.name}")
                    
                finally:
                    await browser.close()
        
        except Exception as e:
            logger.error(f"{self.name} search failed: {e}")
        
        return urls
