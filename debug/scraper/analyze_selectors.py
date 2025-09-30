"""
Analyze the saved HTML to find the best selectors for extracting loan products.
"""

from pathlib import Path
from bs4 import BeautifulSoup
import re
import json


def analyze_anz_html():
    """Analyze ANZ HTML to find product data structure."""
    
    html_file = Path("debug/scraper/outputs/anz.html")
    if not html_file.exists():
        print("❌ HTML file not found. Run debug_page_inspector.py first.")
        return
    
    print("📄 Analyzing ANZ HTML structure...\n")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    # Find the interest rate dropdown
    print("🔍 Looking for interest rate dropdowns...")
    selects = soup.find_all('select')
    
    for i, select in enumerate(selects, 1):
        select_id = select.get('id', 'no-id')
        options = select.find_all('option')
        
        # Check if it contains rate information
        rate_options = [opt for opt in options if '% p.a' in opt.get_text()]
        
        if rate_options:
            print(f"\n✅ Found rate dropdown #{i}:")
            print(f"   ID: {select_id}")
            print(f"   Options with rates: {len(rate_options)}")
            print(f"\n   Selector: select#{select_id}")
            print(f"   Or: select[id*='InterestRate']")
            print(f"\n   Sample products:")
            
            products = []
            for opt in rate_options[:5]:  # First 5
                text = opt.get_text().strip()
                print(f"      - {text}")
                
                # Parse the option text
                # Format: "6.49% p.a Standard Variable 80% or less LVR"
                match = re.match(r'([\d.]+)% p\.a\s+(.+?)(?:\s+([\d]+%.*LVR))?$', text)
                if match:
                    rate = match.group(1)
                    product_name = match.group(2).strip()
                    lvr_info = match.group(3) if match.group(3) else "Unknown"
                    
                    products.append({
                        "rate": float(rate),
                        "product_name": product_name,
                        "lvr": lvr_info,
                        "raw_text": text
                    })
            
            # Save analysis
            output_file = Path("debug/scraper/outputs/anz_products_found.json")
            with open(output_file, 'w') as f:
                json.dump(products, f, indent=2)
            print(f"\n💾 Saved parsed products to: {output_file}")
    
    # Find product heading sections
    print("\n\n🔍 Looking for product section headings...")
    h3_tags = soup.find_all('h3')
    
    loan_headings = [h3 for h3 in h3_tags if 'loan' in h3.get_text().lower()]
    if loan_headings:
        print(f"\n   Found {len(loan_headings)} loan-related headings:")
        for h3 in loan_headings[:5]:
            print(f"      - {h3.get_text().strip()}")
    
    # Find tables with rate data
    print("\n\n🔍 Looking for rate tables...")
    tables = soup.find_all('table')
    
    for i, table in enumerate(tables, 1):
        # Check if table has rate-related headers
        headers = table.find_all('th')
        header_texts = [th.get_text().strip() for th in headers]
        
        if any('rate' in h.lower() or 'lvr' in h.lower() for h in header_texts):
            print(f"\n   Table #{i} with rate data:")
            print(f"      Headers: {header_texts[:5]}")  # First 5 headers
    
    print("\n" + "="*80)
    print("✅ Analysis complete!")
    print("="*80)
    print("\n💡 Recommended Selectors for ANZ:")
    print("   Product names: select[id*='InterestRate'] option")
    print("   Rates: Parse option text with regex")
    print("   Format: '{rate}% p.a {product_name} {lvr_info}'")


if __name__ == "__main__":
    analyze_anz_html()
