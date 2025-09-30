"""
Extract ANZ products using ChatGPT's recommended approach:
1. Check for JSON-LD / structured data
2. Check for embedded state (window.__NEXT_DATA__, etc.)
3. Extract from select dropdowns (ANZ uses this!)
4. Fallback to DOM parsing

Based on our HTML analysis, ANZ embeds products in:
<select id="scenarioDialogue__InterestRate0">
  <option>6.49% p.a Standard Variable 80% or less LVR</option>
  <option>5.64% p.a Simplicity PLUS special offer discount 60% or less LVR*</option>
  ...
</select>
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright
from pathlib import Path


async def extract_anz_products():
    """Extract ANZ products using the dropdown strategy."""
    
    url = "https://www.anz.com.au/personal/home-loans/interest-rates/"
    
    print("🔍 Extracting ANZ Products - Smart Extraction Method")
    print("="*80)
    print(f"URL: {url}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("📡 Loading page...")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for JS to render
            print("✅ Page loaded\n")
            
            products = []
            
            # Strategy 1: Check for JSON-LD structured data
            print("🔍 Strategy 1: Looking for JSON-LD...")
            jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            
            for script in jsonld_scripts:
                try:
                    content = await script.inner_text()
                    data = json.loads(content)
                    if data.get("@type") in ["Product", "FinancialProduct"]:
                        print(f"   ✅ Found JSON-LD product: {data.get('name')}")
                        products.append(data)
                except:
                    pass
            
            if products:
                print(f"   Found {len(products)} products via JSON-LD\n")
            else:
                print("   ℹ️  No JSON-LD data found\n")
            
            # Strategy 2: Check for embedded state
            print("🔍 Strategy 2: Looking for embedded state...")
            embedded_state = await page.evaluate("""() => {
                return {
                    nextData: globalThis.__NEXT_DATA__ || null,
                    nuxt: globalThis.__NUXT__ || null,
                    dataLayer: globalThis.dataLayer || null
                };
            }""")
            
            if any(embedded_state.values()):
                print(f"   ✅ Found embedded state: {[k for k,v in embedded_state.items() if v]}")
            else:
                print("   ℹ️  No embedded state found\n")
            
            # Strategy 3: Extract from select dropdown (ANZ-specific!)
            print("🔍 Strategy 3: Extracting from interest rate dropdown...")
            
            # Find select element with interest rates
            rate_select = await page.query_selector('select[id*="InterestRate"]')
            
            if rate_select:
                print("   ✅ Found rate dropdown!")
                
                # Get all options
                options = await rate_select.query_selector_all('option')
                print(f"   Found {len(options)} options\n")
                
                anz_products = []
                
                for opt in options:
                    text = await opt.inner_text()
                    text = text.strip()
                    
                    # Skip "Please select" placeholder
                    if not text or 'Please select' in text:
                        continue
                    
                    # Parse: "6.49% p.a Standard Variable 80% or less LVR"
                    # Or: "5.64% p.a Simplicity PLUS special offer discount 60% or less LVR*"
                    match = re.match(r'([\d.]+)% p\.a\s+(.+?)(?:\s+([\d]+%.*LVR.*?))?$', text)
                    
                    if match:
                        rate = match.group(1)
                        product_name = match.group(2).strip()
                        lvr_info = match.group(3).strip() if match.group(3) else "No LVR specified"
                        
                        product = {
                            "lender": "ANZ",
                            "product_name": product_name,
                            "rate_percent": float(rate),
                            "lvr_bracket": lvr_info,
                            "raw_text": text,
                            "source_url": url,
                            "extraction_method": "select_dropdown"
                        }
                        
                        anz_products.append(product)
                        print(f"   ✓ {product_name}: {rate}% ({lvr_info})")
                
                products.extend(anz_products)
                
                print(f"\n   ✅ Extracted {len(anz_products)} products from dropdown!")
            else:
                print("   ❌ Rate dropdown not found")
            
            print("\n" + "="*80)
            print(f"✅ Total products extracted: {len(products)}")
            print("="*80)
            
            # Save results
            output_file = Path("debug/scraper/outputs/anz_extracted_products.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2)
            
            print(f"\n💾 Saved to: {output_file}")
            
            # Pretty print
            print("\n📊 Products Found:")
            for p in products:
                print(f"\n  Product: {p.get('product_name', p.get('name'))}")
                print(f"  Rate: {p.get('rate_percent', 'N/A')}%")
                print(f"  LVR: {p.get('lvr_bracket', 'N/A')}")
            
        finally:
            await browser.close()
    
    return products


if __name__ == "__main__":
    products = asyncio.run(extract_anz_products())
    print(f"\n🎉 Successfully extracted {len(products)} ANZ loan products!")
