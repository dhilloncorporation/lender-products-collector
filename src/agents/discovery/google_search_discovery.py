"""
Google search-based discovery agent for finding lender product pages.

Instead of maintaining static URLs, this agent uses Google search to find:
- Interest rate pages
- Product comparison pages
- Fee schedules
- Rate cards

This makes the system self-healing - if banks change URLs, search finds them.

Uses Playwright (not httpx) to avoid bot detection.
"""

import logging
from typing import List, Dict, Any
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class GoogleSearchDiscovery:
    """Discover lender product pages using Google search."""
    
    # Better search templates with intitle for precision
    SEARCH_TEMPLATES = {
        "interest_rates": 'site:{domain} intitle:"home loan" interest rates',
        "products": 'site:{domain} intitle:"home loans" products',
        "comparison": 'site:{domain} intitle:"home loans" compare',
        "fees": 'site:{domain} "home loan" fees OR charges',
        "rates_alt": 'site:{domain} intitle:"home loan" rate',
    }
    
    def __init__(self):
        """Initialize the discovery agent."""
        # Stable desktop Chrome User-Agent
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    
    async def discover_lender_pages(
        self, 
        lender_name: str,
        lender_domain: str = None
    ) -> Dict[str, List[str]]:
        """
        Discover relevant pages for a lender using Google search.
        
        Args:
            lender_name: Name of the lender (e.g., "Commonwealth Bank")
            lender_domain: Optional domain to restrict search (e.g., "commbank.com.au")
        
        Returns:
            Dict with discovered URLs by category:
            {
                "interest_rates": [...],
                "products": [...],
                "fees": [...]
            }
        """
        discovered_pages = {
            "interest_rates": [],
            "products": [],
            "fees": [],
            "comparison": []
        }
        
        # Use improved search templates
        search_queries = {}
        
        if lender_domain:
            # Use precise templates with intitle
            for key, template in self.SEARCH_TEMPLATES.items():
                search_queries[key] = template.format(domain=lender_domain)
        else:
            # Fallback to basic queries without site restriction
            search_queries = {
                "interest_rates": f"{lender_name} home loan interest rates",
                "products": f"{lender_name} home loan products",
                "fees": f"{lender_name} home loan fees charges",
                "comparison": f"{lender_name} compare home loans"
            }
        
        # Use Playwright for searching to avoid bot detection
        import asyncio
        
        for i, (category, query) in enumerate(search_queries.items()):
            try:
                # Add delay between searches to avoid rate limiting
                if i > 0:
                    delay = 5  # 5 seconds between searches
                    logger.debug(f"Waiting {delay}s before next search (rate limit prevention)...")
                    await asyncio.sleep(delay)
                
                logger.info(f"Searching for {lender_name} {category}...")
                urls = await self._search_google_with_playwright(query, max_results=3)
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
    
    async def _search_google_with_playwright(
        self, 
        query: str, 
        max_results: int = 5
    ) -> List[str]:
        """
        Perform Google search using Playwright to avoid bot detection.
        
        Playwright appears as a real browser, bypassing most anti-bot measures.
        """
        urls = []
        
        try:
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&num={max_results}"
            
            logger.debug(f"Google search URL: {search_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    # Navigate to Google search
                    logger.debug("Navigating to Google...")
                    response = await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
                    
                    # DIAGNOSIS: Log response status
                    logger.debug(f"Response status: {response.status}")
                    logger.debug(f"Final URL: {page.url}")
                    
                    # Wait for results to load
                    await page.wait_for_timeout(2000)
                    
                    # DIAGNOSIS: Check page title and content
                    title = await page.title()
                    logger.debug(f"Page title: {title}")
                    
                    # DIAGNOSIS: Check for CAPTCHA or blocking
                    page_content = await page.content()
                    
                    # ALWAYS save HTML for debugging
                    from pathlib import Path
                    html_file = Path("debug/discovery/outputs/google_last_search.html")
                    html_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(page_content)
                    logger.debug(f"💾 Saved Google response to: {html_file}")
                    
                    # Take screenshot for visual debugging
                    screenshot_file = Path("debug/discovery/outputs/google_last_search.png")
                    await page.screenshot(path=str(screenshot_file))
                    logger.debug(f"📸 Saved screenshot to: {screenshot_file}")
                    
                    if 'captcha' in page_content.lower():
                        logger.warning("⚠️  CAPTCHA detected - Google is blocking automated access")
                        logger.warning(f"   Check {html_file} for details")
                        return []
                    
                    if 'unusual traffic' in page_content.lower():
                        logger.warning("⚠️  'Unusual traffic' message - Google rate limiting detected")
                        logger.warning(f"   Check {html_file} for details")
                        return []
                    
                    # Extract links from search results
                    result_links = await page.query_selector_all('a[href]')
                    logger.debug(f"Found {len(result_links)} total links on page")
                    
                    import re
                    candidate_urls = []
                    
                    for link in result_links:
                        href = await link.get_attribute('href')
                        
                        if not href:
                            continue
                        
                        # Extract actual URL from Google redirect format
                        # Format: /url?q=ACTUAL_URL&...
                        if '/url?q=' in href:
                            match = re.search(r'/url\?q=(https?://[^&]+)', href)
                            if match:
                                from urllib.parse import unquote
                                url = unquote(match.group(1))
                                candidate_urls.append(url)
                                
                                # Filter out Google's own URLs
                                if not any(domain in url for domain in ['google.com', 'youtube.com', 'facebook.com', 'maps.google']):
                                    urls.append(url)
                                    logger.debug(f"Extracted URL: {url}")
                        
                        # Direct URLs (new Google format)
                        elif href.startswith('http') and 'google.com' not in href:
                            candidate_urls.append(href)
                            urls.append(href)
                            logger.debug(f"Extracted direct URL: {href}")
                    
                    # Remove duplicates
                    urls = list(dict.fromkeys(urls))[:max_results]
                    
                    # DIAGNOSIS: Log extraction results
                    logger.info(f"Extracted {len(urls)} URLs from {len(candidate_urls)} candidates")
                    if len(urls) == 0 and len(candidate_urls) > 0:
                        logger.warning(f"Found {len(candidate_urls)} candidates but all were filtered out")
                
                finally:
                    await browser.close()
        
        except Exception as e:
            logger.error(f"Playwright Google search failed: {e}")
        
        return urls
    
    def generate_search_query(
        self, 
        lender_name: str, 
        page_type: str,
        lender_domain: str = None
    ) -> str:
        """
        Generate optimized search query for finding lender pages.
        
        Args:
            lender_name: Name of lender
            page_type: Type of page ("rates", "products", "fees", "comparison")
            lender_domain: Optional domain restriction
        
        Returns:
            Optimized search query
        """
        query_templates = {
            "rates": f"{lender_name} home loan interest rates",
            "products": f"{lender_name} home loan products compare",
            "fees": f"{lender_name} home loan fees and charges",
            "comparison": f"{lender_name} home loan comparison table",
            "calculator": f"{lender_name} home loan calculator",
            "eligibility": f"{lender_name} home loan eligibility criteria"
        }
        
        base_query = query_templates.get(page_type, f"{lender_name} home loans")
        
        # Add site restriction if provided
        if lender_domain:
            return f"site:{lender_domain} {base_query}"
        
        return base_query


# Example usage
async def discover_lender_urls_example():
    """Example of using Google search to discover lender URLs."""
    discovery = GoogleSearchDiscovery()
    
    # For CBA
    cba_pages = await discovery.discover_lender_pages(
        lender_name="Commonwealth Bank",
        lender_domain="commbank.com.au"
    )
    
    print("CBA Discovered Pages:")
    for category, urls in cba_pages.items():
        print(f"\n{category}:")
        for url in urls:
            print(f"  - {url}")
    
    return cba_pages


if __name__ == "__main__":
    import asyncio
    asyncio.run(discover_lender_urls_example())
