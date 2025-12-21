"""
Collector Agent - Web Scraping and Data Extraction

ROLE: Worker Agent (Data Collection)
PURPOSE: Extracts loan product data from lender websites using Playwright

This agent implements a multi-strategy extraction approach to handle different
website structures. It tries strategies in order of reliability until one succeeds.

EXTRACTION STRATEGIES (in order):
1. Network Introspection - Captures JSON API responses (fastest, most reliable)
2. JSON-LD Structured Data - Parses schema.org structured data
3. Embedded JavaScript State - Extracts from window.__NEXT_DATA__, dataLayer, etc.
4. Select Dropdowns - Parses rate dropdowns (ANZ-style pages)
5. DOM Parsing - Fallback text-based extraction

FEATURES:
- Multi-strategy fallback (tries 5 different methods)
- Network monitoring (captures API calls)
- BIAN schema compliance (returns standardized LoanProduct objects)
- Error resilience (continues if one strategy fails)
- Async/await support (non-blocking operations)

DEPENDENCIES:
- Playwright (browser automation)
- LoanProduct models (BIAN schema)

USAGE:
    async with PlaywrightCollectorAgent(headless=True) as collector:
        products = await collector.collect_from_url(
            url="https://example.com/rates",
            lender_name="ANZ"
        )
"""

import os
import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from playwright.async_api import async_playwright, Browser, Page
from ...models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria

logger = logging.getLogger(__name__)


