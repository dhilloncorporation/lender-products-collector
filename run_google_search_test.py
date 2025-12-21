#!/usr/bin/env python3
"""
Quick test runner for Google Custom Search API.

This script provides a simple way to test if Google Custom Search is working
without running the full test suite.

Usage:
    python run_google_search_test.py

Requirements:
    - Set CUSTOM_SEARCH_API_KEY and CUSTOM_SEARCH_CX environment variables
    - Or create a .env file with these variables
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def quick_test():
    """Quick test of Google Custom Search functionality."""
    print("🚀 Quick Google Custom Search Test")
    print("-" * 40)
    
    # Check environment variables
    api_key = os.getenv("CUSTOM_SEARCH_API_KEY")
    search_engine_id = os.getenv("CUSTOM_SEARCH_CX")
    
    if not api_key or not search_engine_id:
        print("❌ Missing required environment variables:")
        if not api_key:
            print("   - CUSTOM_SEARCH_API_KEY")
        if not search_engine_id:
            print("   - CUSTOM_SEARCH_CX")
        print("\nPlease set these in your .env file or environment.")
        return False
    
    print(f"✅ API Key: {api_key[:10]}...")
    print(f"✅ Search Engine ID: {search_engine_id[:20]}...")
    
    try:
        # Import and test
        from src.agents.discovery.google_custom_search import GoogleCustomSearchAPI
        
        print("\n🔍 Testing Google Custom Search API...")
        api = GoogleCustomSearchAPI()
        
        # Simple search test
        result = await api.search("site:commbank.com.au home loan", num_results=2)
        
        print(f"✅ Search successful!")
        print(f"   Found {len(result['urls'])} URLs")
        print(f"   Queries used: {result['queries_used']}/{api.daily_limit}")
        
        if result['urls']:
            print("\n📋 Sample URLs:")
            for i, url in enumerate(result['urls'][:2], 1):
                print(f"   {i}. {url}")
        
        print("\n🎉 Google Custom Search API is working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your API key is correct")
        print("2. Check your Search Engine ID is correct")
        print("3. Make sure Custom Search API is enabled in Google Cloud Console")
        print("4. Check your API key has the correct permissions")
        return False

if __name__ == "__main__":
    # Try to load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available, use system env vars
    
    success = asyncio.run(quick_test())
    sys.exit(0 if success else 1)
