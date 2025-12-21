"""
Backward compatibility module for GoogleSearchDiscovery.

This module provides backward compatibility for existing code that imports
GoogleSearchDiscovery. It now uses the new modular search system.
"""

from .search_discovery import SearchDiscovery

# Backward compatibility aliases
GoogleSearchDiscovery = SearchDiscovery
WebSearchDiscovery = SearchDiscovery


# Example usage
async def discover_lender_urls_example():
    """Example of using multi-engine search to discover lender URLs."""
    discovery = SearchDiscovery()
    
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