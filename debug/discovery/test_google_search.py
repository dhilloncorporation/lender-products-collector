"""
Test Google search and save the HTML response to debug why URL extraction fails.
"""

import asyncio
import httpx
from pathlib import Path
from urllib.parse import quote_plus
import re


OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


async def test_google_search():
    """Test Google search and save response."""
    
    # Test query
    query = 'site:anz.com.au intitle:"home loan" interest rates'
    encoded_query = quote_plus(query)
    search_url = f"https://www.google.com/search?q={encoded_query}&num=5"
    
    print("🔍 Testing Google Search")
    print("="*80)
    print(f"Query: {query}")
    print(f"URL: {search_url}\n")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
    }
    
    params = {
        "hl": "en",
        "gl": "au"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("📡 Sending request to Google...")
            response = await client.get(
                search_url,
                headers=headers,
                params=params,
                follow_redirects=True,
                timeout=20.0
            )
            
            print(f"✅ Response received: {response.status_code}\n")
            
            # Save HTML for inspection
            html_file = OUTPUT_DIR / "google_response.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"💾 Saved Google HTML to: {html_file}\n")
            
            # Try the current regex pattern
            print("🔍 Trying current regex pattern: r'/url\\?q=(https?://[^&]+)'")
            matches = re.findall(r'/url\?q=(https?://[^&]+)', response.text)
            print(f"   Found {len(matches)} matches")
            for url in matches[:5]:
                print(f"      - {url}")
            
            # Try alternative patterns
            print("\n🔍 Trying alternative pattern 1: r'<a href=\"(https?://[^\"]+)\"'")
            alt_matches1 = re.findall(r'<a href="(https?://[^"]+)"', response.text)
            print(f"   Found {len(alt_matches1)} matches")
            for url in alt_matches1[:5]:
                if 'anz.com' in url:
                    print(f"      - {url}")
            
            # Try pattern 2
            print("\n🔍 Trying alternative pattern 2: Look for anz.com.au URLs")
            alt_matches2 = re.findall(r'(https?://[^\s<>"]+anz\.com[^\s<>"]*)', response.text)
            print(f"   Found {len(alt_matches2)} matches")
            for url in alt_matches2[:5]:
                print(f"      - {url}")
            
            # Try pattern 3 - look in onclick or data attributes  
            print("\n🔍 Trying alternative pattern 3: data-attributes")
            alt_matches3 = re.findall(r'data-url="([^"]+)"', response.text)
            print(f"   Found {len(alt_matches3)} matches")
            
            print("\n" + "="*80)
            print("💡 Recommendations:")
            print(f"   1. Check {html_file} to see Google's actual HTML structure")
            print("   2. Search for 'anz.com.au' in the file to find URL format")
            print("   3. Update regex pattern in google_search_discovery.py")
            print("   4. Or consider using Google Custom Search API or SerpAPI")
            
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_google_search())
