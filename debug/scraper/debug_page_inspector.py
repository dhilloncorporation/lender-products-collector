"""
Debug script to inspect what's actually on lender pages.
This helps us understand why we're getting 0 products.

Output saved to: debug/scraper/outputs/
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


# Create output directory
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


async def debug_page(url: str, lender_name: str):
    """Load a page and show what's actually there."""
    print(f"\n{'='*80}")
    print(f"Debugging: {lender_name}")
    print(f"URL: {url}")
    print(f"{'='*80}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visible browser
        page = await browser.new_page()
        
        try:
            print("📡 Loading page...")
            # Use 'domcontentloaded' instead of 'networkidle' - more reliable
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            # Wait a bit for dynamic content
            await page.wait_for_timeout(3000)
            print("✅ Page loaded\n")
            
            # Get page title
            title = await page.title()
            print(f"📄 Page Title: {title}\n")
            
            # Check for common elements
            print("🔍 Looking for product-related elements...\n")
            
            # Try different selectors
            selectors_to_try = {
                "Tables": "table",
                "Product cards": ".product, .card, [class*='product'], [class*='loan']",
                "Headings (h1-h4)": "h1, h2, h3, h4",
                "Rates": "[class*='rate'], [class*='interest']",
                "Percentages": "*:has-text('%')",
            }
            
            for name, selector in selectors_to_try.items():
                try:
                    elements = await page.query_selector_all(selector)
                    count = len(elements)
                    print(f"  {name} ({selector}): {count} found")
                    
                    if count > 0 and count < 10:  # Show samples if reasonable number
                        for i, elem in enumerate(elements[:3], 1):
                            text = await elem.inner_text()
                            text_preview = text.strip()[:100].replace('\n', ' ')
                            print(f"    Sample {i}: {text_preview}")
                except Exception as e:
                    print(f"  {name}: Error - {e}")
            
            # Save HTML for inspection
            html = await page.content()
            filename = OUTPUT_DIR / f"{lender_name.lower().replace(' ', '_')}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"\n💾 Saved HTML to: {filename}")
            
            # Take screenshot
            screenshot_file = OUTPUT_DIR / f"{lender_name.lower().replace(' ', '_')}.png"
            await page.screenshot(path=str(screenshot_file), full_page=True)
            print(f"📸 Saved screenshot to: {screenshot_file}")
            
            # Wait for manual inspection
            print(f"\n⏸️  Browser window open for manual inspection...")
            print(f"   Press Ctrl+C when done looking at the page\n")
            await asyncio.sleep(300)  # Wait 5 minutes or until interrupted
            
        except KeyboardInterrupt:
            print("\n✋ Stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            await browser.close()


async def main():
    """Debug multiple lenders."""
    
    # Debug all major banks to find their data extraction patterns
    lenders_to_debug = [
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
    
    print("\n🐛 Page Inspector - Scraper Debug Tool")
    print("="*80)
    print("\nThis will:")
    print("  1. Open each lender's page in a visible browser")
    print("  2. Show what elements are found")
    print(f"  3. Save HTML and screenshots to: {OUTPUT_DIR}")
    print("  4. Let you inspect the page manually")
    print("\nPress Ctrl+C to stop and move to next lender\n")
    
    for lender in lenders_to_debug:
        try:
            await debug_page(lender["url"], lender["name"])
        except KeyboardInterrupt:
            print(f"\n⏭️  Moving to next lender...")
            continue
    
    print("\n" + "="*80)
    print("✅ Debug complete!")
    print("="*80)
    print("\nNext steps:")
    print(f"  1. Check the saved files in: {OUTPUT_DIR}")
    print("  2. Update CSS selectors in src/agents/collector/playwright_collector.py")
    print("  3. Or add lender-specific selectors to src/configs/lenders.json")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Debug session ended")
