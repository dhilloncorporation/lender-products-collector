"""
Batch analyze all major banks to find their data extraction patterns.

This script runs headless and generates analysis reports for each bank,
helping us understand which extraction strategy to use for each.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright


OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


async def analyze_bank(url: str, bank_name: str):
    """Analyze a single bank's website structure."""
    
    print(f"\n{'='*80}")
    print(f"Analyzing: {bank_name}")
    print(f"URL: {url}")
    print(f"{'='*80}")
    
    analysis = {
        "bank": bank_name,
        "url": url,
        "strategies_found": [],
        "recommended_strategy": None,
        "details": {}
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Headless for batch
        page = await browser.new_page()
        
        try:
            # Load page
            print(f"📡 Loading {bank_name}...")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)
            print("   ✅ Page loaded")
            
            # Strategy 1: Check for JSON-LD
            print("\n   🔍 Checking Strategy 1: JSON-LD...")
            jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            if jsonld_scripts:
                analysis["strategies_found"].append("json-ld")
                analysis["details"]["jsonld_count"] = len(jsonld_scripts)
                print(f"      ✅ Found {len(jsonld_scripts)} JSON-LD scripts")
                
                # Check if any contain product data
                for script in jsonld_scripts:
                    content = await script.inner_text()
                    if any(keyword in content for keyword in ['"Product"', '"FinancialProduct"', '"LoanOrCredit"']):
                        analysis["recommended_strategy"] = "json-ld"
                        print(f"      🎯 RECOMMENDED: Contains financial product data!")
                        break
            
            # Strategy 2: Check for embedded state
            print("\n   🔍 Checking Strategy 2: Embedded State...")
            state = await page.evaluate("""() => {
                return {
                    hasNextData: !!globalThis.__NEXT_DATA__,
                    hasNuxt: !!globalThis.__NUXT__,
                    hasDataLayer: !!globalThis.dataLayer,
                    hasShopify: !!globalThis.Shopify
                };
            }""")
            
            if any(state.values()):
                found_states = [k for k, v in state.items() if v]
                analysis["strategies_found"].append("embedded-state")
                analysis["details"]["embedded_state"] = found_states
                print(f"      ✅ Found: {found_states}")
                
                if not analysis["recommended_strategy"]:
                    analysis["recommended_strategy"] = "embedded-state"
                    print(f"      🎯 RECOMMENDED: Explore these state objects")
            
            # Strategy 3: Check for select dropdowns with rates
            print("\n   🔍 Checking Strategy 3: Select Dropdowns...")
            rate_selects = await page.query_selector_all('select[id*="Interest"], select[id*="interest"], select[id*="rate"], select[id*="Rate"]')
            
            dropdown_products = []
            for select_elem in rate_selects:
                options = await select_elem.query_selector_all('option')
                for opt in options:
                    text = await opt.inner_text()
                    if '% p.a' in text or '%p.a' in text:
                        dropdown_products.append(text.strip())
            
            if dropdown_products:
                analysis["strategies_found"].append("select-dropdown")
                analysis["details"]["dropdown_products"] = len(dropdown_products)
                print(f"      ✅ Found {len(dropdown_products)} products in dropdowns")
                print(f"         Samples:")
                for sample in dropdown_products[:3]:
                    print(f"           - {sample[:80]}")
                
                if not analysis["recommended_strategy"]:
                    analysis["recommended_strategy"] = "select-dropdown"
                    print(f"      🎯 RECOMMENDED: Use dropdown extraction (like ANZ)")
            
            # Strategy 4: Check for tables with rate data
            print("\n   🔍 Checking Strategy 4: HTML Tables...")
            tables = await page.query_selector_all('table')
            rate_tables = []
            
            for table in tables:
                html = await table.inner_html()
                if re.search(r'\d+\.\d+%|rate|LVR', html, re.IGNORECASE):
                    rate_tables.append(table)
            
            if rate_tables:
                analysis["strategies_found"].append("html-table")
                analysis["details"]["rate_tables"] = len(rate_tables)
                print(f"      ✅ Found {len(rate_tables)} tables with rate data")
                
                if not analysis["recommended_strategy"]:
                    analysis["recommended_strategy"] = "html-table"
                    print(f"      🎯 RECOMMENDED: Parse HTML tables")
            
            # Check for product cards/sections
            print("\n   🔍 Checking for product cards...")
            product_cards = await page.query_selector_all('[class*="product-card"], [class*="rate-card"], div.product, div.loan-product')
            if product_cards and len(product_cards) < 50:  # Reasonable number
                analysis["details"]["product_cards"] = len(product_cards)
                print(f"      ℹ️  Found {len(product_cards)} product cards (might need DOM parsing)")
            
            # Final recommendation
            if not analysis["recommended_strategy"]:
                analysis["recommended_strategy"] = "dom-parsing"
                print(f"\n      ⚠️  No structured data found - will need DOM parsing")
            
            # Save HTML for manual inspection
            html = await page.content()
            html_file = OUTPUT_DIR / f"{bank_name.lower()}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # Save screenshot
            screenshot_file = OUTPUT_DIR / f"{bank_name.lower()}.png"
            await page.screenshot(path=str(screenshot_file), full_page=True)
            
            print(f"\n   💾 Saved HTML to: {html_file.name}")
            print(f"   📸 Saved screenshot to: {screenshot_file.name}")
            
        except Exception as e:
            print(f"\n   ❌ Error analyzing {bank_name}: {e}")
            analysis["error"] = str(e)
        
        finally:
            await browser.close()
    
    return analysis


