#!/usr/bin/env python3
"""
Simple test script to verify Google Custom Search API works.

This script tests the Google Custom Search API implementation without
running the full test suite. It's useful for quick verification.

Usage:
    python test_google_custom_search.py

Make sure you have set the environment variables:
    CUSTOM_SEARCH_API_KEY=your_api_key_here
    CUSTOM_SEARCH_CX=your_search_engine_id_here
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agents.discovery.google_custom_search import GoogleCustomSearchAPI
from src.agents.discovery.web_search_discovery import WebSearchDiscovery
from src.configs.settings_manager import YamlSettingsManager


async def test_google_custom_search_api():
    """Test Google Custom Search API directly."""
    print("🔍 Testing Google Custom Search API...")
    
    # Check environment variables
    api_key = os.getenv("CUSTOM_SEARCH_API_KEY")
    search_engine_id = os.getenv("CUSTOM_SEARCH_CX")
    
    if not api_key:
        print("❌ CUSTOM_SEARCH_API_KEY environment variable not set")
        print("   Please set it in your .env file or environment")
        return False
    
    if not search_engine_id:
        print("❌ CUSTOM_SEARCH_CX environment variable not set")
        print("   Please set it in your .env file or environment")
        return False
    
    print(f"✅ API Key: {api_key[:10]}...")
    print(f"✅ Search Engine ID: {search_engine_id}")
    
    try:
        # Initialize API
        api = GoogleCustomSearchAPI()
        print("✅ Google Custom Search API initialized successfully")
        
        # Test basic search
        print("\n🔍 Testing basic search...")
        result = await api.search("site:commbank.com.au home loan rates", num_results=3)
        
        print(f"✅ Search completed successfully")
        print(f"   Query: {result['query']}")
        print(f"   Total results: {result['total_results']}")
        print(f"   URLs found: {len(result['urls'])}")
        print(f"   Queries used: {result['queries_used']}")
        print(f"   Queries remaining: {result['queries_remaining']}")
        
        if result['urls']:
            print("\n📋 Found URLs:")
            for i, url in enumerate(result['urls'], 1):
                print(f"   {i}. {url}")
        else:
            print("⚠️  No URLs found in search results")
        
        # Test lender page discovery
        print("\n🔍 Testing lender page discovery...")
        pages = await api.discover_lender_pages("Commonwealth Bank", "commbank.com.au")
        
        total_urls = sum(len(urls) for urls in pages.values())
        print(f"✅ Discovered {total_urls} total URLs across all categories")
        
        for category, urls in pages.items():
            if urls:
                print(f"   {category}: {len(urls)} URLs")
                for url in urls[:2]:  # Show first 2 URLs
                    print(f"     - {url}")
                if len(urls) > 2:
                    print(f"     ... and {len(urls) - 2} more")
        
        # Show usage stats
        stats = api.get_usage_stats()
        print(f"\n📊 Usage Statistics:")
        print(f"   Queries used: {stats['queries_used']}")
        print(f"   Queries remaining: {stats['queries_remaining']}")
        print(f"   Daily limit: {stats['daily_limit']}")
        print(f"   Estimated cost: ${stats['estimated_cost']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Google Custom Search API: {e}")
        return False


async def test_web_search_discovery_integration():
    """Test WebSearchDiscovery integration with Google Custom Search."""
    print("\n🔍 Testing WebSearchDiscovery integration...")
    
    try:
        # Load settings
        settings_manager = YamlSettingsManager()
        print("✅ Settings manager loaded")
        
        # Initialize discovery
        discovery = WebSearchDiscovery(settings_manager)
        print("✅ WebSearchDiscovery initialized")
        
        # Check if Google Custom Search is available
        if discovery.google_custom_search:
            print("✅ Google Custom Search API is configured and available")
        else:
            print("⚠️  Google Custom Search API not available, will use fallback engines")
        
        # Test discovery
        print("\n🔍 Testing lender discovery...")
        result = await discovery.discover_lender_pages("Commonwealth Bank", "commbank.com.au")
        
        total_urls = sum(len(urls) for urls in result.values())
        print(f"✅ Discovery completed: {total_urls} total URLs found")
        
        for category, urls in result.items():
            if urls:
                print(f"   {category}: {len(urls)} URLs")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing WebSearchDiscovery integration: {e}")
        return False


async def main():
    """Main test function."""
    print("🚀 Google Custom Search API Test")
    print("=" * 50)
    
    # Test 1: Direct API test
    api_success = await test_google_custom_search_api()
    
    # Test 2: Integration test
    integration_success = await test_web_search_discovery_integration()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   Google Custom Search API: {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"   WebSearchDiscovery Integration: {'✅ PASS' if integration_success else '❌ FAIL'}")
    
    if api_success and integration_success:
        print("\n🎉 All tests passed! Google Custom Search is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
        return 1


if __name__ == "__main__":
    # Load environment variables from .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment variables")
    except Exception as e:
        print(f"⚠️  Could not load .env file: {e}")
    
    # Run tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
