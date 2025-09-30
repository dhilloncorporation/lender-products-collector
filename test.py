"""
Test script for Playwright collector agent.

This script tests the PlaywrightCollectorAgent by scraping a sample lender website.
For production use, run: python run_collection.py
"""

import asyncio
import json
import sys
from typing import List, Dict, Any

try:
    from src.agents.collector.playwright_collector import PlaywrightCollectorAgent
    from src.services.json_storage import JSONStorageService
except Exception as import_error:
    print("Error: Required modules not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    print("For Playwright: playwright install", file=sys.stderr)
    raise


# Sample lender configuration for testing
# In production, this comes from src/configs/lenders.json
TEST_LENDER = {
    "name": "ANZ",
    "urls": [
        {
            "url": "https://www.anz.com.au/personal/home-loans/interest-rates/",
            "type": "rates_table",
            "description": "Current interest rates with LVR brackets"
        }
    ]
}


async def test_collector() -> Dict[str, Any]:
    """Test the Playwright collector agent with a sample lender."""
    print("="*80)
    print("Testing Playwright Collector Agent")
    print("="*80)
    print(f"\nLender: {TEST_LENDER['name']}")
    print(f"URLs to scrape: {len(TEST_LENDER['urls'])}\n")
    
    all_products = []
    results = []
    
    async with PlaywrightCollectorAgent(headless=True) as collector:
        for url_config in TEST_LENDER['urls']:
            url = url_config["url"]
            url_type = url_config["type"]
            description = url_config["description"]
            
            try:
                print(f"📡 Scraping: {url}")
                print(f"   Type: {url_type}")
                print(f"   Description: {description}")
                
                products = await collector.collect_from_url(
                    url=url,
                    lender_name=TEST_LENDER['name']
                )
                
                # Convert to dict for JSON output
                products_data = [p.model_dump() for p in products]
                all_products.extend(products)
                
                results.append({
                    "url": url,
                    "type": url_type,
                    "description": description,
                    "products_found": len(products_data),
                    "status": "success"
                })
                
                print(f"   ✅ Found {len(products_data)} products\n")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}\n", file=sys.stderr)
                results.append({
                    "url": url,
                    "type": url_type,
                    "description": description,
                    "products_found": 0,
                    "status": "error",
                    "error": str(e)
                })
    
    # Optionally save to JSON storage
    if all_products:
        print("💾 Saving to JSON storage...")
        storage = JSONStorageService()
        try:
            await storage.save_current_products(
                products=all_products,
                lender=TEST_LENDER['name']
            )
            print(f"   ✅ Saved to data/current/by_lender/{TEST_LENDER['name']}.json\n")
        except Exception as e:
            print(f"   ⚠️  Storage error: {e}\n")
    
    print("="*80)
    print("Test Complete")
    print("="*80)
    print(f"\nTotal products collected: {len(all_products)}")
    print(f"Successful URLs: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Failed URLs: {sum(1 for r in results if r['status'] == 'error')}")
    
    return {
        "lender": TEST_LENDER['name'],
        "total_products": len(all_products),
        "results": results,
        "products": [p.model_dump() for p in all_products]
    }


if __name__ == "__main__":
    print("\n🚀 Starting collector test...")
    print("💡 Tip: For production use, run: python run_collection.py\n")
    
    data = asyncio.run(test_collector())
    
    # Pretty print summary
    print("\n📄 JSON Output:")
    print(json.dumps({
        "lender": data["lender"],
        "total_products": data["total_products"],
        "results": data["results"]
    }, indent=2))
    
    # Save full output to file
    with open("test_output.json", "w") as f:
        json.dump(data, f, indent=2)
    print("\n💾 Full output saved to: test_output.json")