async def main():
    """Analyze all major Australian banks."""
    
    banks = [
        {
            "name": "CBA",
            "url": "https://www.commbank.com.au/home-loans/interest-rates.html"
        },
        {
            "name": "Westpac",
            "url": "https://www.westpac.com.au/personal-banking/home-loans/home-loan-rates/"
        },
        {
            "name": "NAB",
            "url": "https://www.nab.com.au/personal/home-loans/compare-our-home-loan-rates"
        },
        {
            "name": "ANZ",
            "url": "https://www.anz.com.au/personal/home-loans/interest-rates/"
        },
    ]
    
    print("\n🔬 Batch Bank Analysis - Finding Extraction Strategies")
    print("="*80)
    print(f"\nAnalyzing {len(banks)} banks...")
    print("This will take ~30 seconds per bank\n")
    
    all_analysis = []
    
    for bank in banks:
        try:
            analysis = await analyze_bank(bank["url"], bank["name"])
            all_analysis.append(analysis)
            await asyncio.sleep(2)  # Be respectful to servers
        except Exception as e:
            print(f"\n❌ Failed to analyze {bank['name']}: {e}")
    
    # Save comprehensive report
    report_file = OUTPUT_DIR / "extraction_strategy_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(all_analysis, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("📊 ANALYSIS SUMMARY")
    print("="*80)
    
    for analysis in all_analysis:
        bank = analysis["bank"]
        recommended = analysis.get("recommended_strategy", "unknown")
        strategies = ", ".join(analysis.get("strategies_found", []))
        
        print(f"\n{bank}:")
        print(f"  Recommended Strategy: {recommended}")
        print(f"  Available Strategies: {strategies or 'None found'}")
        
        if recommended == "select-dropdown":
            count = analysis["details"].get("dropdown_products", 0)
            print(f"  Products in dropdown: {count}")
        elif recommended == "html-table":
            count = analysis["details"].get("rate_tables", 0)
            print(f"  Rate tables found: {count}")
    
    print("\n" + "="*80)
    print(f"✅ Full report saved to: {report_file}")
    print("="*80)
    
    print("\n📝 Next Steps:")
    print("1. Check the report to see which strategy each bank uses")
    print("2. Update PlaywrightCollectorAgent to handle each strategy")
    print("3. Test again with: python run_collection.py")


if __name__ == "__main__":
    asyncio.run(main())
