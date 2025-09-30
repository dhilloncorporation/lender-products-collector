"""Playwright-based collector agent for loan products."""

import os
import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page
from ...models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria

logger = logging.getLogger(__name__)


class PlaywrightCollectorAgent:
    """Agent that uses Playwright to collect loan product data from lender websites."""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """Initialize the collector agent."""
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.collected_products: List[LoanProduct] = []
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def collect_from_url(
        self, 
        url: str, 
        lender_name: str,
        selectors: Dict[str, str] = None
    ) -> List[LoanProduct]:
        """
        Collect loan products from a specific URL using multi-strategy extraction.
        
        Strategies (in order):
        1. Network introspection (capture JSON APIs)
        2. JSON-LD structured data
        3. Embedded JavaScript state (window.__NEXT_DATA__, etc.)
        4. Select dropdowns (ANZ-style)
        5. DOM parsing with CSS selectors (fallback)
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async context manager.")
        
        page = await self.browser.new_page()
        products = []
        captured_apis = []
        
        try:
            # Set up network capture to find JSON APIs
            def handle_response(response):
                """Capture JSON API responses."""
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type and response.status == 200:
                    captured_apis.append({
                        'url': response.url,
                        'status': response.status,
                        'response': response
                    })
            
            page.on('response', handle_response)
            
            logger.info(f"Collecting from {url}")
            # Use 'domcontentloaded' instead of 'networkidle' - more reliable
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            # Wait for dynamic content and API calls
            await page.wait_for_timeout(3000)
            
            # Try multiple extraction strategies
            products = await self._smart_extract_products(page, lender_name, url, selectors, captured_apis)
            
        except Exception as e:
            logger.error(f"Error collecting from {url}: {str(e)}")
        finally:
            await page.close()
        
        return products
    
    async def _smart_extract_products(
        self, 
        page: Page, 
        lender_name: str, 
        url: str, 
        selectors: Dict[str, str] = None,
        captured_apis: List[Dict] = None
    ) -> List[LoanProduct]:
        """
        Smart multi-strategy product extraction (ChatGPT approach).
        
        Tries strategies in order of reliability:
        0. Network introspection (captured JSON APIs) - Fastest, most reliable
        1. JSON-LD (structured data) - Most reliable
        2. Embedded state (window.__NEXT_DATA__, etc.) - Very reliable
        3. Select dropdowns - Reliable for ANZ-style pages
        4. DOM parsing - Fallback
        """
        products = []
        captured_apis = captured_apis or []
        
        # Strategy 0: Network introspection - check captured JSON APIs
        if captured_apis:
            logger.debug(f"Trying Strategy 0: Network introspection ({len(captured_apis)} APIs captured)")
            products = await self._extract_from_captured_apis(captured_apis, lender_name, url)
            if products:
                logger.info(f"✅ Extracted {len(products)} products via captured JSON API")
                return products
        
        # Strategy 1: JSON-LD structured data
        logger.debug("Trying Strategy 1: JSON-LD")
        products = await self._extract_from_jsonld(page, lender_name, url)
        if products:
            logger.info(f"✅ Extracted {len(products)} products via JSON-LD")
            return products
        
        # Strategy 2: Embedded JavaScript state
        logger.debug("Trying Strategy 2: Embedded state")
        products = await self._extract_from_embedded_state(page, lender_name, url)
        if products:
            logger.info(f"✅ Extracted {len(products)} products via embedded state")
            return products
        
        # Strategy 3: Select dropdowns (ANZ, CBA use this)
        logger.debug("Trying Strategy 3: Select dropdowns")
        products = await self._extract_from_select_dropdowns(page, lender_name, url)
        if products:
            logger.info(f"✅ Extracted {len(products)} products via select dropdown")
            return products
        
        # Strategy 4: Fallback to DOM parsing
        logger.debug("Trying Strategy 4: DOM parsing (fallback)")
        products = await self._extract_products(page, lender_name, url, selectors)
        if products:
            logger.info(f"✅ Extracted {len(products)} products via DOM parsing")
        else:
            logger.warning(f"⚠️  No products found with any strategy")
        
        return products
    
    async def _extract_from_captured_apis(
        self, 
        captured_apis: List[Dict], 
        lender_name: str, 
        url: str
    ) -> List[LoanProduct]:
        """
        Extract products from captured JSON API responses.
        
        The page loaded JSON data via XHR/fetch - parse it directly!
        This is often the cleanest, most structured data source.
        """
        products = []
        
        try:
            for api_call in captured_apis:
                try:
                    # Get JSON response
                    response_obj = api_call['response']
                    json_data = await response_obj.json()
                    api_url = api_call['url']
                    
                    logger.debug(f"Analyzing API: {api_url}")
                    
                    # Look for product/loan data in common JSON structures
                    # Try different paths where product data might be
                    product_arrays = self._find_product_arrays_in_json(json_data)
                    
                    for product_data in product_arrays:
                        # Extract fields
                        name = (
                            product_data.get('name') or 
                            product_data.get('productName') or 
                            product_data.get('title') or
                            product_data.get('loanName') or
                            ''
                        )
                        
                        rate = (
                            product_data.get('rate') or
                            product_data.get('interestRate') or
                            product_data.get('comparisonRate') or
                            0
                        )
                        
                        if name and rate:
                            # Convert rate to float if it's a string
                            if isinstance(rate, str):
                                rate_match = re.search(r'([\d.]+)', rate)
                                rate = float(rate_match.group(1)) if rate_match else 0
                            
                            product = LoanProduct(
                                product_id=f"{lender_name}-API-{re.sub(r'[^a-zA-Z0-9]', '-', name)[:50]}",
                                version="1.0",
                                status="active",
                                name=f"{lender_name} {name}",
                                short_name=name,
                                description=product_data.get('description', f"{name} from {lender_name}"),
                                purpose="OwnerOccupied_Purchase",
                                channels=["Branch", "Online"],
                                interest_components=[
                                    InterestComponent(
                                        name=name,
                                        rate_type=product_data.get('rateType', 'Variable'),
                                        comparison_rate_pct_au=float(rate),
                                        applicability={}
                                    )
                                ],
                                fees=FeeStructure(),
                                features=ProductFeatures(),
                                eligibility=EligibilityCriteria(
                                    min_loan_amount_aud=20000,
                                    max_loan_amount_aud=2000000,
                                    min_age_years=18,
                                    residency=["AustralianCitizen", "PermanentResident"],
                                    borrower_types=["Individual"],
                                    occupancy=["OwnerOccupied"],
                                    max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": 0.80}],
                                    property_types_allowed=["House", "Apartment", "Townhouse"]
                                ),
                                lender=lender_name,
                                source_url=api_url  # Save the API URL, not the page URL
                            )
                            products.append(product)
                            logger.debug(f"Extracted from API: {name}")
                
                except Exception as e:
                    logger.debug(f"Failed to parse API response: {e}")
        
        except Exception as e:
            logger.debug(f"Captured API extraction failed: {e}")
        
        return products
    
    def _find_product_arrays_in_json(self, data: Any, path: str = "") -> List[Dict]:
        """
        Recursively search JSON for arrays that look like product data.
        
        Returns flattened list of all objects that might be products.
        """
        products = []
        
        if isinstance(data, dict):
            # Check if this dict looks like a product
            if any(key in data for key in ['name', 'productName', 'rate', 'interestRate', 'loanName']):
                products.append(data)
            
            # Recursively check nested dicts and arrays
            for key, value in data.items():
                # Common product array keys
                if key in ['products', 'items', 'loans', 'data', 'results', 'productList']:
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                products.extend(self._find_product_arrays_in_json(item, f"{path}.{key}"))
                    elif isinstance(value, dict):
                        products.extend(self._find_product_arrays_in_json(value, f"{path}.{key}"))
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    products.extend(self._find_product_arrays_in_json(item, path))
        
        return products
    
    async def _extract_from_jsonld(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from JSON-LD structured data (schema.org format).
        
        Many financial sites use JSON-LD for SEO. Format:
        {
          "@type": "FinancialProduct" or "LoanOrCredit",
          "name": "Product name",
          "offers": {"price": "5.99", ...}
        }
        """
        products = []
        
        try:
            import json as json_module
            jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            
            for script in jsonld_scripts:
                content = await script.inner_text()
                data = json_module.loads(content)
                
                # Handle both single objects and arrays
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    item_type = item.get("@type", "")
                    
                    # Check if it's a financial product
                    if item_type in ["Product", "FinancialProduct", "LoanOrCredit", "Offer"]:
                        logger.debug(f"Found JSON-LD {item_type}: {item.get('name')}")
                        
                        # Extract basic info
                        name = item.get("name", "")
                        description = item.get("description", "")
                        
                        # Extract offers/pricing
                        offers = item.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}
                        
                        # Try to extract rate from price or description
                        rate = 0.0
                        price_str = str(offers.get("price", "0"))
                        rate_match = re.search(r'([\d.]+)', price_str)
                        if rate_match:
                            rate = float(rate_match.group(1))
                        else:
                            # Try to find rate in name or description
                            text = f"{name} {description}"
                            rate_match = re.search(r'([\d.]+)%', text)
                            if rate_match:
                                rate = float(rate_match.group(1))
                        
                        if rate > 0 and name:
                            # Create product
                            product = LoanProduct(
                                product_id=f"{lender_name}-JSONLD-{re.sub(r'[^a-zA-Z0-9]', '-', name)[:50]}",
                                version="1.0",
                                status="active",
                                name=f"{lender_name} {name}",
                                short_name=name,
                                description=description or f"{name} from {lender_name}",
                                purpose="OwnerOccupied_Purchase",
                                channels=["Branch", "Online"],
                                interest_components=[
                                    InterestComponent(
                                        name=name,
                                        rate_type="Variable",  # Default, could parse from name
                                        comparison_rate_pct_au=rate,
                                        applicability={}
                                    )
                                ],
                                fees=FeeStructure(),
                                features=ProductFeatures(),
                                eligibility=EligibilityCriteria(
                                    min_loan_amount_aud=20000,
                                    max_loan_amount_aud=2000000,
                                    min_age_years=18,
                                    residency=["AustralianCitizen", "PermanentResident"],
                                    borrower_types=["Individual"],
                                    occupancy=["OwnerOccupied"],
                                    max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": 0.80}],
                                    property_types_allowed=["House", "Apartment", "Townhouse"]
                                ),
                                lender=lender_name,
                                source_url=url
                            )
                            products.append(product)
                            logger.debug(f"Extracted from JSON-LD: {name}")
        
        except Exception as e:
            logger.debug(f"JSON-LD extraction failed: {e}")
        
        return products
    
    async def _extract_from_embedded_state(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from embedded JavaScript state.
        
        Common patterns:
        - window.__NEXT_DATA__ (Next.js apps)
        - window.__NUXT__ (Nuxt apps)
        - window.dataLayer (Google Tag Manager - CBA uses this!)
        - window.Shopify (Shopify stores)
        """
        products = []
        
        try:
            # Check for common state objects
            state = await page.evaluate("""() => {
                return {
                    nextData: globalThis.__NEXT_DATA__ || null,
                    nuxt: globalThis.__NUXT__ || null,
                    dataLayer: globalThis.dataLayer || null,
                    shopify: globalThis.Shopify || null
                };
            }""")
            
            if any(state.values()):
                logger.debug(f"Found embedded state: {[k for k,v in state.items() if v]}")
            
            # Parse dataLayer (CBA, ANZ use this)
            if state.get('dataLayer'):
                products = await self._parse_datalayer(state['dataLayer'], lender_name, url)
                if products:
                    return products
            
            # Parse Next.js data
            if state.get('nextData'):
                products = await self._parse_nextjs_data(state['nextData'], lender_name, url)
                if products:
                    return products
            
            # Parse Nuxt data
            if state.get('nuxt'):
                products = await self._parse_nuxt_data(state['nuxt'], lender_name, url)
                if products:
                    return products
                    
        except Exception as e:
            logger.debug(f"Embedded state extraction failed: {e}")
        
        return products
    
    async def _parse_datalayer(self, datalayer: list, lender_name: str, url: str) -> List[LoanProduct]:
        """Parse Google Tag Manager dataLayer for product data."""
        products = []
        
        try:
            # dataLayer is an array of events/objects
            for item in datalayer:
                # Look for ecommerce data
                if 'ecommerce' in item:
                    ecommerce = item['ecommerce']
                    
                    # Check for products array
                    product_list = ecommerce.get('items', []) or ecommerce.get('products', [])
                    
                    for prod_data in product_list:
                        name = prod_data.get('name') or prod_data.get('item_name', '')
                        price = prod_data.get('price', 0)
                        
                        if name and price:
                            # Try to parse rate from price or name
                            rate = float(price) if isinstance(price, (int, float)) else 0.0
                            
                            product = LoanProduct(
                                product_id=f"{lender_name}-DL-{re.sub(r'[^a-zA-Z0-9]', '-', name)[:50]}",
                                version="1.0",
                                status="active",
                                name=f"{lender_name} {name}",
                                short_name=name,
                                description=prod_data.get('description', f"{name} from {lender_name}"),
                                purpose="OwnerOccupied_Purchase",
                                channels=["Branch", "Online"],
                                interest_components=[
                                    InterestComponent(
                                        name=name,
                                        rate_type="Variable",
                                        comparison_rate_pct_au=rate,
                                        applicability={}
                                    )
                                ],
                                fees=FeeStructure(),
                                features=ProductFeatures(),
                                eligibility=EligibilityCriteria(
                                    min_loan_amount_aud=20000,
                                    max_loan_amount_aud=2000000,
                                    min_age_years=18,
                                    residency=["AustralianCitizen", "PermanentResident"],
                                    borrower_types=["Individual"],
                                    occupancy=["OwnerOccupied"],
                                    max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": 0.80}],
                                    property_types_allowed=["House", "Apartment", "Townhouse"]
                                ),
                                lender=lender_name,
                                source_url=url
                            )
                            products.append(product)
                            logger.debug(f"Extracted from dataLayer: {name}")
                
                # Also check for page-level product data (not in ecommerce)
                if 'product' in item:
                    prod_data = item['product']
                    name = prod_data.get('name', '')
                    if name:
                        logger.debug(f"Found product in dataLayer: {name}")
                        # TODO: Extract and create product
        
        except Exception as e:
            logger.debug(f"dataLayer parsing failed: {e}")
        
        return products
    
    async def _parse_nextjs_data(self, nextdata: dict, lender_name: str, url: str) -> List[LoanProduct]:
        """Parse Next.js __NEXT_DATA__ for product information."""
        products = []
        
        try:
            # Next.js data is in props.pageProps
            page_props = nextdata.get('props', {}).get('pageProps', {})
            
            # Look for products in common locations
            product_data = (
                page_props.get('products') or
                page_props.get('productList') or
                page_props.get('loans') or
                page_props.get('initialData', {}).get('products') or
                []
            )
            
            for prod in product_data:
                name = prod.get('name') or prod.get('title', '')
                rate = prod.get('rate') or prod.get('interestRate', 0)
                
                if name:
                    logger.debug(f"Found Next.js product: {name}")
                    # TODO: Map to LoanProduct
        
        except Exception as e:
            logger.debug(f"Next.js data parsing failed: {e}")
        
        return products
    
    async def _parse_nuxt_data(self, nuxt_data: dict, lender_name: str, url: str) -> List[LoanProduct]:
        """Parse Nuxt __NUXT__ for product information."""
        products = []
        
        try:
            # Nuxt structure varies - explore common paths
            # Usually in nuxt_data.data or nuxt_data.state
            logger.debug("Nuxt data found but parsing not implemented yet")
            # TODO: Implement Nuxt data parsing
        
        except Exception as e:
            logger.debug(f"Nuxt data parsing failed: {e}")
        
        return products
    
    async def _extract_from_select_dropdowns(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from select dropdowns (ANZ-style).
        
        ANZ embeds products in:
        <select id="...InterestRate...">
          <option>6.49% p.a Standard Variable 80% or less LVR</option>
        </select>
        """
        products = []
        
        try:
            # Find select elements that might contain rates
            rate_selects = await page.query_selector_all('select[id*="Interest"], select[id*="interest"], select[id*="rate"], select[id*="Rate"]')
            
            for select_elem in rate_selects:
                options = await select_elem.query_selector_all('option')
                
                for opt in options:
                    text = await opt.inner_text()
                    text = text.strip()
                    
                    # Skip placeholders
                    if not text or 'Please select' in text or 'Select' in text:
                        continue
                    
                    # Look for rate patterns: "6.49% p.a ..."
                    if '% p.a' in text or '%p.a' in text:
                        product = await self._parse_rate_dropdown_option(text, lender_name, url)
                        if product:
                            products.append(product)
            
            if products:
                logger.info(f"Found {len(products)} products in select dropdowns")
        
        except Exception as e:
            logger.debug(f"Select dropdown extraction failed: {e}")
        
        return products
    
    async def _parse_rate_dropdown_option(self, text: str, lender_name: str, url: str) -> Optional[LoanProduct]:
        """
        Parse rate dropdown option text into LoanProduct.
        
        Format examples:
        - "6.49% p.a Standard Variable 80% or less LVR"
        - "5.64% p.a Simplicity PLUS special offer discount 60% or less LVR*"
        """
        try:
            # Parse: "{rate}% p.a {product_name} [{lvr_info}]"
            match = re.match(r'([\d.]+)%\s*p\.a\s+(.+?)(?:\s+([\d]+%.*?LVR.*?))?$', text)
            
            if not match:
                return None
            
            rate = float(match.group(1))
            product_name = match.group(2).strip()
            lvr_text = match.group(3).strip() if match.group(3) else None
            
            # Parse LVR from text like "80% or less LVR" or "60% or less LVR*"
            lvr_value = 0.80  # Default
            if lvr_text:
                lvr_match = re.search(r'([\d]+)%', lvr_text)
                if lvr_match:
                    lvr_value = float(lvr_match.group(1)) / 100
            
            # Determine rate type from product name
            rate_type = "Variable"
            if "fixed" in product_name.lower():
                rate_type = "Fixed"
            elif "variable" in product_name.lower():
                rate_type = "Variable"
            
            # Create product with BIAN schema
            product = LoanProduct(
                product_id=f"{lender_name}-{re.sub(r'[^a-zA-Z0-9]', '-', product_name)[:50]}",
                version="1.0",
                status="active",
                name=f"{lender_name} {product_name}",
                short_name=product_name,
                description=f"{product_name} from {lender_name}",
                purpose="OwnerOccupied_Purchase",
                channels=["Branch", "Online"],
                interest_components=[
                    InterestComponent(
                        name=product_name,
                        rate_type=rate_type,
                        comparison_rate_pct_au=rate,
                        applicability={}
                    )
                ],
                fees=FeeStructure(),
                features=ProductFeatures(),
                eligibility=EligibilityCriteria(
                    min_loan_amount_aud=20000,
                    max_loan_amount_aud=2000000,
                    min_age_years=18,
                    residency=["AustralianCitizen", "PermanentResident"],
                    borrower_types=["Individual"],
                    occupancy=["OwnerOccupied"],
                    max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": lvr_value}],
                    property_types_allowed=["House", "Apartment", "Townhouse"]
                ),
                lender=lender_name,
                source_url=url
            )
            
            return product
            
        except Exception as e:
            logger.debug(f"Failed to parse dropdown option '{text}': {e}")
            return None
    
    async def _extract_products(self, page: Page, lender_name: str, url: str, selectors: Dict[str, str] = None) -> List[LoanProduct]:
        """
        Extract loan products from DOM (fallback strategy).
        
        This uses a simpler text-based approach that looks for rate patterns
        anywhere on the page, rather than complex container-based extraction.
        
        Works for pages like NAB where products are in simple HTML sections:
        <h3>Tailored fixed rate</h3>
        <div>5.19% p.a.</div>
        """
        products = []
        
        try:
            # Simple strategy: Find all headings that look like product names
            # and check nearby text for rates
            headings = await page.query_selector_all('h1, h2, h3, h4, h5')
            
            for heading in headings:
                heading_text = await heading.inner_text()
                heading_text = heading_text.strip()
                
                # Check if heading looks like a loan product
                if not self._looks_like_loan_product(heading_text):
                    continue
                
                # Get parent container (usually a div or section)
                parent = await heading.evaluate_handle('el => el.closest("div, section, article")')
                if not parent:
                    continue
                
                parent_text = await parent.inner_text()
                
                # Look for rate patterns in the parent container
                # Format: "5.19% p.a" or "6.04 % p.a." or "5.19%"
                rate_matches = re.findall(r'([\d.]+)\s*%\s*(?:p\.a\.?)?', parent_text)
                
                if rate_matches:
                    # Take the first rate found (usually the main rate)
                    rate = float(rate_matches[0])
                    
                    # Look for comparison rate
                    comparison_rate = rate
                    comp_match = re.search(r'[Cc]omparison\s+rate.*?([\d.]+)\s*%', parent_text)
                    if comp_match:
                        comparison_rate = float(comp_match.group(1))
                    
                    # Determine rate type
                    rate_type = "Variable"
                    if re.search(r'\bfixed\b', heading_text + parent_text, re.IGNORECASE):
                        rate_type = "Fixed"
                    
                    # Extract LVR if mentioned
                    lvr_value = 0.80  # Default
                    lvr_match = re.search(r'([\d]+)%.*?LVR', parent_text, re.IGNORECASE)
                    if lvr_match:
                        lvr_value = float(lvr_match.group(1)) / 100
                    
                    # Create product
                    product = LoanProduct(
                        product_id=f"{lender_name}-DOM-{re.sub(r'[^a-zA-Z0-9]', '-', heading_text)[:50]}",
                        version="1.0",
                        status="active",
                        name=f"{lender_name} {heading_text}",
                        short_name=heading_text,
                        description=f"{heading_text} from {lender_name}",
                        purpose="OwnerOccupied_Purchase",
                        channels=["Branch", "Online"],
                        interest_components=[
                            InterestComponent(
                                name=heading_text,
                                rate_type=rate_type,
                                comparison_rate_pct_au=comparison_rate,
                                applicability={}
                            )
                        ],
                        fees=FeeStructure(),
                        features=ProductFeatures(),
                        eligibility=EligibilityCriteria(
                            min_loan_amount_aud=20000,
                            max_loan_amount_aud=2000000,
                            min_age_years=18,
                            residency=["AustralianCitizen", "PermanentResident"],
                            borrower_types=["Individual"],
                            occupancy=["OwnerOccupied"],
                            max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": lvr_value}],
                            property_types_allowed=["House", "Apartment", "Townhouse"]
                        ),
                        lender=lender_name,
                        source_url=url
                    )
                    
                    products.append(product)
                    logger.debug(f"Extracted via DOM: {heading_text} - {rate}%")
        
        except Exception as e:
            logger.debug(f"DOM parsing failed: {e}")
        
        return products
    
    def _looks_like_loan_product(self, text: str) -> bool:
        """Check if text looks like a loan product name."""
        text_lower = text.lower()
        
        # Must contain loan-related keywords
        loan_keywords = ['loan', 'rate', 'variable', 'fixed', 'mortgage', 'offset', 'tailored', 'basic']
        has_keyword = any(keyword in text_lower for keyword in loan_keywords)
        
        # Exclude navigation/generic text
        exclude_keywords = ['contact', 'login', 'menu', 'search', 'apply now', 'learn more', 'calculator']
        has_exclude = any(keyword in text_lower for keyword in exclude_keywords)
        
        # Should be reasonable length
        is_reasonable_length = 5 < len(text) < 100
        
        return has_keyword and not has_exclude and is_reasonable_length
    
    # Keep old complex methods for reference (not used by new simple DOM parser)
    async def _extract_products_OLD_COMPLEX(self, page: Page, lender_name: str, url: str, selectors: Dict[str, str] = None) -> List[LoanProduct]:
        """OLD complex DOM extraction - keeping for reference."""
        products = []
        
        # Default selectors - can be overridden per lender
        default_selectors = {
            'product_container': '.product-card, .loan-product, .rate-card, [class*="product"][class*="card"]',
            'product_name': 'h3, h4, .product-title, .loan-name, [class*="product"][class*="name"]',
            'rate': '.rate-value, .interest-rate, .rate-number, [class*="rate"][class*="value"]',
            'comparison_rate': '.comparison-rate, .comparison-value, [class*="comparison"][class*="rate"]',
            'rate_type': '.rate-type, .loan-type, [class*="fixed"], [class*="variable"]',
            'features': '.features, .benefits, .product-features, [class*="feature"]',
            'fees': '.fees, .cost, .fee-amount, [class*="fee"]',
            'lvr': '.lvr, .lvr-value, [class*="lvr"]'
        }
        
        selectors = selectors or default_selectors
        
        try:
            # First try to find product containers
            product_containers = await page.query_selector_all(selectors.get('product_container', 'body'))
            
            if not product_containers:
                # Fallback to individual elements
                product_containers = [page]
            
            for container in product_containers:
                # Extract product name
                product_name = await self._extract_text_from_selector(container, selectors['product_name'])
                if not product_name or not self._is_valid_product_name(product_name):
                    continue
                
                # Extract rates
                rates = await self._extract_rates_from_container(container, selectors)
                if rates['main_rate'] == 0.0:
                    continue  # Skip products without rates
                
                # Extract features
                features = await self._extract_features_from_container(container, selectors)
                
                # Extract fees
                fees = await self._extract_fees_from_container(container, selectors)
                
                # Extract rate type
                rate_type = await self._extract_text_from_selector(container, selectors['rate_type'])
                if not rate_type:
                    rate_type = self._determine_rate_type(product_name)
                
                # Extract LVR
                lvr_text = await self._extract_text_from_selector(container, selectors['lvr'])
                lvr_max = self._extract_lvr_from_text(lvr_text) if lvr_text else 95.0
                
                # Create comprehensive product using BIAN schema
                product = LoanProduct(
                    # Basic info
                    product_id=f"{lender_name.upper()}-{product_name.replace(' ', '-').upper()}-{datetime.now().strftime('%Y%m%d')}",
                    version="1.0",
                    status="Active",
                    name=product_name.strip(),
                    short_name=product_name.strip()[:20],
                    description=f"{lender_name} {product_name} home loan product",
                    purpose="OwnerOccupied_Purchase",
                    channels=["DirectOnline", "Branch"],
                    
                    # Interest components
                    interest_components=[
                        InterestComponent(
                            name="PrimaryRate",
                            rate_type="VariableIndex" if rate_type == "variable" else "Fixed",
                            fixed_term_months=24 if rate_type == "fixed" else None,
                            comparison_rate_pct_au=rates['main_rate'],
                            margin_pct=Decimal("1.20") if rate_type == "variable" else None,
                            floor_pct=Decimal("4.80") if rate_type == "variable" else None,
                            applicability={"portionMaxPctOfLimit": 1.0}
                        )
                    ],
                    
                    # Fees
                    fees=FeeStructure(
                        upfront=[
                            {"code": "APP", "label": "Application Fee", "amountAUD": fees.get("application_fee", 0)},
                            {"code": "VAL", "label": "Valuation Fee", "amountAUD": 330}
                        ],
                        ongoing=[],
                        event_driven=[]
                    ),
                    
                    # Features
                    features=ProductFeatures(
                        offset_account={"enabled": "offset" in features},
                        redraw={"enabled": "redraw" in features},
                        extra_repayments={"allowed": True},
                        split_loans={"maxSplits": 10},
                        rate_lock={"available": False},
                        package={"bundleName": "Standard", "annualFeeAUD": 0}
                    ),
                    
                    # Eligibility
                    eligibility=EligibilityCriteria(
                        min_loan_amount_aud=Decimal("50000"),
                        max_loan_amount_aud=Decimal("2000000"),
                        min_age_years=18,
                        residency=["Citizen", "PR", "NZCitizen"],
                        borrower_types=["Individual"],
                        occupancy=["OwnerOccupied"],
                        max_lvr_by_segment=[
                            {"segment": "OO_PPOR", "maxLVR": lvr_max / 100, "lmiRequiredAboveLVR": 0.80}
                        ],
                        property_types_allowed=["House", "Townhouse", "Unit"]
                    ),
                    
                    # Security
                    security={
                        "requiredSecurity": "Secured",
                        "acceptableCollateralTypes": ["ResidentialProperty"],
                        "valuationPolicy": {"method": "Desktop", "validityDays": 120}
                    },
                    
                    # Policy
                    policy={
                        "serviceability": {
                            "assessmentRateMethod": "FloorVsNoteRatePlusBufferMax",
                            "bufferPct": 3.0,
                            "floorPct": 7.25
                        }
                    },
                    
                    # Compliance
                    compliance={
                        "apraProductCode": f"APRA-MORT-{lender_name.upper()}",
                        "amlKycNotes": "Standard AUSTRAC requirements apply"
                    },
                    
                    # Collection metadata
                    lender=lender_name,
                    source_url=url,
                    collected_at=datetime.now()
                )
                
                products.append(product)
                logger.info(f"Extracted product: {product_name} - Rate: {rates['main_rate']}%")
        
        except Exception as e:
            logger.error(f"Error extracting products: {str(e)}")
        
        return products
    
    async def _extract_rates(self, page: Page, element, selectors: Dict[str, str]) -> Dict[str, float]:
        """Extract interest rates from the page."""
        rates = {'main_rate': 0.0, 'comparison_rate': 0.0}
        
        try:
            # Look for rate text in the element and nearby
            rate_text = await element.text_content()
            rate_matches = re.findall(r'(\d+\.?\d*)\s*%', rate_text)
            
            if rate_matches:
                rates['main_rate'] = float(rate_matches[0])
            
            # Look for comparison rate
            comparison_elements = await page.query_selector_all(selectors['comparison_rate'])
            for comp_element in comparison_elements:
                comp_text = await comp_element.text_content()
                comp_matches = re.findall(r'(\d+\.?\d*)\s*%', comp_text)
                if comp_matches:
                    rates['comparison_rate'] = float(comp_matches[0])
                    break
        
        except Exception as e:
            logger.warning(f"Error extracting rates: {str(e)}")
        
        return rates
    
    async def _extract_features(self, page: Page, element, selectors: Dict[str, str]) -> List[str]:
        """Extract product features."""
        features = []
        
        try:
            feature_elements = await page.query_selector_all(selectors['features'])
            for feat_element in feature_elements:
                feature_text = await feat_element.text_content()
                if feature_text and len(feature_text.strip()) > 2:
                    features.append(feature_text.strip())
        
        except Exception as e:
            logger.warning(f"Error extracting features: {str(e)}")
        
        return features
    
    async def _extract_fees(self, page: Page, element, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Extract fee information."""
        fees = {}
        
        try:
            fee_elements = await page.query_selector_all(selectors['fees'])
            for fee_element in fee_elements:
                fee_text = await fee_element.text_content()
                if fee_text:
                    # Look for dollar amounts
                    dollar_matches = re.findall(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', fee_text)
                    if dollar_matches:
                        fees['application_fee'] = float(dollar_matches[0].replace(',', ''))
        
        except Exception as e:
            logger.warning(f"Error extracting fees: {str(e)}")
        
        return fees
    
    def _determine_rate_type(self, product_name: str) -> str:
        """Determine if the product is fixed or variable rate."""
        name_lower = product_name.lower()
        if 'fixed' in name_lower:
            return 'fixed'
        elif 'variable' in name_lower:
            return 'variable'
        else:
            return 'variable'  # Default assumption
    
    async def _extract_text_from_selector(self, container, selector: str) -> str:
        """Extract text from a selector within a container."""
        try:
            element = await container.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else ""
        except Exception:
            pass
        return ""
    
    def _is_valid_product_name(self, name: str) -> bool:
        """Check if the product name is valid (not navigation/marketing)."""
        if not name or len(name.strip()) < 3:
            return False
        
        name_lower = name.lower()
        
        # Filter out navigation and marketing content
        invalid_keywords = [
            'menu', 'navigation', 'footer', 'header', 'sidebar',
            'contact', 'about', 'help', 'support', 'login', 'register',
            'search', 'filter', 'sort', 'more', 'learn', 'explore',
            'book', 'appointment', 'call', 'email', 'phone',
            'download', 'app', 'mobile', 'security', 'privacy',
            'terms', 'conditions', 'disclaimer', 'important',
            'frequently asked', 'faq', 'question', 'answer'
        ]
        
        for keyword in invalid_keywords:
            if keyword in name_lower:
                return False
        
        # Must contain loan-related keywords
        loan_keywords = ['loan', 'rate', 'home', 'mortgage', 'fixed', 'variable', 'interest']
        if not any(keyword in name_lower for keyword in loan_keywords):
            return False
        
        return True
    
    async def _extract_rates_from_container(self, container, selectors: Dict[str, str]) -> Dict[str, float]:
        """Extract rates from a product container."""
        rates = {'main_rate': 0.0, 'comparison_rate': 0.0}
        
        try:
            # Extract main rate
            rate_text = await self._extract_text_from_selector(container, selectors['rate'])
            if rate_text:
                rate_matches = re.findall(r'(\d+\.?\d*)\s*%', rate_text)
                if rate_matches:
                    rates['main_rate'] = float(rate_matches[0])
            
            # Extract comparison rate
            comp_text = await self._extract_text_from_selector(container, selectors['comparison_rate'])
            if comp_text:
                comp_matches = re.findall(r'(\d+\.?\d*)\s*%', comp_text)
                if comp_matches:
                    rates['comparison_rate'] = float(comp_matches[0])
        
        except Exception as e:
            logger.warning(f"Error extracting rates: {str(e)}")
        
        return rates
    
    async def _extract_features_from_container(self, container, selectors: Dict[str, str]) -> List[str]:
        """Extract features from a product container."""
        features = []
        
        try:
            feature_elements = await container.query_selector_all(selectors['features'])
            for element in feature_elements:
                feature_text = await element.text_content()
                if feature_text and len(feature_text.strip()) > 2:
                    features.append(feature_text.strip())
        except Exception as e:
            logger.warning(f"Error extracting features: {str(e)}")
        
        return features
    
    async def _extract_fees_from_container(self, container, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Extract fees from a product container."""
        fees = {}
        
        try:
            fee_elements = await container.query_selector_all(selectors['fees'])
            for element in fee_elements:
                fee_text = await element.text_content()
                if fee_text:
                    # Look for dollar amounts
                    dollar_matches = re.findall(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', fee_text)
                    if dollar_matches:
                        fees['application_fee'] = float(dollar_matches[0].replace(',', ''))
        except Exception as e:
            logger.warning(f"Error extracting fees: {str(e)}")
        
        return fees
    
    def _extract_lvr_from_text(self, text: str) -> float:
        """Extract LVR percentage from text."""
        try:
            lvr_matches = re.findall(r'(\d+)\s*%', text)
            if lvr_matches:
                return float(lvr_matches[0])
        except Exception:
            pass
        return 95.0  # Default
    
    async def collect_products(self, lender_config: Dict[str, Any]) -> Dict[str, Any]:
        """Collect products for a specific lender."""
        lender_name = lender_config.get('abbreviation', 'Unknown')
        urls = lender_config.get('collection_urls', [])
        
        all_products = []
        errors = []
        
        for url in urls:
            try:
                products = await self.collect_from_url(url, lender_name)
                all_products.extend(products)
            except Exception as e:
                error_msg = f"Error collecting from {url}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            'lender': lender_name,
            'products': all_products,
            'status': 'success' if not errors else 'partial',
            'errors': errors,
            'timestamp': datetime.now().isoformat()
        }
