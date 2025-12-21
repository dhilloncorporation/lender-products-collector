"""
Google Custom Search API implementation.

This module provides a compliant, fast, and reliable way to search Google
using the official Custom Search JSON API. No bot detection, no rate limiting
issues, just clean JSON responses.

Setup:
1. Enable customsearch.googleapis.com in Google Cloud Console
2. Create API key and restrict to Custom Search API
3. Create Programmable Search Engine (CSE) and note the CSE ID
4. Set environment variables: CUSTOM_SEARCH_API_KEY and CUSTOM_SEARCH_CX
"""

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus
import httpx

logger = logging.getLogger(__name__)


class GoogleCustomSearchAPI:
    """Google Custom Search API client."""
    
    def __init__(self, settings_manager=None):
        """Initialize the Google Custom Search API client."""
        self.settings_manager = settings_manager
        
        # Get API credentials from environment
        self.api_key = os.getenv("CUSTOM_SEARCH_API_KEY")
        self.search_engine_id = os.getenv("CUSTOM_SEARCH_CX")
        
        if not self.api_key:
            raise ValueError("CUSTOM_SEARCH_API_KEY environment variable not set")
        if not self.search_engine_id:
            raise ValueError("CUSTOM_SEARCH_CX environment variable not set")
        
        # API configuration
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.timeout = 30
        self.max_results = 10
        
        # Rate limiting
        self.daily_limit = 100
        self.cost_per_1000 = 5.00
        self.queries_today = 0
        
        logger.info(f"Google Custom Search API initialized (Daily limit: {self.daily_limit})")
    
    async def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Search using Google Custom Search API.
        
        Args:
            query: Search query string
            num_results: Number of results to return (max 10)
            
        Returns:
            Dictionary with search results and metadata
        """
        if self.queries_today >= self.daily_limit:
            raise Exception(f"Daily limit reached ({self.daily_limit} queries)")
        
        # Prepare request
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(num_results, 10),  # API max is 10
            "gl": "au",  # Country: Australia
            "hl": "en",  # Language: English
            "safe": "off",  # Include all results
            "fields": "items(title,link,snippet),searchInformation(totalResults)"
        }
        
        logger.info(f"🔍 Google Custom Search: {query}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                self.queries_today += 1
                
                # Extract results
                results = {
                    "query": query,
                    "total_results": data.get("searchInformation", {}).get("totalResults", "0"),
                    "items": data.get("items", []),
                    "urls": [item["link"] for item in data.get("items", [])],
                    "engine": "google_custom_search",
                    "queries_used": self.queries_today,
                    "queries_remaining": self.daily_limit - self.queries_today
                }
                
                logger.info(f"✅ Found {len(results['urls'])} results ({results['total_results']} total)")
                return results
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                error_msg = "Google Custom Search API quota exceeded or API key invalid"
            elif e.response.status_code == 400:
                error_msg = "Invalid search request parameters"
            else:
                error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            
            logger.error(f"❌ Google Custom Search API error: {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            logger.error(f"❌ Google Custom Search API error: {str(e)}")
            raise
    
    async def discover_lender_pages(self, lender_name: str, lender_domain: str) -> Dict[str, List[str]]:
        """
        Discover lender pages using multiple search templates.
        
        Args:
            lender_name: Name of the lender (e.g., "Commonwealth Bank")
            lender_domain: Domain of the lender (e.g., "commbank.com.au")
            
        Returns:
            Dictionary with categorized URLs
        """
        logger.info(f"🔍 Discovering pages for {lender_name} ({lender_domain})")
        
        # Search templates from config
        templates = {
            "interest_rates": f'site:{lender_domain} "home loan rates" OR "mortgage rates"',
            "products": f'site:{lender_domain} "home loan products" OR "our home loans"',
            "comparison": f'site:{lender_domain} "home loan" compare OR comparison',
            "fees": f'site:{lender_domain} "home loan" fees OR charges',
            "rates_alt": f'site:{lender_domain} inurl:rates "home loans"',
            "products_alt": f'site:{lender_domain} inurl:"home-loans" intitle:"products"'
        }
        
        discovered_pages = {
            "interest_rates": [],
            "products": [],
            "comparison": [],
            "fees": []
        }
        
        # Search each template
        for category, query in templates.items():
            try:
                logger.info(f"  🔍 Searching: {category}")
                results = await self.search(query, num_results=5)
                
                # Categorize results
                if category in ["interest_rates", "rates_alt"]:
                    discovered_pages["interest_rates"].extend(results["urls"])
                elif category in ["products", "products_alt"]:
                    discovered_pages["products"].extend(results["urls"])
                elif category == "comparison":
                    discovered_pages["comparison"].extend(results["urls"])
                elif category == "fees":
                    discovered_pages["fees"].extend(results["urls"])
                
                # Small delay between queries
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"  ⚠️  Search failed for {category}: {str(e)}")
                continue
        
        # Remove duplicates and filter
        for category in discovered_pages:
            urls = discovered_pages[category]
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in urls:
                if url not in seen and self._is_valid_lender_url(url, lender_domain):
                    seen.add(url)
                    unique_urls.append(url)
            discovered_pages[category] = unique_urls[:3]  # Limit to 3 per category
        
        # Log results
        total_urls = sum(len(urls) for urls in discovered_pages.values())
        logger.info(f"✅ Discovered {total_urls} total URLs for {lender_name}")
        for category, urls in discovered_pages.items():
            if urls:
                logger.info(f"  {category}: {len(urls)} URLs")
                for url in urls:
                    logger.info(f"    - {url}")
        
        return discovered_pages
    
    def _is_valid_lender_url(self, url: str, lender_domain: str) -> bool:
        """Check if URL is valid for the lender."""
        if not url or not isinstance(url, str):
            return False
        
        # Must contain the lender domain
        if lender_domain not in url:
            return False
        
        # Skip certain file types and paths
        skip_patterns = [
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$',
            r'/(pdf|documents?|files?)/',
            r'/(privacy|terms|cookies|legal)/',
            r'/(contact|about|careers|investor)/',
            r'/(login|signin|register|account)/',
            r'/(search|sitemap|robots)',
            r'/#',  # Fragment URLs
            r'\?.*utm_',  # UTM tracking URLs
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "queries_used": self.queries_today,
            "queries_remaining": self.daily_limit - self.queries_today,
            "daily_limit": self.daily_limit,
            "cost_per_1000": self.cost_per_1000,
            "estimated_cost": (self.queries_today / 1000) * self.cost_per_1000
        }


# Example usage
async def test_google_custom_search():
    """Test the Google Custom Search API."""
    try:
        api = GoogleCustomSearchAPI()
        
        # Test basic search
        results = await api.search("site:commbank.com.au home loan rates")
        print(f"Found {len(results['urls'])} results")
        for url in results['urls']:
            print(f"  - {url}")
        
        # Test lender discovery
        pages = await api.discover_lender_pages("Commonwealth Bank", "commbank.com.au")
        print(f"\nDiscovered pages:")
        for category, urls in pages.items():
            print(f"  {category}: {len(urls)} URLs")
        
        # Show usage stats
        stats = api.get_usage_stats()
        print(f"\nUsage: {stats['queries_used']}/{stats['daily_limit']} queries used")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_google_custom_search())
