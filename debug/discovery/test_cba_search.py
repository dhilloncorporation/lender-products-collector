"""
Test Google search for CBA using Playwright.
"""

import asyncio
import sys
import os
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.agents.discovery.google_search_discovery import GoogleSearchDiscovery


async def test_cba_search():
    """Test Google search for CBA."""
    
    print("🔍 Testing Google Search with Playwright for CBA")
    print("="*80)
    
    discovery = GoogleSearchDiscovery()
    
    # Test CBA discovery
    print("\n📡 Discovering CBA pages...\n")
    
    cba_pages = await discovery.discover_lender_pages(
        lender_name="Commonwealth Bank",
        lender_domain="commbank.com.au"
    )
    
    print("\n" + "="*80)
    print("📊 Results for CBA:")
    print("="*80)
    
    for category, urls in cba_pages.items():
        print(f"\n{category}:")
        if urls:
            for url in urls:
                print(f"  ✅ {url}")
        else:
            print(f"  ❌ No URLs found")
    
    total_urls = sum(len(urls) for urls in cba_pages.values())
    print(f"\n📈 Total URLs discovered: {total_urls}")
    
    if total_urls > 0:
        print("\n✅ SUCCESS! Google search working with Playwright")
    else:
        print("\n⚠️  No URLs found - Google may be blocking or query needs adjustment")


if __name__ == "__main__":
    asyncio.run(test_cba_search())