class PlaywrightCollectorAgent:
    """
    Playwright-based collector agent for extracting loan product data.
    
    This agent uses Playwright to automate browser interactions and extract
    loan product information from lender websites. It implements a smart
    multi-strategy approach that adapts to different website structures.
    
    The agent tries extraction strategies in order of reliability:
    1. Network introspection (captured JSON APIs) - Fastest, most reliable
    2. JSON-LD structured data - Standardized schema.org format
    3. Embedded JavaScript state - Next.js, Nuxt, GTM dataLayer
    4. Select dropdowns - ANZ/CBA style rate dropdowns
    5. DOM parsing - Fallback text-based extraction
    
    Attributes:
        headless: Run browser in headless mode
        timeout: Page load timeout in milliseconds
        browser: Playwright browser instance
        collected_products: List of collected products
    
    Example:
        >>> async with PlaywrightCollectorAgent(headless=True) as collector:
        ...     products = await collector.collect_from_url(
        ...         url="https://www.anz.com.au/home-loans/interest-rates/",
        ...         lender_name="ANZ"
        ...     )
        ...     print(f"Collected {len(products)} products")
    """
    
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
            
            # Detect page structure and wait appropriately for dynamic content
            page_structure = await self._detect_page_structure(page)
            logger.debug(f"   Detected page structure: {page_structure}")
            
            # Wait for dynamic content based on detected structure
            if 'compare_cards' in page_structure or 'data_cell_rates' in page_structure:
                # Wait for rate elements to populate (CommBank-style)
                try:
                    await page.wait_for_function(
                        """() => {
                            const rateElements = document.querySelectorAll('[data-cell="interest-rate"], [data-cell="comparison-rate"]');
                            if (rateElements.length > 0) {
                                return Array.from(rateElements).some(el => el.textContent.trim().length > 0);
                            }
                            return false;
                        }""",
                        timeout=10000
                    )
                    await page.wait_for_timeout(2000)  # Additional wait for API completion
                except Exception as e:
                    logger.debug(f"   Timeout waiting for rate elements: {e}")
                    await page.wait_for_timeout(5000)  # Fallback wait
            else:
                # Standard wait for dynamic content and API calls
                await page.wait_for_timeout(3000)
            
            # Try multiple extraction strategies
            products = await self._smart_extract_products(page, lender_name, url, selectors, captured_apis, page_structure)
            
        except Exception as e:
            logger.error(f"Error collecting from {url}: {str(e)}")
        finally:
            await page.close()
        
        return products
    
    async def analyze_page_structure(self, url: str) -> Dict[str, Any]:
        """
        Analyze a page to determine the best extraction strategy.
        
        This is a public method that can be called by the workflow to analyze
        page structure before collection. It returns recommended strategy and
        available strategies.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Dict with:
                - recommended_strategy: Best strategy to use
                - available_strategies: List of strategies found
                - page_structure: Detected page structure details
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use async context manager.")
        
        page = await self.browser.new_page()
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
            await page.wait_for_timeout(3000)  # Wait for dynamic content
            
            # Detect page structure
            page_structure = await self._detect_page_structure(page)
            
            # Determine recommended strategy based on detected structure
            strategies_found = []
            recommended_strategy = "dom-parsing"  # Default fallback
            
            # Priority order: json-ld > embedded-state > select-dropdown > html-table > dom-parsing
            if page_structure.get('json_ld'):
                strategies_found.append("json-ld")
                recommended_strategy = "json-ld"
            
            if page_structure.get('embedded_state'):
                strategies_found.append("embedded-state")
                if recommended_strategy == "dom-parsing":
                    recommended_strategy = "embedded-state"
            
            if page_structure.get('select_dropdowns'):
                strategies_found.append("select-dropdown")
                if recommended_strategy not in ["json-ld", "embedded-state"]:
                    recommended_strategy = "select-dropdown"
            
            if page_structure.get('compare_cards') or page_structure.get('data_cell_rates'):
                strategies_found.append("compare-cards")
                if recommended_strategy not in ["json-ld", "embedded-state", "select-dropdown"]:
                    recommended_strategy = "compare-cards"
            
            # Check for HTML tables with rates
            tables = await page.query_selector_all('table')
            table_with_rates_count = 0
            for table in tables:
                text = await table.inner_text()
                if re.search(r'([\d.]+)%\s*p\.a', text, re.IGNORECASE):
                    table_with_rates_count += 1
            if table_with_rates_count > 0:
                strategies_found.append("html-table")
                if recommended_strategy not in ["json-ld", "embedded-state", "select-dropdown", "compare-cards"]:
                    recommended_strategy = "html-table"
            
            if not strategies_found:
                strategies_found.append("dom-parsing")
            
            return {
                "recommended_strategy": recommended_strategy,
                "available_strategies": strategies_found,
                "page_structure": page_structure
            }
        finally:
            await page.close()
    
    async def _detect_page_structure(self, page: Page) -> Dict[str, bool]:
        """
        Analyze page structure to detect available extraction strategies.
        
        Returns a dict indicating which structures are present:
        - compare_cards: CommBank-style compare cards with data-cell attributes
        - data_cell_rates: Elements with data-cell="interest-rate" or "comparison-rate"
        - select_dropdowns: Rate selection dropdowns
        - json_ld: JSON-LD structured data
        - embedded_state: JavaScript state objects
        """
        structure = {
            'compare_cards': False,
            'data_cell_rates': False,
            'select_dropdowns': False,
            'json_ld': False,
            'embedded_state': False
        }
        
        try:
            # Check for compare cards (CommBank-style)
            compare_cards = await page.query_selector_all('.compare-card, .compare-carditem, [class*="compare-card"]')
            if compare_cards:
                structure['compare_cards'] = True
                logger.debug(f"   Found {len(compare_cards)} compare cards")
            
            # Check for data-cell rate attributes
            data_cell_elements = await page.query_selector_all('[data-cell="interest-rate"], [data-cell="comparison-rate"]')
            if data_cell_elements:
                structure['data_cell_rates'] = True
                logger.debug(f"   Found {len(data_cell_elements)} data-cell rate elements")
            
            # Check for select dropdowns
            rate_selects = await page.query_selector_all('select[id*="rate"], select[id*="Rate"], select[class*="rate"]')
            if rate_selects:
                structure['select_dropdowns'] = True
                logger.debug(f"   Found {len(rate_selects)} rate select dropdowns")
            
            # Check for JSON-LD
            jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            if jsonld_scripts:
                structure['json_ld'] = True
                logger.debug(f"   Found {len(jsonld_scripts)} JSON-LD scripts")
            
            # Check for embedded state
            has_state = await page.evaluate("""() => {
                return !!(globalThis.__NEXT_DATA__ || globalThis.__NUXT__ || 
                         globalThis.dataLayer || globalThis.Shopify);
            }""")
            if has_state:
                structure['embedded_state'] = True
                logger.debug("   Found embedded JavaScript state")
        
        except Exception as e:
            logger.debug(f"Page structure detection failed: {e}")
        
        return structure
    
    async def _smart_extract_products(
        self, 
        page: Page, 
        lender_name: str, 
        url: str, 
        selectors: Dict[str, str] = None,
        captured_apis: List[Dict] = None,
        page_structure: Dict[str, bool] = None
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
        logger.debug("=" * 60)
        logger.debug(f"🔄 [COLLECTOR] Starting multi-strategy extraction for {lender_name}")
        logger.debug(f"   URL: {url}")
        
        products = []
        captured_apis = captured_apis or []
        
        # Strategy 0: Network introspection - check captured JSON APIs
        if captured_apis:
            logger.debug(f"   [STRATEGY 0] Trying Network introspection ({len(captured_apis)} APIs captured)")
            products = await self._extract_from_captured_apis(captured_apis, lender_name, url)
            if products:
                logger.info(f"   ✅ [STRATEGY 0 SUCCESS] Extracted {len(products)} products via captured JSON API")
                return products
            else:
                logger.debug(f"   ❌ [STRATEGY 0 FAILED] No products found in captured APIs")
        
        # Strategy 1: JSON-LD structured data
        logger.debug("   [STRATEGY 1] Trying JSON-LD structured data")
        products = await self._extract_from_jsonld(page, lender_name, url)
        if products:
            logger.info(f"   ✅ [STRATEGY 1 SUCCESS] Extracted {len(products)} products via JSON-LD")
            return products
        else:
            logger.debug(f"   ❌ [STRATEGY 1 FAILED] No JSON-LD products found")
        
        # Strategy 2: Embedded JavaScript state
        logger.debug("   [STRATEGY 2] Trying Embedded JavaScript state")
        products = await self._extract_from_embedded_state(page, lender_name, url)
        if products:
            logger.info(f"   ✅ [STRATEGY 2 SUCCESS] Extracted {len(products)} products via embedded state")
            return products
        else:
            logger.debug(f"   ❌ [STRATEGY 2 FAILED] No embedded state products found")
        
        # Strategy 2.5: Compare cards with data-cell attributes (CommBank-style, but detected dynamically)
        page_structure = page_structure or await self._detect_page_structure(page)
        if page_structure.get('compare_cards') or page_structure.get('data_cell_rates'):
            logger.debug("   [STRATEGY 2.5] Trying Compare cards with data-cell attributes")
            products = await self._extract_from_compare_cards(page, lender_name, url)
            if products:
                logger.info(f"   ✅ [STRATEGY 2.5 SUCCESS] Extracted {len(products)} products via compare cards")
                return products
            else:
                logger.debug(f"   ❌ [STRATEGY 2.5 FAILED] No compare card products found")
        
        # Strategy 3: Select dropdowns (ANZ, CBA use this)
        logger.debug("   [STRATEGY 3] Trying Select dropdowns")
        products = await self._extract_from_select_dropdowns(page, lender_name, url)
        if products:
            logger.info(f"   ✅ [STRATEGY 3 SUCCESS] Extracted {len(products)} products via select dropdown")
            return products
        else:
            logger.debug(f"   ❌ [STRATEGY 3 FAILED] No dropdown products found")
        
        # Strategy 4: Fallback to DOM parsing
        logger.debug("   [STRATEGY 4] Trying DOM parsing (fallback)")
        products = await self._extract_products(page, lender_name, url, selectors)
        if products:
            logger.info(f"   ✅ [STRATEGY 4 SUCCESS] Extracted {len(products)} products via DOM parsing")
        else:
            logger.warning(f"   ⚠️  [ALL STRATEGIES FAILED] No products found with any strategy")
        
        logger.debug(f"   Final result: {len(products)} products extracted")
        logger.debug("=" * 60)
        
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
    
    async def _extract_from_compare_cards(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from compare cards with data-cell attributes (CommBank-style).
        
        Looks for:
        - .compare-card or .compare-carditem elements
        - Elements with data-cell="interest-rate" and data-cell="comparison-rate"
        - Product names in card headers
        """
        products = []
        
        try:
            # Find all compare cards
            cards = await page.query_selector_all('.compare-card, .compare-carditem, [class*="compare-card"]')
            
            if not cards:
                logger.debug("   No compare cards found")
                return products
            
            logger.debug(f"   Found {len(cards)} compare cards")
            
            for card in cards:
                try:
                    # Extract product name from card header
                    name_elem = await card.query_selector('h2, .compare-card-head h2, .head-content h2')
                    if not name_elem:
                        name_elem = await card.query_selector('.compare-card-head, .head-content')
                    
                    name = ""
                    if name_elem:
                        name = await name_elem.inner_text()
                        name = name.strip()
                    
                    if not name:
                        # Try to get from card ID or data attributes
                        card_id = await card.get_attribute('id')
                        if card_id:
                            name = card_id.replace('-', ' ').replace('_', ' ').title()
                    
                    if not name:
                        continue
                    
                    # Extract interest rate
                    interest_rate_elem = await card.query_selector('[data-cell="interest-rate"]')
                    interest_rate = 0.0
                    if interest_rate_elem:
                        rate_text = await interest_rate_elem.inner_text()
                        rate_match = re.search(r'([\d.]+)', rate_text)
                        if rate_match:
                            interest_rate = float(rate_match.group(1))
                    
                    # Extract comparison rate
                    comparison_rate_elem = await card.query_selector('[data-cell="comparison-rate"]')
                    comparison_rate = interest_rate  # Default to interest rate
                    if comparison_rate_elem:
                        comp_rate_text = await comparison_rate_elem.inner_text()
                        comp_rate_match = re.search(r'([\d.]+)', comp_rate_text)
                        if comp_rate_match:
                            comparison_rate = float(comp_rate_match.group(1))
                    
                    # Determine rate type from product name
                    rate_type = "Variable"
                    if "fixed" in name.lower() or "fix" in name.lower():
                        rate_type = "Fixed"
                    
                    if interest_rate > 0:
                        product = LoanProduct(
                            product_id=f"{lender_name}-CC-{re.sub(r'[^a-zA-Z0-9]', '-', name)[:50]}",
                            version="1.0",
                            status="active",
                            name=f"{lender_name} {name}",
                            short_name=name,
                            description=f"{name} from {lender_name}",
                            purpose="OwnerOccupied_Purchase",
                            channels=["Branch", "Online"],
                            interest_components=[
                                InterestComponent(
                                    name=name,
                                    rate_type=rate_type,
                                    interest_rate_pct_au=interest_rate if interest_rate != comparison_rate else None,
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
                                max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": 0.80}],
                                property_types_allowed=["House", "Apartment", "Townhouse"]
                            ),
                            lender=lender_name,
                            source_url=url
                        )
                        products.append(product)
                        logger.debug(f"   Extracted from compare card: {name} ({interest_rate}%)")
                
                except Exception as e:
                    logger.debug(f"   Failed to extract from compare card: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"Compare card extraction failed: {e}")
        
        return products
    
    async def _extract_from_select_dropdowns(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from select dropdowns (ANZ-style).
        
        ANZ embeds products in:
        <select id="...InterestRate...">
          <option>6.49% p.a Standard Variable 80% or less LVR</option>
        </select>
        
        Also checks for LVR tier tables that may be on the same page.
        """
        products = []
        
        try:
            # First, check for LVR tier tables (e.g., ANZ rate tables with multiple LVR tiers)
            lvr_tier_products = await self._extract_lvr_tier_tables(page, lender_name, url)
            if lvr_tier_products:
                products.extend(lvr_tier_products)
                logger.info(f"Found {len(lvr_tier_products)} products from LVR tier tables")
            
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
                        applicability={
                            "lvr_tier": lvr_text if lvr_text else None,
                            "lvr_max": lvr_value,
                            "lvr_min": 0.0 if lvr_text and "or less" in lvr_text.lower() else None
                        } if lvr_text else {}
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
    
    async def _extract_lvr_tier_tables(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from LVR tier tables (e.g., ANZ rate tables).
        
        Looks for tables with structure:
        LVR Tier | Comparison Rate (p.a.)
        ≤ 60%    | 5.65%
        ≤ 70%    | 5.70%
        ≤ 80%    | 5.80%
        ≤ 90%    | 6.34%
        > 90%    | 6.89%
        Index rate | 7.24%
        """
        products = []
        
        try:
            # Find tables that might contain LVR tier data
            tables = await page.query_selector_all('table')
            
            for table in tables:
                table_text = await table.inner_text()
                
                # Check if table contains LVR tier indicators
                if not (('lvr' in table_text.lower() or 'loan to value' in table_text.lower()) and 
                        ('rate' in table_text.lower() or '%' in table_text)):
                    continue
                
                # Extract table rows
                rows = await table.query_selector_all('tr')
                if len(rows) < 2:  # Need at least header + 1 data row
                    continue
                
                # Try to find header row
                header_row = rows[0]
                header_text = await header_row.inner_text()
                
                # Check if this looks like an LVR tier table
                if 'lvr' not in header_text.lower() and 'tier' not in header_text.lower():
                    continue
                
                # Extract LVR tiers from data rows
                lvr_tiers = []
                product_name = None
                
                for row in rows[1:]:  # Skip header
                    cells = await row.query_selector_all('td, th')
                    if len(cells) < 2:
                        continue
                    
                    tier_text = await cells[0].inner_text()
                    rate_text = await cells[1].inner_text()
                    
                    # Parse LVR tier (e.g., "≤ 60%", "> 90%", "Index rate")
                    tier_match = re.search(r'([≤<>]|Index)\s*([\d]+)?%?', tier_text)
                    rate_match = re.search(r'([\d.]+)%', rate_text)
                    
                    if tier_match and rate_match:
                        operator = tier_match.group(1)
                        tier_value = tier_match.group(2)
                        rate = float(rate_match.group(1))
                        
                        # Determine LVR range
                        if operator == "Index" or tier_text.lower() == "index rate":
                            lvr_tiers.append({
                                "tier": "Index rate",
                                "rate": rate,
                                "lvr_min": 0.0,
                                "lvr_max": 1.0,
                                "is_index": True
                            })
                        elif operator == "≤":
                            max_lvr = float(tier_value) / 100 if tier_value else 1.0
                            # Find previous tier's max to determine min
                            prev_max = 0.0
                            for existing_tier in lvr_tiers:
                                if existing_tier.get("lvr_max", 0) > prev_max:
                                    prev_max = existing_tier.get("lvr_max", 0)
                            
                            lvr_tiers.append({
                                "tier": f"≤ {tier_value}%",
                                "rate": rate,
                                "lvr_min": prev_max,
                                "lvr_max": max_lvr,
                                "lvr_exclusive_max": False
                            })
                        elif operator == ">":
                            min_lvr = float(tier_value) / 100 if tier_value else 0.0
                            lvr_tiers.append({
                                "tier": f"> {tier_value}%",
                                "rate": rate,
                                "lvr_min": min_lvr,
                                "lvr_max": 1.0,
                                "lvr_exclusive_max": True
                            })
                
                # If we found LVR tiers, create a product with multiple interest components
                if lvr_tiers and len(lvr_tiers) > 1:
                    # Try to get product name from page context
                    product_name = await self._extract_product_name_from_context(page, table)
                    if not product_name:
                        product_name = f"{lender_name} Variable Rate"
                    
                    # Create interest components for each LVR tier
                    interest_components = []
                    for tier in lvr_tiers:
                        component_name = f"{product_name} - {tier['tier']}"
                        rate_type = "VariableIndex" if tier.get("is_index") else "Variable"
                        
                        interest_components.append(
                            InterestComponent(
                                name=component_name,
                                rate_type=rate_type,
                                comparison_rate_pct_au=Decimal(str(tier["rate"])),
                                applicability={
                                    "lvr_tier": tier["tier"],
                                    "lvr_min": tier["lvr_min"],
                                    "lvr_max": tier["lvr_max"],
                                    "lvr_exclusive_max": tier.get("lvr_exclusive_max", False)
                                }
                            )
                        )
                    
                    # Create product with multiple LVR tier components
                    product = LoanProduct(
                        product_id=f"{lender_name}-{re.sub(r'[^a-zA-Z0-9]', '-', product_name)[:50]}",
                        version="1.0",
                        status="active",
                        name=f"{lender_name} {product_name}",
                        short_name=product_name,
                        description=f"{product_name} with LVR tiered rates from {lender_name}",
                        purpose="OwnerOccupied_Purchase",
                        channels=["Branch", "Online"],
                        interest_components=interest_components,
                        fees=FeeStructure(),
                        features=ProductFeatures(),
                        eligibility=EligibilityCriteria(
                            min_loan_amount_aud=20000,
                            max_loan_amount_aud=2000000,
                            min_age_years=18,
                            residency=["AustralianCitizen", "PermanentResident"],
                            borrower_types=["Individual"],
                            occupancy=["OwnerOccupied"],
                            max_lvr_by_segment=[{"segment": "OwnerOccupied", "maxLVR": 0.95}],
                            property_types_allowed=["House", "Apartment", "Townhouse"]
                        ),
                        lender=lender_name,
                        source_url=url
                    )
                    products.append(product)
                    logger.debug(f"   Extracted product with {len(lvr_tiers)} LVR tiers: {product_name}")
        
        except Exception as e:
            logger.debug(f"LVR tier table extraction failed: {e}")
        
        return products
    
    async def _extract_product_name_from_context(self, page: Page, table_element) -> Optional[str]:
        """Extract product name from page context around a table."""
        try:
            # Look for headings before the table
            table_parent = await table_element.evaluate_handle('el => el.closest("div, section, article")')
            if table_parent:
                # Check for headings in the same container
                headings = await table_parent.query_selector_all('h1, h2, h3, h4')
                for heading in headings:
                    heading_text = await heading.inner_text()
                    if heading_text and len(heading_text) < 100:  # Reasonable length
                        return heading_text.strip()
            
            # Fallback: look for product name in table caption
            caption = await table_element.query_selector('caption')
            if caption:
                caption_text = await caption.inner_text()
                if caption_text:
                    return caption_text.strip()
            
            return None
        except Exception:
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
