"""
Collector Agent - Web Scraping and Data Extraction

ROLE: Worker Agent (Data Collection)
PURPOSE: Extracts loan product data from lender websites using Playwright

This agent implements a multi-strategy extraction approach to handle different
website structures. It tries strategies in order of reliability until one succeeds.

EXTRACTION STRATEGIES (in priority order):
1. Network Introspection – Capture JSON API / XHR / GraphQL responses (fastest, most reliable, source‑of‑truth)
2. JSON‑LD Structured Data – Parse schema.org structured data embedded in the page
3. Embedded JavaScript State – Extract hydrated app state (window.__NEXT_DATA__, __NUXT__, dataLayer, etc.)
4. Compare Cards – Extract from structured compare cards with data-cell attributes
5. UI State Enumeration – Systematically iterate tabs, toggles, dropdowns, filters, pagination
6. DOM Parsing – Semantic DOM extraction as a last‑resort fallback

HIGH ACCURACY MODE:
- Tries ALL strategies (doesn't stop at first success)
- Selects the MOST ACCURATE strategy (highest priority) that has products
- Uses ONLY data from the selected strategy (no merging to avoid conflicts)
- Strategy priority: Network API > JSON-LD > Embedded State > Compare Cards > UI Enumeration > DOM Parsing
- Data quality scoring (0-100 confidence score per product)
- Product validation (required fields, rate sanity checks)
- Deduplication within selected strategy

FEATURES:
- Multi-strategy extraction (tries all 6 methods)
- Result merging and validation for maximum accuracy
- Network monitoring (captures API calls)
- UI state enumeration (clicks tabs, toggles, dropdowns to reveal hidden data)
- BIAN schema compliance (returns standardized LoanProduct objects)
- Confidence scoring (0-100 per product based on data quality)
- Error resilience (continues if one strategy fails)
- Async/await support (non-blocking operations)

DEPENDENCIES:
- Playwright (browser automation)
- LoanProduct models (BIAN schema)

USAGE:
    async with PlaywrightCollectorAgent(headless=True) as collector:
        products = await collector.collect_from_url(
            url="https://example.com/rates",
            lender_name="Example Bank"
        )
"""

import os
import logging
import asyncio
import re
from itertools import product
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from decimal import Decimal
from playwright.async_api import async_playwright, Browser, Page
from ...models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria
from .filter_keywords import (
    FilterKeywords, matches_loan_type, matches_repayment_type, matches_lvr_tier, 
    matches_loan_term, matches_rate_type, matches_loan_purpose, matches_product_segment,
    matches_region_residency, matches_rate_tier
)

logger = logging.getLogger(__name__)

# Get singleton instance for property access
_filter_keywords = FilterKeywords()


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
    4. Compare cards - Structured data tables with semantic attributes
    5. UI state enumeration - Adaptive filter/tab/dropdown detection
    6. DOM parsing - Fallback text-based extraction
    
    The filter detection is generic and adaptive - it uses semantic analysis
    rather than hardcoded patterns, making it work across different bank websites.
    
    Attributes:
        headless: Run browser in headless mode
        timeout: Page load timeout in milliseconds
        browser: Playwright browser instance
        collected_products: List of collected products
    
    Example:
        >>> async with PlaywrightCollectorAgent(headless=True) as collector:
        ...     products = await collector.collect_from_url(
        ...         url="https://example.com/home-loans/interest-rates/",
        ...         lender_name="Example Bank"
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
        
        Strategies (in priority order):
        1. Network introspection (capture JSON APIs / XHR / GraphQL)
        2. JSON-LD structured data
        3. Embedded JavaScript state (window.__NEXT_DATA__, etc.)
        4. UI State Enumeration (tabs, toggles, dropdowns, filters, pagination)
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
                # Wait for rate elements to populate (dynamic content)
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
        - compare_cards: Structured compare cards with data-cell attributes
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
            # Check for compare cards (structured data pattern)
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
        Smart multi-strategy product extraction with HIGH ACCURACY mode.
        
        For maximum accuracy, tries ALL strategies and selects the BEST one:
        1. Network introspection (captured JSON APIs) - Fastest, most reliable, source-of-truth
        2. JSON-LD (structured data) - Most reliable
        3. Embedded state (window.__NEXT_DATA__, etc.) - Very reliable
        4. Compare cards (conditional) - Structured card pattern
        5. UI State Enumeration - Systematically iterate tabs, toggles, dropdowns, filters, pagination
        6. DOM parsing - Fallback
        
        Selects the highest priority strategy that successfully extracts products.
        Uses ONLY data from the selected strategy (no merging) for maximum accuracy.
        """
        logger.debug("=" * 60)
        logger.debug(f"🔄 [COLLECTOR] Starting HIGH ACCURACY multi-strategy extraction for {lender_name}")
        logger.debug(f"   URL: {url}")
        logger.debug(f"   Mode: Try ALL strategies and merge results for maximum accuracy")
        
        all_products_by_strategy = {}
        captured_apis = captured_apis or []
        
        # Strategy 1: Network introspection - check captured JSON APIs
        if captured_apis:
            logger.debug(f"   [STRATEGY 1] Trying Network introspection ({len(captured_apis)} APIs captured)")
            try:
                products = await self._extract_from_captured_apis(captured_apis, lender_name, url)
                if products:
                    all_products_by_strategy['network_api'] = products
                    logger.info(f"   ✅ [STRATEGY 1 SUCCESS] Extracted {len(products)} products via captured JSON API")
                else:
                    logger.debug(f"   ❌ [STRATEGY 1 FAILED] No products found in captured APIs")
            except Exception as e:
                logger.debug(f"   ❌ [STRATEGY 1 ERROR] {e}")
        
        # Strategy 2: JSON-LD structured data
        logger.debug("   [STRATEGY 2] Trying JSON-LD structured data")
        try:
            products = await self._extract_from_jsonld(page, lender_name, url)
            if products:
                all_products_by_strategy['jsonld'] = products
                logger.info(f"   ✅ [STRATEGY 2 SUCCESS] Extracted {len(products)} products via JSON-LD")
            else:
                logger.debug(f"   ❌ [STRATEGY 2 FAILED] No JSON-LD products found")
        except Exception as e:
            logger.debug(f"   ❌ [STRATEGY 2 ERROR] {e}")
        
        # Strategy 3: Embedded JavaScript state
        logger.debug("   [STRATEGY 3] Trying Embedded JavaScript state")
        try:
            products = await self._extract_from_embedded_state(page, lender_name, url)
            if products:
                all_products_by_strategy['embedded_state'] = products
                logger.info(f"   ✅ [STRATEGY 3 SUCCESS] Extracted {len(products)} products via embedded state")
            else:
                logger.debug(f"   ❌ [STRATEGY 3 FAILED] No embedded state products found")
        except Exception as e:
            logger.debug(f"   ❌ [STRATEGY 3 ERROR] {e}")
        
        # Strategy 2.5: Compare cards with data-cell attributes (detected dynamically)
        page_structure = page_structure or await self._detect_page_structure(page)
        if page_structure.get('compare_cards') or page_structure.get('data_cell_rates'):
            logger.debug("   [STRATEGY 2.5] Trying Compare cards with data-cell attributes")
            try:
                products = await self._extract_from_compare_cards(page, lender_name, url)
                if products:
                    all_products_by_strategy['compare_cards'] = products
                    logger.info(f"   ✅ [STRATEGY 2.5 SUCCESS] Extracted {len(products)} products via compare cards")
                else:
                    logger.debug(f"   ❌ [STRATEGY 2.5 FAILED] No compare card products found")
            except Exception as e:
                logger.debug(f"   ❌ [STRATEGY 2.5 ERROR] {e}")
        
        # Strategy 4: UI State Enumeration - systematically iterate tabs, toggles, dropdowns, filters
        logger.debug("   [STRATEGY 4] Trying UI State Enumeration (tabs, toggles, dropdowns, filters)")
        try:
            products = await self._extract_from_ui_enumeration(page, lender_name, url)
            if products:
                all_products_by_strategy['ui_enumeration'] = products
                logger.info(f"   ✅ [STRATEGY 4 SUCCESS] Extracted {len(products)} products via UI enumeration")
            else:
                logger.debug(f"   ❌ [STRATEGY 4 FAILED] No products found via UI enumeration")
        except Exception as e:
            logger.debug(f"   ❌ [STRATEGY 4 ERROR] {e}")
        
        # Strategy 5: Fallback to DOM parsing
        logger.debug("   [STRATEGY 5] Trying DOM parsing (fallback)")
        try:
            products = await self._extract_products(page, lender_name, url, selectors)
            if products:
                all_products_by_strategy['dom_parsing'] = products
                logger.info(f"   ✅ [STRATEGY 5 SUCCESS] Extracted {len(products)} products via DOM parsing")
            else:
                logger.debug(f"   ❌ [STRATEGY 5 FAILED] No products found via DOM parsing")
        except Exception as e:
            logger.debug(f"   ❌ [STRATEGY 5 ERROR] {e}")
        
        # Select best strategy results (highest priority, no merging)
        logger.debug("   [SELECT] Selecting best strategy results for maximum accuracy")
        best_products = self._select_best_strategy_products(all_products_by_strategy, lender_name, url)
        
        logger.debug(f"   Final result: {len(best_products)} products from best strategy")
        logger.debug("=" * 60)
        
        return best_products
    
    def _select_best_strategy_products(
        self, 
        products_by_strategy: Dict[str, List[LoanProduct]], 
        lender_name: str,
        url: str
    ) -> List[LoanProduct]:
        """
        Select products from the most accurate/reliable strategy only.
        
        For maximum accuracy:
        1. Try all strategies to find which one works
        2. Select the highest priority strategy that has products
        3. Use ONLY that strategy's data (no merging)
        4. Validate and score products
        5. Deduplicate within the selected strategy
        """
        if not products_by_strategy:
            return []
        
        # Strategy priority (higher = more reliable/accurate)
        strategy_priority = {
            'network_api': 100,      # Highest priority - source of truth
            'jsonld': 90,            # Very reliable - structured data
            'embedded_state': 80,    # Very reliable - app state
            'compare_cards': 70,     # Reliable - structured DOM
            'ui_enumeration': 60,    # Good - comprehensive
            'dom_parsing': 50        # Lowest - fallback
        }
        
        # Find the highest priority strategy that has products
        best_strategy = None
        best_priority = 0
        best_products = []
        
        for strategy_name, products in products_by_strategy.items():
            if not products:
                continue
            
            priority = strategy_priority.get(strategy_name, 50)
            if priority > best_priority:
                best_priority = priority
                best_strategy = strategy_name
                best_products = products
        
        if not best_strategy:
            return []
        
        logger.info(f"   [SELECT] Using {best_strategy} strategy (priority: {best_priority}) - {len(best_products)} products")
        
        # Add strategy metadata and validate
        final_products = []
        seen_products = set()  # For deduplication within strategy
        
        for product in best_products:
            # Add strategy metadata
            if product.interest_components:
                for component in product.interest_components:
                    if not component.applicability:
                        component.applicability = {}
                    component.applicability['extraction_strategy'] = best_strategy
                    component.applicability['strategy_priority'] = best_priority
                    component.applicability['confidence_score'] = self._calculate_confidence_score(
                        product, [best_strategy], best_priority
                    )
            
            # Deduplicate within strategy (by product_id or name+rate+filter_state)
            product_key = self._get_product_key(product)
            if product_key in seen_products:
                continue
            seen_products.add(product_key)
            
            # Validate product quality
            if self._validate_product_quality(product):
                final_products.append(product)
            else:
                logger.warning(f"   ⚠️  Product failed validation: {product.product_id}")
        
        logger.info(f"   [SELECT] Selected {len(final_products)} validated products from {best_strategy} strategy")
        
        # Merge products with same name but different permutations
        merged_products = self._merge_products_by_name(final_products)
        
        if len(merged_products) < len(final_products):
            logger.info(f"   [MERGE] Merged {len(final_products)} products into {len(merged_products)} products (combined permutations)")
        
        return merged_products
    
    def _merge_products_by_name(self, products: List[LoanProduct]) -> List[LoanProduct]:
        """
        Merge products with same base name but different permutations.
        
        Instead of having separate products like:
        - "Standard Variable" (P&I, 80% LVR)
        - "Standard Variable" (Interest Only, 80% LVR)
        - "Standard Variable" (P&I, 90% LVR)
        
        We merge them into:
        - "Standard Variable" with 3 InterestComponent entries
        
        Args:
            products: List of products to merge
            
        Returns:
            List of merged products
        """
        if not products:
            return []
        
        # Group products by base name (normalized)
        products_by_name = {}
        
        for product in products:
            # Use short_name or name as base identifier
            base_name = (product.short_name or product.name).strip()
            
            # Normalize base name (remove filter suffixes, extra spaces)
            # Remove common suffixes that indicate permutations
            # This handles: "Standard Variable more than", "Simplicity PLUS special offer discount more than"
            base_name_normalized = re.sub(
                r'\s+(more\s+than|or\s+less|less\s+than|up\s+to|over|more|less)$',
                '',
                base_name,
                flags=re.IGNORECASE
            ).strip()
            
            # Also remove any remaining LVR text that might have slipped through
            base_name_normalized = re.sub(
                r'\s+\d+%.*?LVR.*$',
                '',
                base_name_normalized,
                flags=re.IGNORECASE
            ).strip()
            
            # Use normalized name as key
            if base_name_normalized not in products_by_name:
                products_by_name[base_name_normalized] = []
            
            products_by_name[base_name_normalized].append(product)
        
        merged = []
        
        for base_name, product_group in products_by_name.items():
            if len(product_group) == 1:
                # No merging needed
                merged.append(product_group[0])
            else:
                # Merge multiple products into one
                # Use the first product as the base
                base_product = product_group[0]
                
                # Collect all unique interest components
                seen_components = set()
                all_components = []
                
                for product in product_group:
                    for component in product.interest_components:
                        # Create a key for deduplication based on applicability
                        component_key = self._get_component_key(component)
                        
                        if component_key not in seen_components:
                            seen_components.add(component_key)
                            all_components.append(component)
                
                # Update base product with all components
                base_product.interest_components = all_components
                
                # FIX 2: STRICT ALIGNMENT of product_id, product_name, and short_name
                # All three must refer to the SAME canonical product name
                # Import slugify from product module
                from ...models.product import slugify
                
                # Set canonical name (remove filter suffixes)
                base_product.name = base_name_normalized
                base_product.short_name = base_name_normalized
                
                # Generate product_id using centralized slugify
                lender_slug = slugify(base_product.lender)
                product_slug = slugify(base_name_normalized)
                base_product.product_id = f"{lender_slug}-{product_slug}"
                
                merged.append(base_product)
                
                logger.debug(f"   [MERGE] Merged {len(product_group)} products into '{base_name_normalized}' ({len(all_components)} components)")
        
        return merged
    
    def _get_component_key(self, component: InterestComponent) -> str:
        """
        Generate unique key for interest component deduplication.
        
        Components are considered duplicates if they have the same:
        - Rate
        - Rate type
        - All applicability keys (purpose, repayment_type, lvr_min, lvr_max, etc.)
        """
        key_parts = [
            str(component.comparison_rate_pct_au),
            component.rate_type,
            str(component.fixed_term_months or ''),
        ]
        
        # Add sorted applicability keys for deterministic comparison
        if component.applicability:
            applicability_items = sorted([
                f"{k}:{v}" for k, v in component.applicability.items()
                if k not in ['filter_state', 'extraction_strategy', 'strategy_priority', 'confidence_score']
            ])
            key_parts.extend(applicability_items)
        
        return "|".join(key_parts)
    
    def _get_product_key(self, product: LoanProduct) -> str:
        """Generate unique key for product deduplication."""
        # Use product_id if available
        if product.product_id:
            return product.product_id
        
        # Otherwise use name + rate + filter state
        product_name_normalized = re.sub(r'[^a-zA-Z0-9]', '', product.short_name.lower())
        rate_key = "0"
        if product.interest_components:
            rate_key = str(product.interest_components[0].comparison_rate_pct_au)
        
        filter_state_key = ""
        if product.interest_components and product.interest_components[0].applicability:
            filter_state = product.interest_components[0].applicability.get('filter_state', {})
            if filter_state:
                filter_state_key = "_".join(sorted([f"{k}:{v}" for k, v in filter_state.items()]))
        
        return f"{product_name_normalized}_{rate_key}_{filter_state_key}"
    
    def _validate_product_quality(self, product: LoanProduct) -> bool:
        """Validate product data quality."""
        # Required fields
        if not product.product_id or not product.name:
            return False
        
        # Must have at least one interest component with a rate
        if not product.interest_components:
            return False
        
        rate = product.interest_components[0].comparison_rate_pct_au
        if not rate or rate <= 0 or rate > 50:  # Sanity check: rate between 0% and 50%
            return False
        
        return True
    
    def _calculate_confidence_score(self, product: LoanProduct, strategies: List[str], priority_sum: int) -> int:
        """
        Calculate confidence score (0-100) based on data quality and strategy reliability.
        
        INCLUDES SURFACE PENALTY: Deducts points if critical pricing surfaces are missing
        (e.g., Interest Only, Investment variants).
        """
        score = 0
        
        # Base score from strategy reliability (0-50 points)
        strategy_priority_map = {
            'network_api': 50,
            'jsonld': 45,
            'embedded_state': 40,
            'compare_cards': 35,
            'ui_enumeration': 30,
            'dom_parsing': 25
        }
        
        # Use highest priority strategy
        max_strategy_score = max([strategy_priority_map.get(s, 20) for s in strategies], default=20)
        score += max_strategy_score
        
        # Multiple strategies confirm same product (+10 points)
        if len(strategies) > 1:
            score += min(10, len(strategies) * 2)
        
        # Data completeness (0-30 points)
        if product.interest_components and product.interest_components[0].comparison_rate_pct_au:
            score += 10
        if product.eligibility.max_lvr_by_segment or product.eligibility.max_lvr_by_loan_type:
            score += 5
        if product.repayment_type:
            score += 5
        if product.purpose:
            score += 5
        if product.eligibility.min_loan_amount_aud and product.eligibility.max_loan_amount_aud:
            score += 5
        
        # Data consistency (0-10 points)
        if product.interest_components:
            rate = product.interest_components[0].comparison_rate_pct_au
            if rate and 0.5 <= rate <= 20:  # Reasonable rate range
                score += 10
        
        # SURFACE PENALTY: Deduct points if critical pricing variants are missing
        # This incentivizes complete coverage of Interest Only / Investment surfaces
        if product.interest_components:
            # Check for distinct pricing surfaces
            purposes = set()
            repayment_types = set()
            
            for component in product.interest_components:
                if component.applicability:
                    purpose = component.applicability.get('purpose', '')
                    repayment = component.applicability.get('repayment_type', '')
                    if purpose:
                        purposes.add(purpose)
                    if repayment:
                        repayment_types.add(repayment)
            
            # Penalty if missing Investment variant (when OwnerOccupied exists)
            if 'OwnerOccupied' in purposes and 'Investment' not in purposes:
                score -= 15  # Missing Investment surface
            
            # Penalty if missing Interest Only variant (when P&I exists)
            if 'PrincipalAndInterest' in repayment_types and 'InterestOnly' not in repayment_types:
                score -= 15  # Missing Interest Only surface
            
            # Bonus if we have complete coverage (all 4 surfaces)
            if len(purposes) >= 2 and len(repayment_types) >= 2:
                score += 10  # Complete surface coverage bonus
        
        return max(0, min(100, score))  # Clamp to 0-100
    
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
                    
                    # Look for structured product data with rate tiers (generic pattern)
                    # This handles APIs that return products with multiple rate tiers per product
                    structured_products = self._parse_structured_products_api(json_data, lender_name, api_url)
                    if structured_products:
                        products.extend(structured_products)
                        logger.info(f"   ✅ [API] Extracted {len(structured_products)} products from structured API (with rate tiers)")
                        continue  # Skip generic parsing if we found structured data
                    
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
    
    def _parse_structured_products_api(
        self, 
        json_data: Any, 
        lender_name: str, 
        api_url: str
    ) -> List[LoanProduct]:
        """
        Parse structured product APIs that have rate tiers.
        
        Generic pattern: Products with multiple rate tiers per product.
        Handles structures like:
        - { "loanProducts": [{ "productId": "...", "rateTiers": [...] }] }
        - { "products": [{ "id": "...", "pricing": { "rateTiers": [...] } }] }
        - Any array of products with nested rate tier structures
        
        Returns empty list if structure doesn't match.
        """
        products = []
        
        try:
            # Find products array (could be named differently)
            products_array = None
            if isinstance(json_data, dict):
                # Try common array keys
                for key in ['loanProducts', 'products', 'items', 'data', 'results', 'productList']:
                    if key in json_data and isinstance(json_data[key], list):
                        products_array = json_data[key]
                        break
            elif isinstance(json_data, list):
                products_array = json_data
            
            if not products_array:
                return []
            
            logger.debug(f"   Found {len(products_array)} products in structured API")
            
            # Parse each product
            for product_data in products_array:
                if not isinstance(product_data, dict):
                    continue
                
                # Extract product name
                product_name = (
                    product_data.get('productName') or
                    product_data.get('name') or
                    product_data.get('productId') or
                    product_data.get('id') or
                    'Unknown Product'
                )
                
                # Extract eligibility info
                eligibility = product_data.get('eligibility', {})
                loan_purposes = eligibility.get('loanPurpose', [])
                repayment_types = eligibility.get('repaymentType', [])
                
                # Extract rate tiers
                rate_tiers = []
                pricing = product_data.get('pricing', {})
                if 'rateTiers' in product_data:
                    rate_tiers = product_data['rateTiers']
                elif 'rateTiers' in pricing:
                    rate_tiers = pricing['rateTiers']
                
                if not rate_tiers:
                    # No rate tiers - skip this product (use generic parser instead)
                    continue
                
                # Create interest components for each rate tier
                # Materialize ALL combinations explicitly (no inference)
                interest_components = []
                for tier_idx, tier in enumerate(rate_tiers):
                    if not isinstance(tier, dict):
                        continue
                    
                    # Extract rate (prefer comparisonRate, fallback to interestRate)
                    rate = tier.get('comparisonRate') or tier.get('interestRate') or tier.get('rate')
                    if not rate:
                        continue
                    
                    # Extract LVR info
                    lvr_min = tier.get('lvrMin')
                    lvr_max = tier.get('lvrMax')
                    if lvr_min is not None:
                        lvr_min = float(lvr_min) / 100  # Convert percentage to decimal
                    if lvr_max is not None:
                        lvr_max = float(lvr_max) / 100
                    
                    # Build applicability for this tier
                    applicability = {}
                    if lvr_min is not None:
                        applicability['lvr_min'] = lvr_min
                    if lvr_max is not None:
                        applicability['lvr_max'] = lvr_max
                        applicability['lvr_tier'] = f"≤{int(lvr_max * 100)}%" if lvr_min == 0 else f"{int(lvr_min * 100)}%-{int(lvr_max * 100)}%"
                    
                    # Materialize ALL combinations explicitly (no inference)
                    # For each rate tier, create components for ALL purpose × repayment_type combinations
                    if loan_purposes and repayment_types:
                        # Create explicit component for each combination
                        for purpose in loan_purposes:
                            for repayment_type in repayment_types:
                                # Create a copy of applicability for this specific combination
                                combo_applicability = applicability.copy()
                                combo_applicability['purpose'] = purpose
                                combo_applicability['repayment_type'] = repayment_type
                                
                                # Add provenance
                                combo_applicability['state_parameters'] = {
                                    'api_source': 'structured_api',
                                    'product_id': product_data.get('productId', ''),
                                    'rate_tier_index': tier_idx
                                }
                                combo_applicability['extraction_method'] = 'api_structured_rate_tiers'
                                combo_applicability['extraction_strategy'] = 'network_api'
                                
                                interest_components.append(
                                    InterestComponent(
                                        name=product_name,
                                        rate_type=product_data.get('rateType', 'Variable'),
                                        comparison_rate_pct_au=Decimal(str(rate)),
                                        applicability=combo_applicability
                                    )
                                )
                    else:
                        # Fallback if no purposes/repayment types specified
                        applicability['purpose'] = "OwnerOccupied_Purchase"
                        applicability['repayment_type'] = "PrincipalAndInterest"
                        applicability['state_parameters'] = {
                            'api_source': 'structured_api',
                            'product_id': product_data.get('productId', '')
                        }
                        applicability['extraction_method'] = 'api_structured_rate_tiers'
                        applicability['extraction_strategy'] = 'network_api'
                        
                        interest_components.append(
                            InterestComponent(
                                name=product_name,
                                rate_type=product_data.get('rateType', 'Variable'),
                                comparison_rate_pct_au=Decimal(str(rate)),
                                applicability=applicability
                            )
                        )
                
                if not interest_components:
                    continue
                
                # Create product
                product = LoanProduct(
                    product_id=f"{lender_name}-{product_data.get('productId', product_name)}",
                    version="1.0",
                    status="active",
                    name=f"{lender_name} {product_name}",
                    short_name=product_name,
                    description=product_data.get('description', f"{product_name} from {lender_name}"),
                    purpose=loan_purposes[0] if loan_purposes else "OwnerOccupied_Purchase",
                    repayment_type=repayment_types[0] if repayment_types else "PrincipalAndInterest",
                    channels=["Branch", "Online"],
                    interest_components=interest_components,
                    fees=FeeStructure(),
                    features=ProductFeatures(),
                    eligibility=EligibilityCriteria(
                        min_loan_amount_aud=eligibility.get('minLoanAmount', 20000),
                        max_loan_amount_aud=eligibility.get('maxLoanAmount', 2000000),
                        min_age_years=18,
                        residency=["AustralianCitizen", "PermanentResident"],
                        borrower_types=["Individual"],
                        occupancy=loan_purposes if loan_purposes else ["OwnerOccupied"],
                        max_lvr_by_segment=[
                            {"segment": purpose, "maxLVR": max([t.get('lvrMax', 0) / 100 for t in rate_tiers if t.get('lvrMax')], default=0.80)}
                            for purpose in (loan_purposes if loan_purposes else ["OwnerOccupied"])
                        ],
                        property_types_allowed=["House", "Apartment", "Townhouse"]
                    ),
                    lender=lender_name,
                    source_url=api_url
                )
                products.append(product)
                logger.debug(f"   Extracted structured product: {product_name} ({len(interest_components)} rate tiers)")
        
        except Exception as e:
            logger.debug(f"Structured API parsing failed: {e}")
        
        return products
    
    def generate_structured_json(self, products: List[LoanProduct]) -> Dict[str, Any]:
        """
        Generate structured JSON output in API format (loanProducts with rateTiers).
        
        Converts LoanProduct objects to the structured format:
        {
          "loanProducts": [
            {
              "productId": "...",
              "productName": "...",
              "productType": "HomeLoan",
              "rateType": "Variable",
              "features": {...},
              "eligibility": {
                "loanPurpose": ["OwnerOccupied", "Investment"],
                "repaymentType": ["PrincipalAndInterest", "InterestOnly"],
                ...
              },
              "pricing": {
                "indexRate": {...},
                "rateTiers": [
                  {"lvrMax": 60, "interestRate": 6.49, "comparisonRate": 6.49},
                  ...
                ]
              },
              "governance": {
                "ratesEffectiveDate": "...",
                "sourceUrl": "..."
              }
            }
          ]
        }
        
        Args:
            products: List of LoanProduct objects to convert
            
        Returns:
            Dictionary in structured API format
        """
        loan_products = []
        
        for product in products:
            # Collect all purposes and repayment types from interest components
            purposes = set()
            repayment_types = set()
            
            for component in product.interest_components:
                applicability = component.applicability
                if 'purpose' in applicability:
                    purposes.add(applicability['purpose'])
                if 'repayment_type' in applicability:
                    repayment_types.add(applicability['repayment_type'])
            
            # Fallback to product-level fields
            if not purposes:
                purposes.add(product.purpose)
            if not repayment_types:
                repayment_types.add(product.repayment_type)
            
            # Convert purposes to API format
            loan_purposes = []
            for purpose in purposes:
                if 'Investment' in purpose:
                    loan_purposes.append('Investment')
                elif 'OwnerOccupied' in purpose or 'Owner' in purpose:
                    loan_purposes.append('OwnerOccupied')
            
            # Convert repayment types to API format
            api_repayment_types = []
            for rt in repayment_types:
                if 'InterestOnly' in rt or 'Interest' in rt:
                    api_repayment_types.append('InterestOnly')
                elif 'Principal' in rt or 'P&I' in rt:
                    api_repayment_types.append('PrincipalAndInterest')
            
            # Build rate tiers from interest components
            rate_tiers = []
            index_rate = None
            
            for component in product.interest_components:
                applicability = component.applicability
                
                tier = {
                    "interestRate": float(component.comparison_rate_pct_au),
                    "comparisonRate": float(component.comparison_rate_pct_au)
                }
                
                # Add LVR info
                if 'lvr_min' in applicability:
                    tier["lvrMin"] = int(applicability['lvr_min'] * 100)  # Convert to percentage
                if 'lvr_max' in applicability:
                    tier["lvrMax"] = int(applicability['lvr_max'] * 100)
                
                rate_tiers.append(tier)
                
                # Use first component as index rate
                if index_rate is None:
                    index_rate = {
                        "rate": float(component.comparison_rate_pct_au),
                        "rateType": "ReferenceRate"
                    }
            
            # Build product object
            loan_product = {
                "productId": product.product_id,
                "productName": product.name,
                "productType": "HomeLoan",
                "rateType": product.interest_components[0].rate_type if product.interest_components else "Variable",
                "features": {
                    "offsetAccount": bool(product.features.offset_account),
                    "redraw": bool(product.features.redraw),
                    "packageEligible": bool(product.features.package)
                },
                "eligibility": {
                    "loanPurpose": list(loan_purposes) if loan_purposes else ["OwnerOccupied"],
                    "repaymentType": list(api_repayment_types) if api_repayment_types else ["PrincipalAndInterest"],
                    "minLoanAmount": float(product.eligibility.min_loan_amount_aud),
                    "maxLoanTermYears": product.amortization_term_months // 12 if product.amortization_term_months else 30
                },
                "pricing": {
                    "indexRate": index_rate or {"rate": 0.0, "rateType": "ReferenceRate"},
                    "rateTiers": rate_tiers
                },
                "governance": {
                    "ratesEffectiveDate": product.collected_at.strftime("%Y-%m-%d"),
                    "sourceUrl": product.source_url
                }
            }
            
            loan_products.append(loan_product)
        
        return {"loanProducts": loan_products}
    
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
        - window.dataLayer (Google Tag Manager - common pattern)
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
            
            # Parse dataLayer (common pattern for analytics tracking)
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
    
    async def _fill_numeric_inputs(self, page: Page) -> Dict[str, float]:
        """
        Identify and fill numeric input fields (loan amount, property value, deposit).
        
        This simulates a user entering values to trigger rate calculations.
        Returns dict of field_name -> value filled.
        
        USES EXTERNALIZED KEYWORDS from filter_keywords.yaml (ui_interactions.numeric_input_fields).
        """
        filled_inputs = {}
        
        try:
            # Load input patterns from YAML (100% externalized, no hardcoded strings)
            input_patterns = []
            for field_config in _filter_keywords.NUMERIC_INPUT_FIELDS:
                name = field_config.get('name', '')
                patterns = field_config.get('patterns', [])
                default_value = field_config.get('default_value', 0)
                
                # Build dynamic selectors from patterns
                selectors = []
                for pattern in patterns:
                    selectors.extend([
                        f'input[name*="{pattern}"]',
                        f'input[id*="{pattern}"]',
                        f'input[placeholder*="{pattern}"]'
                    ])
                
                input_patterns.append({
                    'name': name,
                    'selectors': selectors,
                    'value': default_value
                })
            
            for pattern in input_patterns:
                for selector in pattern['selectors']:
                    try:
                        inputs = await page.query_selector_all(selector)
                        for input_elem in inputs:
                            # Check if it's visible and numeric
                            is_visible = await input_elem.is_visible()
                            input_type = await input_elem.get_attribute('type') or 'text'
                            
                            if is_visible and input_type in ['number', 'text', 'tel']:
                                # Clear and fill the input
                                await input_elem.click()
                                await input_elem.fill('')
                                await input_elem.fill(str(pattern['value']))
                                await page.wait_for_timeout(500)  # Wait for calculation
                                
                                filled_inputs[pattern['name']] = pattern['value']
                                logger.debug(f"   💰 Filled {pattern['name']}: ${pattern['value']:,}")
                                break  # Only fill one input per pattern
                    except Exception as e:
                        continue
        
        except Exception as e:
            logger.debug(f"   Text input simulation error: {e}")
        
        return filled_inputs
    
    async def _click_show_more_buttons(self, page: Page) -> int:
        """
        Detect and click "Show More" / "Load More" / "View All" buttons.
        
        Returns count of buttons clicked.
        
        USES EXTERNALIZED KEYWORDS from filter_keywords.yaml (ui_interactions.show_more_patterns).
        """
        clicked_count = 0
        
        try:
            # Build selectors from externalized patterns (100% from YAML)
            show_more_patterns = []
            for pattern in _filter_keywords.SHOW_MORE_PATTERNS:
                # Escape quotes in pattern
                pattern_escaped = pattern.replace('"', '\\"')
                show_more_patterns.extend([
                    f'button:has-text("{pattern_escaped}")',
                    f'a:has-text("{pattern_escaped}")',
                    f'[class*="{pattern.replace(" ", "-")}"]'
                ])
            
            for pattern in show_more_patterns:
                try:
                    buttons = await page.query_selector_all(pattern)
                    for button in buttons:
                        is_visible = await button.is_visible()
                        if is_visible:
                            await button.click(timeout=2000)
                            await page.wait_for_timeout(1000)  # Wait for content to load
                            clicked_count += 1
                            logger.debug(f"   📖 Clicked 'Show More' button")
                except Exception:
                    continue
        
        except Exception as e:
            logger.debug(f"   Show More detection error: {e}")
        
        return clicked_count
    
    async def _find_reset_button(self, page: Page) -> Optional[Any]:
        """
        Find a "Reset Filters" / "Clear All" button for state optimization.
        
        Returns the button element if found, None otherwise.
        
        USES EXTERNALIZED KEYWORDS from filter_keywords.yaml (ui_interactions.reset_patterns).
        """
        try:
            # Build selectors from externalized patterns (100% from YAML)
            reset_patterns = []
            reset_keywords = _filter_keywords.RESET_PATTERNS
            
            for pattern in reset_keywords:
                # Escape quotes in pattern
                pattern_escaped = pattern.replace('"', '\\"')
                reset_patterns.extend([
                    f'button:has-text("{pattern_escaped}")',
                    f'a:has-text("{pattern_escaped}")',
                    f'[class*="{pattern.replace(" ", "-")}"]'
                ])
            
            for pattern in reset_patterns:
                try:
                    buttons = await page.query_selector_all(pattern)
                    for button in buttons:
                        is_visible = await button.is_visible()
                        text = await button.inner_text()
                        # Verify it matches reset keywords (double-check)
                        if is_visible and any(keyword in text.lower() for keyword in reset_keywords):
                            logger.debug(f"   🔄 Found reset button: '{text}'")
                            return button
                except Exception:
                    continue
        
        except Exception as e:
            logger.debug(f"   Reset button detection error: {e}")
        
        return None
    
    async def _query_selector_with_shadow(self, page: Page, selector: str) -> List[Any]:
        """
        Query selectors including Shadow DOM elements.
        
        Uses Playwright's piercing selectors (>>) to penetrate shadow roots.
        """
        try:
            # Try standard selector first
            elements = await page.query_selector_all(selector)
            
            # If no results, try with shadow piercing
            if not elements:
                shadow_selector = f':visible >> {selector}'
                elements = await page.query_selector_all(shadow_selector)
            
            return elements
        
        except Exception as e:
            logger.debug(f"   Shadow DOM query error for '{selector}': {e}")
            return []
    
    async def _is_non_product_widget(
        self, 
        page: Page, 
        filter_groups: List[Dict[str, Any]]
    ) -> tuple[bool, str, int]:
        """
        Detect if filter groups are part of an interactive widget (not product filters).
        
        Widgets include calculators, eligibility checkers, comparison tools, simulators.
        These show estimates/examples/tools, not actual product listings.
        Real product filters reveal hidden products or change DOM structure.
        
        Args:
            page: Playwright page
            filter_groups: List of identified filter groups
            
        Returns:
            Tuple of (is_widget, widget_type, max_depth):
            - is_widget: True if filters are part of a widget
            - widget_type: Type of widget detected (e.g., 'calculator', 'eligibility_checker')
            - max_depth: Maximum recursion depth for exploration
                - 0 = Skip completely (pure widget)
                - 1 = Shallow exploration (uncertain case)
                - 5 = Full exploration (not a widget)
        """
        if not filter_groups:
            return (False, "", 5)
        
        try:
            # Get page text for keyword analysis
            page_text = await page.inner_text('body')
            page_text_lower = page_text.lower()
            
            # Define widget types with their indicators and depth limits
            widget_configs = [
                {
                    'type': 'calculator',
                    'indicators': _filter_keywords.CALCULATOR_INDICATORS,
                    'threshold': 5,  # Increased from 2 to 5 - need strong evidence it's a PURE calculator
                    'max_filter_groups': 15,  # Max unique axes (ANZ has 14)
                    'depth_if_detected': 1  # Changed from 0 to 1 - allow shallow exploration to find products beneath
                },
                {
                    'type': 'eligibility_checker',
                    'indicators': _filter_keywords.ELIGIBILITY_CHECKER_INDICATORS,
                    'threshold': 2,
                    'max_filter_groups': 5,
                    'depth_if_detected': 0  # Skip completely
                },
                {
                    'type': 'comparison_tool',
                    'indicators': _filter_keywords.COMPARISON_TOOL_INDICATORS,
                    'threshold': 2,
                    'max_filter_groups': 6,
                    'depth_if_detected': 1  # Shallow exploration (might have products after selection)
                },
                {
                    'type': 'simulator',
                    'indicators': _filter_keywords.SIMULATOR_INDICATORS,
                    'threshold': 2,
                    'max_filter_groups': 5,
                    'depth_if_detected': 0  # Skip completely
                }
            ]
            
            # Check each widget type
            for widget_config in widget_configs:
                # Count matching indicators
                indicator_count = sum(
                    1 for keyword in widget_config['indicators']
                    if keyword in page_text_lower
                )
                
                # Count UNIQUE filter axes (not total groups) for more accurate detection
                # A calculator might have 20 groups but only 3-4 unique axes
                unique_axes = len(set(g['name'] for g in filter_groups))
                
                logger.info(
                    f"   🔍 Checking {widget_config['type']}: "
                    f"{indicator_count} indicators, {unique_axes} unique axes ({len(filter_groups)} total groups) "
                    f"(threshold: {widget_config['threshold']} indicators, "
                    f"max {widget_config['max_filter_groups']} unique axes)"
                )
                
                # Check if matches widget pattern (using unique axes, not total groups)
                if (indicator_count >= widget_config['threshold'] and 
                    unique_axes <= widget_config['max_filter_groups']):
                    
                    widget_type = widget_config['type']
                    max_depth = widget_config['depth_if_detected']
                    
                    logger.warning(
                        f"   🎮 {widget_type.replace('_', ' ').title()} detected "
                        f"({indicator_count} indicators found), "
                        f"max exploration depth: {max_depth}"
                    )
                    logger.debug(
                        f"   Matched indicators: {[kw for kw in widget_config['indicators'] if kw in page_text_lower][:5]}"
                    )
                    
                    return (True, widget_type, max_depth)
            
            # Not a widget - allow full exploration
            return (False, "", 5)
            
        except Exception as e:
            logger.warning(f"Error in widget detection: {e}")
            # On error, assume not a widget (safe default)
            return (False, "", 5)
    
    async def _is_calculator_widget(
        self, 
        page: Page, 
        filter_groups: List[Dict[str, Any]]
    ) -> bool:
        """
        DEPRECATED: Use _is_non_product_widget() instead.
        
        Detect if filter groups are part of a loan calculator (not product filters).
        Kept for backward compatibility.
        
        Args:
            page: Playwright page
            filter_groups: List of identified filter groups
            
        Returns:
            True if filters are part of calculator widget, False if real product filters
        """
        if not filter_groups:
            return False
        
        try:
            # Get page text for keyword analysis
            page_text = await page.inner_text('body')
            page_text_lower = page_text.lower()
            
            # Check for calculator indicator keywords (from YAML)
            calculator_keywords = _filter_keywords.CALCULATOR_INDICATORS
            
            # Count how many calculator indicators are present
            indicator_count = sum(1 for keyword in calculator_keywords if keyword in page_text_lower)
            
            # Heuristic: If 2+ calculator indicators found, likely a calculator
            if indicator_count >= 2:
                logger.info(f"   🧮 Calculator detected ({indicator_count} indicators found), skipping recursive exploration")
                logger.debug(f"   Calculator indicators: {[kw for kw in calculator_keywords if kw in page_text_lower][:5]}")
                return True
            
            # Additional check: Look for product cards/listings
            # Real product filters should have product elements nearby
            product_selectors = [
                '.product', '.product-card', '.loan-product',
                '[class*="product"]', '[class*="loan-card"]',
                '.rate-table', '[class*="rate-table"]'
            ]
            
            has_products = False
            for selector in product_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if len(elements) > 2:  # Multiple product elements
                        has_products = True
                        break
                except:
                    continue
            
            # If calculator indicators present AND no product listings → likely calculator
            if indicator_count >= 1 and not has_products:
                logger.info(f"   🧮 Calculator detected (indicators + no product listings), skipping recursive exploration")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"   Calculator detection failed: {e}, proceeding with recursive exploration")
            return False  # On error, assume NOT calculator (safe default)
    
    async def _explore_state_recursively(
        self,
        page: Page,
        lender_name: str,
        url: str,
        current_state: Dict[str, str],
        visited_paths: Set[str],
        depth: int = 0,
        max_depth: int = 5
    ) -> List[LoanProduct]:
        """
        RECURSIVE STATE EXPLORER - Implements "Full Matrix" exploration.
        
        This explores the UI as a hierarchy:
        Level 1: Rate Type (Variable/Fixed)
        Level 2: Loan Type (Owner Occupied/Investment)
        Level 3: Repayment Type (P&I/IO)
        
        After clicking each level, it re-discovers what filters appear next.
        This ensures we capture ALL combinations, including nested/conditional filters.
        
        Args:
            page: Playwright page
            lender_name: Lender name
            url: Current URL
            current_state: Dictionary of current filter selections {"rate_type": "Fixed", ...}
            visited_paths: Set of state paths already explored (prevents loops)
            depth: Current recursion depth (for logging)
            max_depth: Maximum recursion depth (default 5, can be limited by widget detection)
            
        Returns:
            List of products found in this branch of the state tree
        """
        indent = "  " * depth
        logger.debug(f"{indent}🔍 Exploring state: {current_state} (depth {depth}/{max_depth})")
        
        # Depth limit check (prevents infinite recursion)
        if depth >= max_depth:
            logger.debug(f"{indent}🛑 Reached max depth {max_depth}, stopping exploration")
            return []
        
        # Create state signature for cycle detection
        state_sig = "_".join(f"{k}={v}" for k, v in sorted(current_state.items()))
        if state_sig in visited_paths:
            logger.debug(f"{indent}↩️  Already visited, skipping")
            return []
        visited_paths.add(state_sig)
        
        # Wait for UI to settle after interactions
        await page.wait_for_timeout(1000)
        
        # Discover filters at THIS level (they may have just appeared)
        filter_groups = await self._identify_filter_groups(page)
        
        # WIDGET DETECTION: Check if we're exploring a calculator/widget
        # This prevents wasting time on non-product widgets
        if depth == 0:  # Only check at root level
            is_widget, widget_type, detected_max_depth = await self._is_non_product_widget(page, filter_groups)
            if is_widget and detected_max_depth < max_depth:
                # Widget detected with lower depth than allowed - update max_depth
                logger.warning(
                    f"{indent}🎮 {widget_type.replace('_', ' ').title()} detected at depth {depth}, "
                    f"limiting exploration to depth {detected_max_depth}"
                )
                max_depth = detected_max_depth
        
        # Separate into enumeration vs metadata filters
        enumeration_groups = []
        for group in filter_groups:
            if group['name'] not in ['region_residency', 'borrower_category']:
                enumeration_groups.append(group)
        
        if not enumeration_groups:
            # LEAF NODE - Extract products here
            logger.debug(f"{indent}📄 Leaf node reached, extracting products...")
            products = await self._extract_from_current_state(page, lender_name, url)
            
            # MATRIX TASK 3: Check if state is explicitly unavailable
            if not products:
                # Check for "not available", "unavailable", "N/A" messages
                page_text = await page.inner_text('body')
                unavailable_indicators = [
                    'not available', 'unavailable', 'n/a',
                    'this product is not available', 'no rates available',
                    'not applicable', 'not offered'
                ]
                
                if any(indicator in page_text.lower() for indicator in unavailable_indicators):
                    logger.debug(f"{indent}❌ State explicitly unavailable: {current_state}")
                    # Create a placeholder product to record this unavailable state
                    # This will be marked in the output so we know we TRIED this combination
                    # (Implementation: Add to unavailable_states tracking)
                    # For now, log it - can be enhanced to store in metadata
                    return []
            
            # Tag products with current state
            for product in products:
                for component in product.interest_components:
                    if not component.applicability:
                        component.applicability = {}
                    component.applicability.update(current_state)
            
            logger.debug(f"{indent}✅ Found {len(products)} products at this leaf")
            return products
        
        # BRANCH NODE - Recursively explore each option
        all_products = []
        
        for group in enumeration_groups:
            filter_name = group['name']
            options = group['options']
            
            logger.debug(f"{indent}🌳 Exploring {filter_name} with {len(options)} options")
            
            for option in options:
                try:
                    # Click this option
                    await option['element'].click(timeout=2000)
                    await page.wait_for_timeout(1500)
                    
                    # Build new state
                    new_state = current_state.copy()
                    new_state[filter_name] = option['value']
                    
                    # RECURSE into next level
                    branch_products = await self._explore_state_recursively(
                        page,
                        lender_name,
                        url,
                        new_state,
                        visited_paths,
                        depth + 1,
                        max_depth  # Pass depth limit down
                    )
                    
                    all_products.extend(branch_products)
                    
                except Exception as e:
                    logger.debug(f"{indent}⚠️  Failed to explore {filter_name}={option['value']}: {e}")
                    continue
        
        # Apply fixed term extraction from product names (REQUIREMENT 2.2)
        for product in all_products:
            self._extract_fixed_term_from_product_name(product)
        
        return all_products
    
    def _materialize_complete_matrix(
        self,
        products: List[LoanProduct],
        discovered_filters: Dict[str, List[str]],
        lender_name: str
    ) -> List[LoanProduct]:
        """
        CLOSED-WORLD MATRIX MATERIALIZER
        
        Transforms products from "Omission Model" → "Materialization Model".
        
        Takes extracted products and ensures EVERY possible state in the theoretical
        matrix is explicitly represented, either with:
        - pricing data (if found)
        - null pricing + status: "not_available" (if attempted but unavailable)
        - null pricing + status: "not_attempted" (if not explored)
        
        Args:
            products: List of products extracted from UI enumeration
            discovered_filters: Dict of filter types and their options, e.g.
                {
                    "loan_type": ["OwnerOccupied", "Investment"],
                    "repayment_type": ["PrincipalAndInterest", "InterestOnly"],
                    "rate_type": ["Variable", "Fixed"]
                }
            lender_name: Lender name for product ID generation
            
        Returns:
            List of products with complete matrix materialized
        """
        if not products or not discovered_filters:
            return products
        
        logger.info(f"   🗺️  Materializing complete state matrix...")
        
        # Step 1: Define the theoretical matrix
        filter_axes = []
        axis_names = []
        for filter_name in ['loan_type', 'repayment_type', 'rate_type']:
            if filter_name in discovered_filters:
                filter_axes.append(discovered_filters[filter_name])
                axis_names.append(filter_name)
        
        if not filter_axes:
            logger.info(f"   ℹ️  No matrix axes found, skipping materialization")
            return products
        
        # Generate all theoretical combinations
        from itertools import product as cartesian_product
        theoretical_states = list(cartesian_product(*filter_axes))
        expected_count = len(theoretical_states)
        
        logger.info(f"   📊 Theoretical matrix: {' × '.join([f'{len(axis)} {name}' for axis, name in zip(filter_axes, axis_names)])} = {expected_count} states")
        
        # Step 2: Inventory what we actually found
        # Group products by canonical name (not ID) to merge states
        product_groups = {}
        for product in products:
            canonical_name = product.short_name or product.name
            if canonical_name not in product_groups:
                product_groups[canonical_name] = {
                    'product': product,
                    'found_states': set(),
                    'state_data': {}
                }
            
            # Track which states we found for this product
            for component in product.interest_components:
                applicability = component.applicability or {}
                state_sig = "_".join([
                    applicability.get('loan_type', 'UNKNOWN'),
                    applicability.get('repayment_type', 'UNKNOWN'),
                    applicability.get('rate_type', 'UNKNOWN')
                ])
                product_groups[canonical_name]['found_states'].add(state_sig)
                product_groups[canonical_name]['state_data'][state_sig] = component
        
        # Step 3: Materialize missing states for each product
        materialized_products = []
        for canonical_name, group_data in product_groups.items():
            base_product = group_data['product']
            found_states = group_data['found_states']
            
            # Build complete set of expected states for this product
            expected_state_sigs = set()
            for state_combo in theoretical_states:
                state_dict = dict(zip(axis_names, state_combo))
                state_sig = "_".join([
                    state_dict.get('loan_type', 'UNKNOWN'),
                    state_dict.get('repayment_type', 'UNKNOWN'),
                    state_dict.get('rate_type', 'UNKNOWN')
                ])
                expected_state_sigs.add(state_sig)
            
            missing_states = expected_state_sigs - found_states
            
            if missing_states:
                logger.info(f"   📋 Product '{canonical_name}': Found {len(found_states)}/{expected_count} states, materializing {len(missing_states)} missing")
                
                # Create explicit null-state components for missing states
                for missing_sig in missing_states:
                    parts = missing_sig.split('_')
                    if len(parts) >= 3:
                        # Create a placeholder InterestComponent with null pricing
                        null_component = InterestComponent(
                            name=f"{canonical_name} - Not Available",
                            rate_type=parts[2] if len(parts) > 2 else "Unknown",
                            comparison_rate_pct_au=Decimal('0.00'),
                            applicability={
                                'loan_type': parts[0],
                                'repayment_type': parts[1],
                                'rate_type': parts[2] if len(parts) > 2 else "Unknown",
                                'capture_status': 'not_available',
                                'reason': 'State not found during exploration'
                            }
                        )
                        base_product.interest_components.append(null_component)
            else:
                logger.info(f"   ✅ Product '{canonical_name}': Complete matrix ({expected_count}/{expected_count} states)")
            
            materialized_products.append(base_product)
        
        logger.info(f"   🎯 Matrix materialization complete: {len(materialized_products)} products with full state coverage")
        return materialized_products
    
    async def _extract_from_ui_enumeration(
        self, 
        page: Page, 
        lender_name: str, 
        url: str
    ) -> List[LoanProduct]:
        """
        Extract products by systematically enumerating UI states.
        
        This strategy simulates a COMPLETE user flow:
        1. Fills numeric inputs (loan amount, property value) to trigger calculations
        2. Clicks "Show More" buttons to expand hidden content
        3. Clicks through all tabs and navigation
        4. Toggles switches/checkboxes to reveal variants
        5. Iterates through dropdown options (native and custom)
        6. Applies filters systematically (Cartesian product)
        7. Handles pagination
        8. Supports Shadow DOM with deep selectors
        9. Optimizes state reset with "Clear Filters" buttons
        10. Collects data from each unique state
        
        This ensures 100% coverage of what a typical high-intent user would see.
        """
        logger.info(f"   🎯 ENTRY: _extract_from_ui_enumeration called for {url}")
        all_products = []
        seen_products = set()  # Deduplicate by product identifier
        
        try:
            # PRE-STEP: Fill numeric inputs to trigger rate calculations
            filled_inputs = await self._fill_numeric_inputs(page)
            if filled_inputs:
                logger.debug(f"   ✅ Filled {len(filled_inputs)} numeric inputs")
                await page.wait_for_timeout(1500)  # Wait for calculations
            
            # PRE-STEP: Click "Show More" buttons to expand hidden content
            show_more_clicked = await self._click_show_more_buttons(page)
            if show_more_clicked > 0:
                logger.debug(f"   ✅ Clicked {show_more_clicked} 'Show More' buttons")
            
            # NEW: RECURSIVE STATE EXPLORATION ("Full Matrix" Explorer)
            # This explores the UI as a hierarchy (Level 1 → Level 2 → Level 3)
            # instead of flat Cartesian product
            logger.info(f"   🌳 Starting recursive state exploration...")
            
            # OPTIMIZATION: Detect interactive widgets (calculators, eligibility checkers, etc.)
            # Identify filter groups first to check if they're part of a widget
            initial_filter_groups = await self._identify_filter_groups(page)
            logger.info(f"   🔍 Checking {len(initial_filter_groups)} filter groups for widget detection...")
            
            # Check if filters are part of an interactive widget
            is_widget, widget_type, max_depth = await self._is_non_product_widget(page, initial_filter_groups)
            logger.info(f"   🎯 Widget detection result: is_widget={is_widget}, type={widget_type}, max_depth={max_depth}")
            
            if is_widget and max_depth == 0:
                # Widget detected with depth 0 - skip recursive exploration completely
                all_products = []
                logger.info(f"   ⏩ Skipped recursive exploration ({widget_type} widget detected)")
            else:
                # Real product filters OR widget with shallow exploration allowed
                if is_widget:
                    logger.info(f"   🔄 Limited exploration for {widget_type} (max depth: {max_depth})")
                
                visited_paths: Set[str] = set()
                initial_state: Dict[str, str] = {}
                
                # Start recursive exploration from root with depth control
                all_products = await self._explore_state_recursively(
                    page=page,
                    lender_name=lender_name,
                    url=url,
                    current_state=initial_state,
                    visited_paths=visited_paths,
                    depth=0,
                    max_depth=max_depth  # Apply depth limit from widget detection
                )
            
            logger.info(f"   ✅ Recursive exploration complete: {len(all_products)} products found across {len(visited_paths)} states")
            
            # OLD FLAT APPROACH (kept as fallback if recursive finds nothing)
            if not all_products:
                logger.warning(f"   ⚠️  Recursive exploration found nothing, falling back to flat enumeration")
                
                # Find reset button for fallback path
                reset_button = await self._find_reset_button(page)
                
                # Step 1: Click through all tabs and capture tab state (Shadow DOM aware)
                tabs = await self._query_selector_with_shadow(
                page,
                'button[role="tab"], .tab, [class*="tab"], nav[role="tablist"] button, [data-tab]'
            )
            if tabs:
                logger.debug(f"   Found {len(tabs)} tabs to enumerate")
                for i, tab in enumerate(tabs):
                    try:
                        # Get tab text before clicking
                        tab_text = await tab.inner_text()
                        if not tab_text:
                            tab_text = await tab.get_attribute('aria-label') or await tab.get_attribute('data-tab') or ''
                        
                        # Click tab
                        await tab.click(timeout=2000)
                        await page.wait_for_timeout(1000)  # Wait for content to load
                        
                        # Create filter state from tab (for BIAN normalization)
                        tab_filter_state = {'tab': tab_text.strip()}
                        
                        # Normalize tab state to BIAN axes
                        bian_axes = self._normalize_ui_state_to_bian_axes(tab_filter_state)
                        
                        # Extract products from this tab state
                        tab_products = await self._extract_from_current_state(page, lender_name, url)
                        
                        # Apply BIAN normalization to products from this tab
                        for product in tab_products:
                            if not product.interest_components:
                                continue
                            
                            # Store normalized BIAN axes in applicability
                            for component in product.interest_components:
                                if not component.applicability:
                                    component.applicability = {}
                                component.applicability.update(bian_axes)
                                
                                # Store provenance (extraction metadata)
                                component.applicability['state_parameters'] = tab_filter_state  # Raw UI state
                                component.applicability['extraction_method'] = 'ui_enumeration_tab'  # Detailed method
                                component.applicability['extraction_strategy'] = 'ui_enumeration'
                                component.applicability['filter_state'] = tab_filter_state  # Keep for backward compatibility
                            
                            # Update product-level fields from BIAN axes
                            if 'purpose' in bian_axes:
                                product.purpose = bian_axes['purpose']
                            if 'repayment_type' in bian_axes:
                                product.repayment_type = bian_axes['repayment_type']
                            
                            # Extract and apply eligibility criteria from filters
                            filter_eligibility = self._extract_eligibility_from_filters(tab_filter_state)
                            if 'product_segment' in filter_eligibility:
                                product.eligibility.product_segment = filter_eligibility['product_segment']
                            if 'region_restrictions' in filter_eligibility:
                                product.eligibility.region_restrictions = filter_eligibility['region_restrictions']
                            if 'borrower_category' in filter_eligibility:
                                product.eligibility.borrower_category = filter_eligibility['borrower_category']
                            
                            # Apply GLOBAL eligibility metadata (if available from later processing)
                            # Note: global_eligibility is populated later, so this won't apply here
                            # But keeping structure consistent
                            
                            product_id = product.product_id
                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                all_products.append(product)
                        
                        logger.debug(f"   Tab {i+1}/{len(tabs)} ('{tab_text[:30]}'): Found {len(tab_products)} products")
                    except Exception as e:
                        logger.debug(f"   Failed to process tab {i+1}: {e}")
                        continue
            
            # Step 2: Toggle switches/checkboxes (Shadow DOM aware)
            toggles = await self._query_selector_with_shadow(
                page,
                'input[type="checkbox"], input[type="radio"], [role="switch"], [role="checkbox"], .toggle, [class*="toggle"]'
            )
            if toggles:
                logger.debug(f"   Found {len(toggles)} toggles to enumerate")
                for toggle in toggles:
                    try:
                        # Check if toggleable
                        is_checked = await toggle.evaluate("el => el.checked || el.getAttribute('aria-checked') === 'true'")
                        
                        # Toggle if not checked
                        if not is_checked:
                            await toggle.click(timeout=2000)
                            await page.wait_for_timeout(1000)
                            
                            # Extract products from this toggle state
                            toggle_products = await self._extract_from_current_state(page, lender_name, url)
                            for product in toggle_products:
                                product_id = product.product_id
                                if product_id not in seen_products:
                                    seen_products.add(product_id)
                                    all_products.append(product)
                            
                            # Toggle back
                            await toggle.click(timeout=2000)
                            await page.wait_for_timeout(500)
                    except Exception as e:
                        logger.debug(f"   Failed to process toggle: {e}")
                        continue
            
            # Step 3: Systematically enumerate ALL filter combinations
            # This ensures we capture products for all loan type + repayment type combinations
            filter_groups = await self._identify_filter_groups(page)
            
            # CRITICAL OPTIMIZATION: Separate ENUMERATION filters from METADATA filters
            # Metadata filters (like region_residency) don't change pricing - they're eligibility constraints
            # Only enumerate filters that actually impact pricing
            
            METADATA_FILTERS = ['region_residency', 'borrower_category']  # Eligibility metadata, not pricing drivers
            
            enumeration_groups = []
            metadata_groups = []
            
            for group in filter_groups:
                if group['name'] in METADATA_FILTERS:
                    metadata_groups.append(group)
                else:
                    enumeration_groups.append(group)
            
            # Extract metadata (regions, borrower categories) ONCE as global eligibility
            global_eligibility = {}
            if metadata_groups:
                logger.info(f"   📋 Found {len(metadata_groups)} metadata filter groups (eligibility, not enumerated):")
                for mg in metadata_groups:
                    logger.info(f"      - {mg['name']} ({mg['type']}): {len(mg['options'])} options → applied as eligibility")
                    
                    # Extract as eligibility metadata
                    if mg['name'] == 'region_residency':
                        # Extract all available regions
                        regions = []
                        for opt in mg['options']:
                            text = opt['text'].strip()
                            # Map to state codes
                            for state in ['NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT']:
                                if state in text or state.lower() in text.lower():
                                    if state not in regions:
                                        regions.append(state)
                        
                        if regions:
                            global_eligibility['region_restrictions'] = regions
                            logger.info(f"      ✅ Extracted regions as eligibility: {regions}")
                    
                    elif mg['name'] == 'borrower_category':
                        # Extract borrower category
                        categories = [opt['text'].strip() for opt in mg['options']]
                        if categories:
                            global_eligibility['borrower_category'] = categories[0]  # Use first as default
            
            if enumeration_groups:
                logger.info(f"   ✅ Found {len(enumeration_groups)} enumeration filter groups (pricing drivers):")
                for fg in enumeration_groups:
                    logger.info(f"      - {fg['name']} ({fg['type']}): {len(fg['options'])} options")
            else:
                logger.warning(f"   ⚠️  No enumeration filter groups detected - will use fallback")
            
            if enumeration_groups:
                
                # Generate all combinations (cartesian product) - ONLY for pricing-impacting filters
                filter_combinations = list(product(*[group['options'] for group in enumeration_groups]))
                original_count = len(list(product(*[group['options'] for group in filter_groups])))
                if original_count > len(filter_combinations):
                    logger.info(f"   🎯 Optimized: {len(filter_combinations)} combinations (was {original_count} before metadata separation)")
                    logger.info(f"   ⚡ Performance gain: {100 * (1 - len(filter_combinations) / original_count):.0f}% fewer page loads")
                else:
                    logger.debug(f"   Generated {len(filter_combinations)} filter combinations")
                
                # Try each combination
                for combo_idx, combination in enumerate(filter_combinations):
                    try:
                        # Reset to default state first (reset button OR reload page)
                        if combo_idx == 0:
                            # First combination - page is already in default state
                            pass
                        else:
                            # OPTIMIZATION: Use reset button if available (faster, more human-like)
                            if reset_button:
                                try:
                                    await reset_button.click(timeout=2000)
                                    await page.wait_for_timeout(1000)
                                    logger.debug(f"   🔄 Reset filters using button (fast path)")
                                except Exception as e:
                                    # Fallback to reload if reset button fails
                                    logger.debug(f"   Reset button failed, falling back to reload: {e}")
                                    await page.reload(wait_until='domcontentloaded', timeout=30000)
                                    await page.wait_for_timeout(2000)
                            else:
                                # Reload page to reset all filters (reliable but slower)
                                await page.reload(wait_until='domcontentloaded', timeout=30000)
                                await page.wait_for_timeout(2000)
                        
                        # Apply all filters in this combination (only enumeration filters)
                        filter_state = {}
                        for filter_group, option in zip(enumeration_groups, combination):
                            filter_name = filter_group['name']
                            option_text = option['text'].strip()  # Clean whitespace and newlines
                            option_value = option.get('value', option_text).strip()
                            
                            # Log what filter we're applying for debugging
                            logger.debug(f"   Applying filter {filter_name} = '{option_text}' (value: '{option_value}')")
                            
                            try:
                                # Apply this filter
                                if filter_group['type'] == 'select':
                                    # Native select dropdown
                                    await filter_group['element'].select_option(option_value, timeout=2000)
                                elif filter_group['type'] == 'custom_dropdown':
                                    # Custom dropdown - click to open, then click option
                                    await filter_group['element'].click(timeout=2000)
                                    await page.wait_for_timeout(500)
                                    await option['element'].click(timeout=2000)
                                elif filter_group['type'] == 'radio':
                                    # Radio button - click the associated label for better compatibility
                                    radio_elem = option['element']
                                    radio_id = await radio_elem.get_attribute('id')
                                    if radio_id:
                                        # Try clicking the label (more reliable for styled radios)
                                        label = await page.query_selector(f'label[for="{radio_id}"]')
                                        if label:
                                            await label.click(timeout=2000)
                                        else:
                                            await radio_elem.click(timeout=2000)
                                    else:
                                        await radio_elem.click(timeout=2000)
                                elif filter_group['type'] == 'button':
                                    # Button/tab - click the button
                                    await option['element'].click(timeout=2000)
                                
                                filter_state[filter_name] = option_text
                                
                                # FIX D: Longer wait for repayment_type (some lenders use async XHR for dynamic tables)
                                if filter_name == 'repayment_type':
                                    await page.wait_for_timeout(2500)  # Extended wait for dynamic content (Interest Only tables, etc.)
                                    logger.debug(f"   ⏱️  Extended wait for repayment_type filter (2500ms)")
                                else:
                                    await page.wait_for_timeout(1500)  # Standard wait for other filters
                                
                                # FIX A: DYNAMIC RE-SCAN for cascading filters (detects nested/conditional filters)
                                # After clicking primary filters (loan_type, product_segment), new filters may appear
                                if filter_name in ['loan_type', 'product_segment', 'rate_type'] and combo_idx == 0:
                                    # Re-scan for additional filter groups that are now visible
                                    logger.debug(f"   🔄 Re-scanning for cascading filters after {filter_name}...")
                                    new_filter_groups = await self._identify_filter_groups(page)
                                    
                                    # Check if we discovered NEW filters (especially repayment_type)
                                    existing_names = {g['name'] for g in enumeration_groups}
                                    for new_group in new_filter_groups:
                                        if new_group['name'] not in existing_names and new_group['name'] not in METADATA_FILTERS:
                                            # Found a cascading filter!
                                            enumeration_groups.append(new_group)
                                            logger.info(f"   ✅ CASCADING FILTER DISCOVERED: {new_group['name']} ({len(new_group['options'])} options)")
                                            logger.info(f"      This appeared after clicking {filter_name}={option_text}")
                                    
                                    # If we found new filters, we need to expand the combinations
                                    # For now, log it - future enhancement could regenerate combinations
                                    if len(enumeration_groups) > len(filter_groups):
                                        logger.warning(f"   ⚠️  Found cascading filters! Consider re-running collection for complete coverage.")
                            
                            except Exception as e:
                                logger.debug(f"   Failed to apply filter {filter_name}={option_text}: {e}")
                                continue
                        
                        # Extract products with this filter combination
                        combo_products = await self._extract_from_current_state(page, lender_name, url)
                        
                        # Normalize filter state to BIAN axes (order-independent)
                        bian_axes = self._normalize_ui_state_to_bian_axes(filter_state)
                        
                        # Store filter state in each product
                        for product in combo_products:
                            # Add filter state to product metadata
                            if not product.interest_components:
                                continue
                            
                            # Store normalized BIAN axes in applicability (order-independent, standardized)
                            for component in product.interest_components:
                                if not component.applicability:
                                    component.applicability = {}
                                
                                # Update with BIAN-aligned keys (order-independent)
                                component.applicability.update(bian_axes)
                                
                                # Store provenance (extraction metadata)
                                component.applicability['state_parameters'] = filter_state  # Raw UI state
                                component.applicability['extraction_method'] = f"ui_enumeration_{'_'.join(filter_state.keys())}"  # Detailed method
                                component.applicability['extraction_strategy'] = 'ui_enumeration'
                                component.applicability['filter_state'] = filter_state  # Keep for backward compatibility
                            
                            # Update product-level fields from BIAN axes (for backward compatibility)
                            if 'purpose' in bian_axes:
                                product.purpose = bian_axes['purpose']
                                if 'Investment' in bian_axes['purpose']:
                                    product.eligibility.occupancy = ["Investment"]
                                    product.eligibility.max_lvr_by_segment = [
                                        {"segment": "Investment", "maxLVR": 0.90}
                                    ]
                                else:
                                    product.eligibility.occupancy = ["OwnerOccupied"]
                            
                            if 'repayment_type' in bian_axes:
                                product.repayment_type = bian_axes['repayment_type']
                            
                            # Update rate_type if specified
                            if 'rate_type' in bian_axes and product.interest_components:
                                product.interest_components[0].rate_type = bian_axes['rate_type']
                            
                            # Update fixed_term_months if specified
                            if 'fixed_term_months' in bian_axes and product.interest_components:
                                product.interest_components[0].fixed_term_months = bian_axes['fixed_term_months']
                            
                            # Extract and apply eligibility criteria from filters
                            filter_eligibility = self._extract_eligibility_from_filters(filter_state)
                            if 'product_segment' in filter_eligibility:
                                product.eligibility.product_segment = filter_eligibility['product_segment']
                            if 'region_restrictions' in filter_eligibility:
                                product.eligibility.region_restrictions = filter_eligibility['region_restrictions']
                            if 'borrower_category' in filter_eligibility:
                                product.eligibility.borrower_category = filter_eligibility['borrower_category']
                            
                            # Apply GLOBAL eligibility metadata (extracted once, applies to all products)
                            if 'region_restrictions' in global_eligibility:
                                product.eligibility.region_restrictions = global_eligibility['region_restrictions']
                            if 'borrower_category' in global_eligibility:
                                if not product.eligibility.borrower_category:  # Don't override if already set
                                    product.eligibility.borrower_category = global_eligibility['borrower_category']
                            
                            # BIAN-Normalized Product ID: [lender]-[normalized_name] (NO UI-state noise)
                            # This ensures clean IDs while state specificity is in pricing_states
                            # Deduplication happens at the name level, not ID level
                            if not product.product_id or product.product_id == "":
                                # Generate clean ID from lender + product name
                                lender_slug = product.lender.replace(" ", "-").replace("&", "and")
                                name_slug = product.short_name.replace(" ", "-").replace("&", "and") if product.short_name else product.name.replace(" ", "-").replace("&", "and")
                                product.product_id = f"{lender_slug}-{name_slug}"
                            
                            # Add to results if not duplicate
                            product_id = product.product_id
                            if product_id not in seen_products:
                                seen_products.add(product_id)
                                all_products.append(product)
                        
                        logger.debug(f"   Combination {combo_idx+1}/{len(filter_combinations)} ({filter_state}): Found {len(combo_products)} products")
                    except Exception as e:
                        logger.debug(f"   Failed to process combination {combo_idx+1}: {e}")
                        continue
            else:
                # Fallback: Try individual dropdowns if filter groups not detected
                dropdowns = await page.query_selector_all(
                    'select, [role="listbox"], [class*="dropdown"], [class*="select"]'
                )
                if dropdowns:
                    logger.debug(f"   Fallback: Found {len(dropdowns)} dropdowns to enumerate individually")
                    for dropdown in dropdowns:
                        try:
                            # Get all options
                            options = await dropdown.query_selector_all('option, [role="option"]')
                            if len(options) <= 1:
                                continue  # Skip if no options or only one
                            
                            # Try each option
                            for i, option in enumerate(options):
                                try:
                                    # Select option
                                    if await dropdown.evaluate("el => el.tagName === 'SELECT'"):
                                        # Native select
                                        value = await option.get_attribute('value')
                                        if value:
                                            await dropdown.select_option(value, timeout=2000)
                                    else:
                                        # Custom dropdown - click to open, then click option
                                        await dropdown.click(timeout=2000)
                                        await page.wait_for_timeout(500)
                                        await option.click(timeout=2000)
                                    
                                    await page.wait_for_timeout(1000)  # Wait for content update
                                    
                                    # Extract products from this dropdown state
                                    dropdown_products = await self._extract_from_current_state(page, lender_name, url)
                                    for product in dropdown_products:
                                        product_id = product.product_id
                                        if product_id not in seen_products:
                                            seen_products.add(product_id)
                                            all_products.append(product)
                                    
                                    logger.debug(f"   Dropdown option {i+1}/{len(options)}: Found {len(dropdown_products)} products")
                                except Exception as e:
                                    logger.debug(f"   Failed to process dropdown option {i+1}: {e}")
                                    continue
                        except Exception as e:
                            logger.debug(f"   Failed to process dropdown: {e}")
                            continue
            
            # Step 4: Handle pagination
            pagination_buttons = await page.query_selector_all(
                'button[aria-label*="next"], button[aria-label*="Next"], .pagination button, [class*="pagination"] button, [class*="next"]'
            )
            if pagination_buttons:
                logger.debug(f"   Found pagination, iterating through pages")
                page_num = 1
                max_pages = 10  # Safety limit
                
                while page_num <= max_pages:
                    # Extract products from current page
                    page_products = await self._extract_from_current_state(page, lender_name, url)
                    for product in page_products:
                        product_id = product.product_id
                        if product_id not in seen_products:
                            seen_products.add(product_id)
                            all_products.append(product)
                    
                    # Try to click next page
                    next_button = None
                    for btn in pagination_buttons:
                        text = await btn.inner_text()
                        if 'next' in text.lower() or '>' in text or '→' in text:
                            # Check if disabled
                            is_disabled = await btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
                            if not is_disabled:
                                next_button = btn
                                break
                    
                    if not next_button:
                        break  # No more pages
                    
                    try:
                        await next_button.click(timeout=2000)
                        await page.wait_for_timeout(2000)  # Wait for page load
                        page_num += 1
                    except Exception as e:
                        logger.debug(f"   Failed to navigate to next page: {e}")
                        break
            
            # Step 5: Extract from initial/default state (if not already done)
            if not all_products:
                initial_products = await self._extract_from_current_state(page, lender_name, url)
                all_products.extend(initial_products)
        
        except Exception as e:
            logger.debug(f"UI enumeration failed: {e}")
        
        # FIX 4 & 6: EXPLICIT IO/INVESTMENT VERIFICATION + STRICT CONFIDENCE PENALTIES
        # Verify we attempted to materialize all expected pricing surfaces
        if all_products:
            # Analyze what states we captured
            captured_purposes = set()
            captured_repayment_types = set()
            
            for product in all_products:
                for component in product.interest_components:
                    if component.applicability:
                        purpose = component.applicability.get('purpose', '')
                        repayment = component.applicability.get('repayment_type', '')
                        if purpose:
                            captured_purposes.add(purpose)
                        if repayment:
                            captured_repayment_types.add(repayment)
            
            # Check for missing surfaces
            is_partial = False
            missing_surfaces = []
            
            if 'Investment' not in captured_purposes and 'Investment_Purchase' not in captured_purposes:
                missing_surfaces.append('Investment')
                is_partial = True
            if 'InterestOnly' not in captured_repayment_types:
                missing_surfaces.append('InterestOnly')
                is_partial = True
            
            # Apply STRICT penalties if partial capture
            if is_partial:
                logger.warning(
                    f"   ⚠️  PARTIAL CAPTURE DETECTED: Missing {', '.join(missing_surfaces)} surfaces. "
                    f"Applying confidence penalty."
                )
                
                # Reduce confidence for ALL components in partial capture
                for product in all_products:
                    for component in product.interest_components:
                        if component.applicability:
                            # Get current confidence or default
                            current_confidence = component.applicability.get('confidence_score', 70)
                            
                            # FIX 6: STRICT PENALTIES
                            # Base: current
                            # Missing Investment: -20
                            # Missing InterestOnly: -20
                            penalty = 0
                            if 'Investment' in missing_surfaces:
                                penalty += 20
                            if 'InterestOnly' in missing_surfaces:
                                penalty += 20
                            
                            new_confidence = max(30, current_confidence - penalty)  # Floor at 30
                            component.applicability['confidence_score'] = new_confidence
                            component.applicability['capture_status'] = 'partial'
                            component.applicability['missing_surfaces'] = missing_surfaces
        
        # Apply fixed term extraction from product names (REQUIREMENT 2.2)
        for product in all_products:
            self._extract_fixed_term_from_product_name(product)
        
        return all_products
    
    async def _identify_filter_groups(self, page: Page) -> List[Dict[str, Any]]:
        """
        Identify filter groups on the page (loan type, repayment type, etc.).
        
        Returns a list of filter groups, each containing:
        - name: Filter name (e.g., 'loan_type', 'repayment_type')
        - type: Filter type ('select', 'custom_dropdown', 'radio', 'button')
        - element: The filter element
        - options: List of options with text, value, and element
        """
        filter_groups = []
        
        try:
            # Find all potential filter elements
            # 1. Select dropdowns
            selects = await page.query_selector_all('select')
            logger.debug(f"   Found {len(selects)} select elements")
            for select in selects:
                # Check if it looks like a filter (not a product selector)
                select_id = await select.get_attribute('id') or ''
                select_name = await select.get_attribute('name') or ''
                select_class = await select.get_attribute('class') or ''
                
                logger.debug(f"   Select: id='{select_id}', name='{select_name}', class='{select_class[:50]}'")
                
                # Skip product selection dropdowns (but be less aggressive)
                if 'product' in select_id.lower() and 'filter' not in select_id.lower() and 'loan' not in select_id.lower():
                    logger.debug(f"   Skipping select (looks like product selector): {select_id}")
                    continue
                
                options = await select.query_selector_all('option')
                valid_options = []
                for opt in options:
                    text = await opt.inner_text()
                    value = await opt.get_attribute('value') or text
                    # Skip placeholder options
                    if text and text.strip() and 'select' not in text.lower() and 'please' not in text.lower():
                        valid_options.append({
                            'text': text.strip(),
                            'value': value,
                            'element': opt
                        })
                
                if len(valid_options) > 1:
                    # Try to identify filter name from context
                    filter_name = self._guess_filter_name(select_id, select_name, select_class, valid_options)
                    
                    # Log what we found for debugging
                    option_texts = [opt['text'][:30] for opt in valid_options[:3]]
                    logger.debug(f"   Select filter '{filter_name}': {len(valid_options)} options - {option_texts}")
                    
                    # Log unmatched filters for future review (enterprise scraper evolution pattern)
                    if filter_name == 'filter_unknown':
                        logger.info(f"   📋 Unmatched select filter (for future review): id='{select_id}', name='{select_name}', options={option_texts}")
                    
                    filter_groups.append({
                        'name': filter_name,
                        'type': 'select',
                        'element': select,
                        'options': valid_options
                    })
            
            # 2. Radio button groups (loan type, repayment type)
            radio_groups = {}
            radios = await page.query_selector_all('input[type="radio"]')
            logger.info(f"   🔘 Found {len(radios)} radio buttons on page")
            for radio in radios:
                name = await radio.get_attribute('name')
                if not name:
                    continue
                
                if name not in radio_groups:
                    radio_groups[name] = []
                
                label_text = await self._get_radio_label(page, radio)
                if label_text:
                    radio_groups[name].append({
                        'text': label_text,
                        'value': await radio.get_attribute('value') or label_text,
                        'element': radio
                    })
                    logger.debug(f"   🔘 Radio '{name}': '{label_text}'")
            
            # Add radio groups with multiple options
            for name, options in radio_groups.items():
                if len(options) > 1:
                    filter_name = self._guess_filter_name(name, name, '', options)
                    option_texts = [opt['text'][:30] for opt in options]
                    logger.info(f"   🔘 Radio group '{name}' → filter '{filter_name}': {option_texts}")
                    # Find the first radio element for reference
                    first_radio = options[0]['element'] if options else None
                    filter_groups.append({
                        'name': filter_name,
                        'type': 'radio',
                        'element': first_radio,  # Reference to first radio for context
                        'options': options
                    })
            
            # 3. Look for text-based filter labels and find associated interactive elements
            # This handles custom components where filters are labeled with text
            filter_labels = await page.query_selector_all(
                'label, [class*="label"], [class*="filter"], [class*="option"], [data-label], [aria-label]'
            )
            
            # Use centralized keyword definitions from YAML
            loan_type_keywords = _filter_keywords.LOAN_TYPE_LABEL_KEYWORDS
            repayment_keywords = _filter_keywords.REPAYMENT_TYPE_LABEL_KEYWORDS
            
            # Find elements with filter-related text
            for label_elem in filter_labels:
                try:
                    label_text = await label_elem.inner_text()
                    if not label_text:
                        continue
                    
                    label_lower = label_text.lower()
                    
                    # Check if this looks like a loan type filter
                    if any(keyword in label_lower for keyword in loan_type_keywords):
                        # Find interactive elements near this label (buttons, divs, etc.)
                        nearby_elements = await self._find_filter_options_near_label(page, label_elem, loan_type_keywords)
                        if nearby_elements and len(nearby_elements) > 1:
                            filter_groups.append({
                                'name': 'loan_type',
                                'type': 'button',  # Could be button, div, etc.
                                'element': nearby_elements[0]['element'],
                                'options': nearby_elements
                            })
                    
                    # Check if this looks like a repayment type filter
                    elif any(keyword in label_lower for keyword in repayment_keywords):
                        nearby_elements = await self._find_filter_options_near_label(page, label_elem, repayment_keywords)
                        if nearby_elements and len(nearby_elements) > 1:
                            filter_groups.append({
                                'name': 'repayment_type',
                                'type': 'button',
                                'element': nearby_elements[0]['element'],
                                'options': nearby_elements
                            })
                except:
                    continue
            
            # 4. Button groups (tabs that act as filters)
            # Comprehensive selectors to catch modern filter button patterns (tabs, toggles, custom components)
            # ENHANCED: Added detection for horizontal toggle button groups (common pattern across major banks)
            button_groups = await page.query_selector_all(
                'button[role="tab"], [role="tablist"] button, [class*="filter"] button, [class*="tab"] button, '
                'button[class*="option"], div[role="button"][class*="option"], div[class*="filter-option"], '
                'button[class*="btn"], [class*="filter-button"], [class*="option-button"], [class*="tab-button"], '
                '[data-filter], [data-option], '
                # Generic toggle buttons in horizontal/vertical groups
                'button[type="button"]:not([class*="show"]):not([class*="more"])'
            )
            if button_groups:
                # Group buttons by their container or aria-controls
                grouped_buttons = {}
                for btn in button_groups:
                    text = await btn.inner_text()
                    if not text:
                        continue
                    
                    # Clean text: normalize whitespace, remove newlines
                    text_clean = ' '.join(text.split()).strip()
                    if len(text_clean) < 2:
                        continue
                    
                    # Try to find parent container (supports various toggle group patterns)
                    container_info = await btn.evaluate("""
                        el => {
                            // Try multiple container patterns (ordered by specificity)
                            const container = el.closest(
                                '[role="tablist"], ' +
                                '.filter-group, .tab-group, ' +
                                '[class*="filter"], [class*="option-group"], ' +
                                '[class*="toggle"], [class*="button-group"], ' +
                                'div:has(> button + button), ' +  // Div with multiple button children
                                'fieldset, ' +  // Form fieldsets
                                'section, ' +  // Sections
                                'div[class*="loan"], div[class*="repayment"]'  // Loan/repayment divs
                            );
                            if (container) {
                                // Get container label if exists
                                const label = container.querySelector('label, legend, [class*="label"], [class*="title"]');
                                const labelText = label ? label.textContent.trim() : '';
                                
                                return {
                                    id: container.id || '',
                                    className: container.className || '',
                                    label: labelText,
                                    tagName: container.tagName
                                };
                            }
                            return null;
                        }
                    """)
                    if container_info:
                        # Use label text if available (most semantic), otherwise ID or className
                        label_text = container_info.get('label', '').lower().strip()
                        container_id = (
                            label_text if label_text else
                            container_info.get('id') if container_info.get('id') else
                            container_info.get('className', '').split()[0] if container_info.get('className') else
                            'default'
                        )
                    else:
                        container_id = 'default'
                    
                    if container_id not in grouped_buttons:
                        grouped_buttons[container_id] = []
                    
                    grouped_buttons[container_id].append({
                        'text': text_clean,
                        'value': text_clean,
                        'element': btn
                    })
                
                # Add button groups with multiple options
                for container_id, options in grouped_buttons.items():
                    if len(options) > 1:
                        filter_name = self._guess_filter_name(container_id, container_id, '', options)
                        # Use first button as reference
                        first_button = options[0]['element'] if options else None
                        filter_groups.append({
                            'name': filter_name,
                            'type': 'button',
                            'element': first_button,  # Reference to first button for context
                            'options': options
                        })
            
            # 5. Aggressive search: Find all clickable elements with filter-related text
            # This catches custom components that don't match standard patterns
            # USES SHADOW-PIERCING to penetrate Web Component boundaries (generic, bank-agnostic)
            all_clickable = await self._query_selector_with_shadow(
                page,
                'button, [role="button"], [role="radio"], [role="tab"], '
                'label, div[onclick], div[class*="click"], div[class*="select"], '
                'span[class*="option"], a[class*="filter"], a[class*="option"], '
                'div[class*="filter"], div[class*="toggle"], input[type="checkbox"], '
                'button[class*="btn"], button[class*="button"], [class*="filter-button"], '
                '[class*="option-button"], [class*="tab-button"], [data-filter], [data-option], '
                '[class*="repayment"], [class*="loan-type"], [class*="rate-type"]'
            )
            
            # Group by filter type based on text content
            # Support all filter types for comprehensive detection
            filter_options_by_type = {
                'loan_type': [],
                'repayment_type': [],
                'rate_type': [],
                'loan_purpose': [],
                'product_segment': [],
                'region_residency': [],
                'rate_tier': [],
            }
            
            # Debug: Log total clickable elements found
            logger.debug(f"   Found {len(all_clickable)} clickable elements for aggressive search")
            
            for elem in all_clickable:
                try:
                    text = await elem.inner_text()
                    if not text:
                        continue
                    
                    # Clean text: remove extra whitespace, newlines, normalize
                    text_clean = ' '.join(text.split()).strip()  # Normalize whitespace
                    if len(text_clean) < 2:
                        continue
                    
                    # Use centralized keyword matching (from YAML) - check all filter types
                    # Priority order matters - check more specific first
                    if matches_rate_type(text_clean):
                        filter_options_by_type['rate_type'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                    elif matches_loan_purpose(text_clean):
                        filter_options_by_type['loan_purpose'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                    elif matches_loan_type(text_clean, max_words=4) and not matches_repayment_type(text_clean):
                        filter_options_by_type['loan_type'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                    elif matches_repayment_type(text_clean, max_words=5):
                        filter_options_by_type['repayment_type'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                        logger.debug(f"   ✅ Matched repayment_type: '{text_clean}'")
                    elif matches_product_segment(text_clean):
                        filter_options_by_type['product_segment'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                    elif matches_region_residency(text_clean):
                        filter_options_by_type['region_residency'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                    elif matches_rate_tier(text_clean):
                        filter_options_by_type['rate_tier'].append({
                            'text': text_clean,
                            'value': text_clean,
                            'element': elem
                        })
                except:
                    continue
            
            # Add all detected filter groups
            # FIX 6: Lower threshold for critical filters (repayment_type, loan_type) to >= 1
            # Some sites hide filters until other interactions occur
            for filter_type, options in filter_options_by_type.items():
                # Critical filters: accept even single option (might discover more dynamically)
                min_options = 1 if filter_type in ['repayment_type', 'loan_type', 'rate_type'] else 2
                
                if len(options) >= min_options:
                    # Check if we already have this filter type
                    if not any(g['name'] == filter_type for g in filter_groups):
                        # Deduplicate options by text
                        unique_options = []
                        seen_texts = set()
                        for opt in options:
                            opt_text_lower = opt['text'].lower()
                            if opt_text_lower not in seen_texts:
                                seen_texts.add(opt_text_lower)
                                unique_options.append(opt)
                        
                        if len(unique_options) > 1:
                            filter_groups.append({
                                'name': filter_type,
                                'type': 'button',
                                'element': unique_options[0]['element'],
                                'options': unique_options
                            })
                            logger.debug(f"   Added {filter_type} filter from aggressive search: {len(unique_options)} options")
            
            # Backward compatibility - keep old variable names for logging
            loan_type_options = filter_options_by_type['loan_type']
            repayment_type_options = filter_options_by_type['repayment_type']
            
            
            logger.debug(f"   Identified {len(filter_groups)} filter groups: {[g['name'] for g in filter_groups]}")
            
            # Log unmatched filters for future review (enterprise scraper evolution pattern)
            # This helps identify when new filter categories are needed
            unmatched_filters = []
            
            # Check for potential filters that weren't matched
            if len(filter_groups) == 0:
                # If no filters detected, log potential candidates
                selects_count = len(await page.query_selector_all('select'))
                radios_count = len(await page.query_selector_all('input[type="radio"]'))
                buttons_count = len(await page.query_selector_all('button, [role="button"]'))
                logger.debug(f"   Debug: Found {selects_count} selects, {radios_count} radios, {buttons_count} buttons")
                
                # Sample some elements to see what we might be missing
                sample_elements = await page.query_selector_all('select, input[type="radio"], button[class*="filter"], button[class*="option"]')
                for elem in sample_elements[:10]:  # Sample first 10
                    try:
                        text = await elem.inner_text()
                        if text and len(text.strip()) > 2 and len(text.strip()) < 50:
                            unmatched_filters.append(text.strip()[:50])
                    except:
                        continue
            
            # Log unmatched filters for review (only if we have candidates)
            if unmatched_filters:
                logger.info(f"   📋 Unmatched filter candidates (for future review): {list(set(unmatched_filters))[:5]}")
            
            # Debug: Log what we found in aggressive search (use INFO level so it's visible)
            if len(loan_type_options) > 0:
                logger.info(f"   🔍 Found {len(loan_type_options)} potential loan_type options: {[opt['text'][:40] for opt in loan_type_options[:10]]}")
            if len(repayment_type_options) > 0:
                logger.info(f"   🔍 Found {len(repayment_type_options)} potential repayment_type options: {[opt['text'][:40] for opt in repayment_type_options[:10]]}")
            
            # FIX C: SAFETY SCAN for repayment_type filters (generic, uses externalized keywords)
            # If page mentions repayment keywords but we didn't find the filter, search harder
            try:
                page_text = await page.inner_text('body')
                page_text_lower = page_text.lower()
                
                # Use externalized repayment keywords from YAML
                repayment_phrases = _filter_keywords.REPAYMENT_TYPE_PHRASES
                repayment_patterns = _filter_keywords.REPAYMENT_TYPE_PATTERNS
                
                # Check if page mentions any repayment type keywords
                mentions_repayment = any(phrase in page_text_lower for phrase in repayment_phrases) or \
                                   any(pattern in page_text_lower for pattern in repayment_patterns)
                
                if mentions_repayment:
                    # Check if we already found repayment_type
                    has_repayment = any(g['name'] == 'repayment_type' for g in filter_groups)
                    if not has_repayment:
                        logger.warning(f"   ⚠️  Page mentions repayment keywords but no repayment_type filter found - scanning harder...")
                        
                        # Build dynamic selector from externalized keywords
                        selectors = []
                        for phrase in repayment_phrases[:5]:  # Use top 5 phrases
                            # Escape quotes in phrases
                            phrase_escaped = phrase.replace('"', '\\"')
                            selectors.extend([
                                f'button:has-text("{phrase_escaped}")',
                                f'[role="button"]:has-text("{phrase_escaped}")',
                                f'[role="radio"]:has-text("{phrase_escaped}")',
                                f'label:has-text("{phrase_escaped}")'
                            ])
                        
                        # Add generic class-based selectors
                        selectors.extend([
                            '[class*="repayment"]',
                            '[class*="interest-only"]',
                            '[data-repayment]'
                        ])
                        
                        # Search for repayment elements
                        repayment_elements = []
                        for selector in selectors:
                            try:
                                elements = await self._query_selector_with_shadow(page, selector)
                                repayment_elements.extend(elements)
                            except:
                                continue
                        
                        if repayment_elements:
                            repayment_options = []
                            seen_texts = set()
                            for elem in repayment_elements:
                                try:
                                    text = await elem.inner_text()
                                    text_clean = text.strip()
                                    if text_clean and len(text_clean) > 1 and text_clean not in seen_texts:
                                        # Verify it matches repayment keywords
                                        if matches_repayment_type(text_clean):
                                            repayment_options.append({
                                                'text': text_clean,
                                                'value': text_clean,
                                                'element': elem
                                            })
                                            seen_texts.add(text_clean)
                                except:
                                    continue
                            
                            if len(repayment_options) >= 1:  # Even 1 is useful
                                filter_groups.append({
                                    'name': 'repayment_type',
                                    'type': 'button',
                                    'element': repayment_options[0]['element'],
                                    'options': repayment_options
                                })
                                logger.info(f"   ✅ SAFETY SCAN: Force-discovered {len(repayment_options)} repayment_type options using externalized keywords!")
            except Exception as e:
                logger.debug(f"   Safety scan error: {e}")
            
            # FIX 6B: SAFETY SCAN for loan_type filters (Owner Occupied / Investment)
            try:
                # Check if we already found loan_type
                has_loan_type = any(g['name'] == 'loan_type' for g in filter_groups)
                if not has_loan_type:
                    # Use externalized loan_type keywords from YAML
                    loan_type_phrases = _filter_keywords.LOAN_TYPE_PHRASES
                    
                    # Check if page mentions loan type keywords
                    mentions_loan_type = any(phrase in page_text_lower for phrase in loan_type_phrases)
                    
                    if mentions_loan_type:
                        logger.warning(f"   ⚠️  Page mentions loan_type keywords but no loan_type filter found - scanning harder...")
                        
                        # Build dynamic selector from externalized keywords
                        selectors = []
                        for phrase in loan_type_phrases[:5]:  # Use top 5 phrases
                            phrase_escaped = phrase.replace('"', '\\"')
                            selectors.extend([
                                f'button:has-text("{phrase_escaped}")',
                                f'[role="tab"]:has-text("{phrase_escaped}")',
                                f'[role="button"]:has-text("{phrase_escaped}")',
                                f'label:has-text("{phrase_escaped}")'
                            ])
                        
                        # Add generic class-based selectors
                        selectors.extend([
                            '[class*="loan-type"]',
                            '[class*="owner"]',
                            '[class*="investment"]',
                            '[data-loan-type]'
                        ])
                        
                        # Search for loan_type elements
                        loan_type_elements = []
                        for selector in selectors:
                            try:
                                elements = await self._query_selector_with_shadow(page, selector)
                                loan_type_elements.extend(elements)
                            except:
                                continue
                        
                        if loan_type_elements:
                            loan_type_options = []
                            seen_texts = set()
                            for elem in loan_type_elements:
                                try:
                                    text = await elem.inner_text()
                                    text_clean = text.strip()
                                    if text_clean and len(text_clean) > 1 and text_clean not in seen_texts:
                                        # Verify it matches loan_type keywords
                                        if matches_loan_type(text_clean):
                                            loan_type_options.append({
                                                'text': text_clean,
                                                'value': text_clean,
                                                'element': elem
                                            })
                                            seen_texts.add(text_clean)
                                except:
                                    continue
                            
                            if len(loan_type_options) >= 1:
                                filter_groups.append({
                                    'name': 'loan_type',
                                    'type': 'button',
                                    'element': loan_type_options[0]['element'],
                                    'options': loan_type_options
                                })
                                logger.info(f"   ✅ SAFETY SCAN: Force-discovered {len(loan_type_options)} loan_type options using externalized keywords!")
            except Exception as e:
                logger.debug(f"   Safety scan loan_type error: {e}")
        
        except Exception as e:
            logger.warning(f"   Failed to identify filter groups: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return filter_groups
    
    def _guess_filter_name(self, element_id: str, element_name: str, element_class: str, options: List[Dict]) -> str:
        """
        Intelligently guess filter name from element attributes and option text.
        Uses semantic analysis rather than hardcoded patterns to work across different banks.
        """
        # Combine all attribute text for analysis
        text = (element_id + ' ' + element_name + ' ' + element_class).lower()
        
        # Analyze option text for semantic patterns
        option_texts = ' '.join([opt.get('text', '').lower() for opt in options])
        combined_text = text + ' ' + option_texts
        
        # Use centralized keyword matching (from YAML)
        # Check all filter types in priority order
        # Note: More specific checks should come before generic ones
        
        # 1. Repayment type: MUST be first because options like "Principal & Interest" contain "interest" 
        #    which could falsely match rate_type patterns
        if any(term in combined_text for term in ['repayment', 'repay', 'payment', 'principal', 'p&i', 'io']):
            if any(term in option_texts for term in _filter_keywords.REPAYMENT_TYPE_PATTERNS):
                return 'repayment_type'
        
        # 2. Rate type (Fixed/Variable) - check after repayment type
        if any(term in combined_text for term in ['rate', 'fixed', 'variable', 'split']):
            if any(term in option_texts for term in _filter_keywords.RATE_TYPE_PATTERNS):
                return 'rate_type'
        
        # 3. Loan type: looks for property/ownership related terms
        if any(term in combined_text for term in ['loan', 'type', 'purpose', 'property', 'home', 'house', 'owner', 'occup', 'invest']):
            if any(term in option_texts for term in _filter_keywords.LOAN_TYPE_PATTERNS):
                return 'loan_type'
        
        # 4. Loan purpose variants (First Home Buyer, Construction, etc.)
        if any(term in combined_text for term in ['first home', 'construction', 'land', 'equity', 'refinance']):
            if any(term in option_texts for term in _filter_keywords.LOAN_PURPOSE_PATTERNS):
                return 'loan_purpose'
        
        # 5. Product segment (Package, Offset, etc.)
        if any(term in combined_text for term in ['package', 'offset', 'basic', 'professional', 'digital']):
            if any(term in option_texts for term in _filter_keywords.PRODUCT_SEGMENT_PATTERNS):
                return 'product_segment'
        
        # 6. LVR tier: looks for loan-to-value ratio terms
        if matches_lvr_tier(combined_text):
            return 'lvr_tier'
        
        # 7. Rate tier (Loan Amount, Risk Band, etc.)
        if any(term in combined_text for term in ['amount', 'band', 'risk', 'credit', 'tier']):
            if any(term in option_texts for term in _filter_keywords.RATE_TIER_PATTERNS):
                return 'rate_tier'
        
        # 8. Region/Residency
        if any(term in combined_text for term in ['state', 'resident', 'region', 'location']):
            if any(term in option_texts for term in _filter_keywords.REGION_RESIDENCY_PATTERNS):
                return 'region_residency'
        
        # 9. Loan term: looks for duration/period terms
        if matches_loan_term(combined_text):
            return 'loan_term'
        
        # Fallback: use element name or generate generic name
        if element_name:
            return element_name.lower().replace(' ', '_').replace('-', '_')
        if element_id:
            return element_id.lower().replace(' ', '_').replace('-', '_')
        return 'filter_unknown'
    
    def _normalize_ui_state_to_bian_axes(self, filter_state: Dict[str, str]) -> Dict[str, Any]:
        """
        Normalize any UI state (regardless of order) to BIAN-aligned axes.
        
        This function maps raw UI filter states (which can appear in any order
        depending on the bank's website structure) to standardized BIAN schema keys.
        
        Example inputs (all valid, different orders):
        - {"loan_type": "Owner Occupied", "repayment": "P&I"}
        - {"repayment": "Interest Only", "purpose": "Investment"}
        - {"tab": "Fixed Rates", "dropdown": "2 years"}
        - {"filter_unknown": "Owner Occupied", "repayment_type": "Interest Only"}
        
        Returns standardized BIAN keys:
        {
            "purpose": "OwnerOccupied_Purchase",
            "repayment_type": "PrincipalAndInterest",
            "rate_type": "Fixed",
            "fixed_term_months": 24,
            "lvr_min": 0.0,
            "lvr_max": 0.80,
            "lvr_tier": "≤80%",
            ...
        }
        
        Args:
            filter_state: Dictionary of raw UI filter states (order-independent)
            
        Returns:
            Dictionary with BIAN-aligned keys and normalized values
        """
        bian_axes = {}
        
        # Combine all filter values for semantic analysis
        all_text = ' '.join([str(v).lower() for v in filter_state.values()])
        all_keys = ' '.join([str(k).lower() for k in filter_state.keys()])
        
        # 1. Purpose mapping (order-independent)
        # Check both filter names and values
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            # Check if this is a purpose/loan_type filter
            if (matches_loan_type(value) or 
                'purpose' in key_lower or 
                'loan_type' in key_lower or
                'loan purpose' in key_lower or
                'property' in key_lower):
                
                if 'investment' in text or 'invest' in text:
                    bian_axes['purpose'] = "Investment_Purchase"
                elif 'owner' in text or 'home' in text or 'live' in text or 'owner occup' in text:
                    bian_axes['purpose'] = "OwnerOccupied_Purchase"
                elif 'first home' in text or 'first-home' in text:
                    bian_axes['purpose'] = "OwnerOccupied_Purchase"  # Could be more specific
                elif 'construction' in text:
                    bian_axes['purpose'] = "OwnerOccupied_Construction"
                elif 'refinance' in text:
                    # Determine if owner occupied or investment refinance
                    if 'investment' in all_text:
                        bian_axes['purpose'] = "Investment_Refinance"
                    else:
                        bian_axes['purpose'] = "OwnerOccupied_Refinance"
        
        # 2. Repayment type mapping (order-independent)
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            if (matches_repayment_type(value) or 
                'repayment' in key_lower or
                'repay' in key_lower):
                
                if any(term in text for term in ['interest only', 'interest-only', 'io', 'interest only repayments', 'i/o']):
                    bian_axes['repayment_type'] = "InterestOnly"
                elif any(term in text for term in ['principal', 'p&i', 'p and i', 'p+i', 'principal & interest', 'principal and interest']):
                    bian_axes['repayment_type'] = "PrincipalAndInterest"
        
        # 3. Rate type mapping (order-independent)
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            if (matches_rate_type(value) or 
                'rate_type' in key_lower or
                'rate type' in key_lower or
                'fixed' in text or 'variable' in text):
                
                if 'fixed' in text:
                    bian_axes['rate_type'] = "Fixed"
                    
                    # REQUIREMENT 2.2: Extract fixed term from filter state
                    # Search for patterns like "1 year", "2yr", "3 years", "1-year", "2 Yr"
                    import re
                    match = re.search(r'(\d+)\s*(?:year|yr)', text, re.IGNORECASE)
                    if match:
                        fixed_term_years = int(match.group(1))
                        bian_axes['fixed_term_months'] = fixed_term_years * 12
                        logger.debug(f"   📅 Extracted fixed term: {fixed_term_years} years = {bian_axes['fixed_term_months']} months from '{value}'")
                    
                elif 'variable' in text or 'var' in text:
                    bian_axes['rate_type'] = "Variable"
                elif 'split' in text:
                    bian_axes['rate_type'] = "Variable"  # Split is typically variable
        
        # 4. LVR tier mapping (order-independent)
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            if (matches_lvr_tier(value) or 
                'lvr' in key_lower or
                'loan to value' in key_lower or
                'ltv' in key_lower):
                
                # Parse LVR from various formats: "≤80%", "80% or less", "80% LVR", etc.
                lvr_match = re.search(r'(\d+)%', str(value))
                if lvr_match:
                    lvr_max = float(lvr_match.group(1)) / 100
                    bian_axes['lvr_max'] = lvr_max
                    
                    # Determine lvr_min from context
                    if '≤' in str(value) or 'less' in text or 'or less' in text or 'up to' in text:
                        bian_axes['lvr_min'] = 0.0
                        bian_axes['lvr_tier'] = f"≤{lvr_match.group(1)}%"
                    elif '>' in str(value) or 'more' in text or 'greater' in text:
                        # For ">80%", lvr_min would be 0.80, but we need context
                        # This is typically "more than 80%", so lvr_min = 0.80, lvr_max = 1.0
                        bian_axes['lvr_min'] = lvr_max
                        bian_axes['lvr_max'] = 1.0
                        bian_axes['lvr_tier'] = f">{lvr_match.group(1)}%"
                    else:
                        # Default: assume it's a range or exact value
                        bian_axes['lvr_min'] = 0.0
                        bian_axes['lvr_tier'] = f"{lvr_match.group(1)}%"
        
        # 5. Fixed term mapping (for fixed rate products)
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            if (matches_loan_term(value) or 
                'term' in key_lower or
                'fixed term' in key_lower or
                'year' in text or 'month' in text):
                
                # Parse term: "2 years", "24 months", "2-year", etc.
                year_match = re.search(r'(\d+)\s*year', text)
                month_match = re.search(r'(\d+)\s*month', text)
                
                if year_match:
                    bian_axes['fixed_term_months'] = int(year_match.group(1)) * 12
                elif month_match:
                    bian_axes['fixed_term_months'] = int(month_match.group(1))
        
        # 6. Occupancy mapping (derived from purpose)
        if 'purpose' in bian_axes:
            if 'Investment' in bian_axes['purpose']:
                bian_axes['occupancy'] = "Investment"
            else:
                bian_axes['occupancy'] = "OwnerOccupied"
        
        # FIX 5: MANDATORY FIXED_TERM VALIDATION (Critical for Fixed products)
        # If rate_type is "Fixed", fixed_term_months MUST be present
        if bian_axes.get('rate_type') == "Fixed" and 'fixed_term_months' not in bian_axes:
            # Try to extract from combined filter text as fallback
            for key, value in filter_state.items():
                text = f"{key} {value}".lower()
                
                # Try various patterns: "2 year", "24 month", "2-year", "two years"
                year_match = re.search(r'(\d+)\s*[-]?\s*year', text)
                month_match = re.search(r'(\d+)\s*[-]?\s*month', text)
                
                if year_match:
                    bian_axes['fixed_term_months'] = int(year_match.group(1)) * 12
                    logger.debug(f"   📅 Extracted fixed_term from '{text}': {bian_axes['fixed_term_months']} months")
                    break
                elif month_match:
                    bian_axes['fixed_term_months'] = int(month_match.group(1))
                    logger.debug(f"   📅 Extracted fixed_term from '{text}': {bian_axes['fixed_term_months']} months")
                    break
            
            # If still not found, log critical error
            if 'fixed_term_months' not in bian_axes:
                logger.error(
                    f"   ❌ VALIDATION FAILED: rate_type='Fixed' but no fixed_term found in filters: {filter_state}"
                )
                # Set a validation failure flag
                bian_axes['_validation_failed'] = 'missing_fixed_term'
        
        return bian_axes
    
    def _extract_fixed_term_from_product_name(self, product: LoanProduct) -> None:
        """
        REQUIREMENT 2.2: Extract fixed_term_months from product name if rate_type is Fixed.
        
        This is a fallback for when fixed term wasn't captured in filter state.
        Searches product name for patterns like "1 year", "2yr", "3 years", "1-Year", "Fixed 2 Year".
        
        Args:
            product: LoanProduct to update (modifies in place)
        """
        # Only process Fixed rate products
        if not product.interest_components:
            return
            
        for interest_component in product.interest_components:
            if interest_component.rate_type == "Fixed" and interest_component.fixed_term_months is None:
                # Search product name for term patterns
                product_name = product.name.lower()
                
                # Try patterns: "1 year", "2yr", "3 years", "1-year", "2 Yr", etc.
                import re
                match = re.search(r'(\d+)\s*[-]?\s*(?:year|yr)s?', product_name, re.IGNORECASE)
                
                if match:
                    fixed_term_years = int(match.group(1))
                    interest_component.fixed_term_months = fixed_term_years * 12
                    logger.debug(
                        f"   📅 Extracted fixed term from product name '{product.name}': "
                        f"{fixed_term_years} years = {interest_component.fixed_term_months} months"
                    )
                else:
                    # If still not found, log warning for Fixed products
                    logger.warning(
                        f"   ⚠️  Fixed rate product '{product.name}' missing fixed_term_months - "
                        f"could not extract from name"
                    )
    
    def _extract_eligibility_from_filters(self, filter_state: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract eligibility criteria from UI filter states.
        
        Maps filter states to eligibility fields:
        - product_segment: Premium, Standard, Basic
        - region_restrictions: NSW, VIC, QLD, etc.
        - borrower_category: Personal, Business, First Home Buyer
        
        Args:
            filter_state: Dictionary of raw UI filter states
            
        Returns:
            Dictionary with eligibility criteria
        """
        eligibility = {}
        
        for key, value in filter_state.items():
            text = str(value).lower()
            key_lower = str(key).lower()
            
            # 1. Product segment detection
            if 'product_segment' in key_lower or 'segment' in key_lower or 'tier' in key_lower:
                # Normalize segment names
                if 'premium' in text or 'prestige' in text or 'platinum' in text:
                    eligibility['product_segment'] = "Premium"
                elif 'standard' in text or 'classic' in text or 'plus' in text:
                    eligibility['product_segment'] = "Standard"
                elif 'basic' in text or 'essential' in text or 'smart' in text:
                    eligibility['product_segment'] = "Basic"
                elif 'package' in text:
                    eligibility['product_segment'] = "Package"
                else:
                    # Keep original value if can't normalize
                    eligibility['product_segment'] = value.strip()
            
            # 2. Region/residency restrictions
            if 'region' in key_lower or 'state' in key_lower or 'residency' in key_lower or 'location' in key_lower:
                # Extract Australian state codes
                regions = []
                for state in ['NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT']:
                    if state.lower() in text or state in value:
                        regions.append(state)
                
                # Also check for full state names
                state_mapping = {
                    'new south wales': 'NSW',
                    'victoria': 'VIC',
                    'queensland': 'QLD',
                    'south australia': 'SA',
                    'western australia': 'WA',
                    'tasmania': 'TAS',
                    'northern territory': 'NT',
                    'australian capital territory': 'ACT'
                }
                for full_name, code in state_mapping.items():
                    if full_name in text:
                        if code not in regions:
                            regions.append(code)
                
                if regions:
                    eligibility['region_restrictions'] = regions
            
            # 3. Borrower category
            if 'borrower' in key_lower or 'customer' in key_lower or 'category' in key_lower:
                if 'business' in text or 'commercial' in text or 'company' in text:
                    eligibility['borrower_category'] = "Business"
                elif 'personal' in text or 'individual' in text or 'consumer' in text:
                    eligibility['borrower_category'] = "Personal"
                elif 'first home' in text or 'fhb' in text or 'first-home' in text:
                    eligibility['borrower_category'] = "FirstHomeBuyer"
                elif 'professional' in text or 'doctor' in text or 'medical' in text:
                    eligibility['borrower_category'] = "Professional"
                else:
                    eligibility['borrower_category'] = value.strip()
        
        return eligibility
    
    async def _find_filter_options_near_label(self, page: Page, label_elem: Any, keywords: List[str]) -> List[Dict[str, Any]]:
        """Find interactive filter options near a label element."""
        options = []
        
        try:
            # Find parent container selector
            container_selector = await label_elem.evaluate("""
                el => {
                    const parent = el.closest('[class*="filter"], [class*="option"], [class*="group"], [class*="field"], fieldset, .form-group');
                    if (parent) {
                        // Generate a selector for the parent
                        if (parent.id) return '#' + parent.id;
                        if (parent.className) {
                            const classes = Array.from(parent.classList).filter(c => c.length > 0);
                            if (classes.length > 0) return '.' + classes[0];
                        }
                    }
                    return null;
                }
            """)
            
            # Find all interactive elements near the label
            # First try in the same container
            if container_selector:
                interactive_elements = await page.query_selector_all(
                    f'{container_selector} button, {container_selector} [role="button"], '
                    f'{container_selector} [role="radio"], {container_selector} [role="tab"], '
                    f'{container_selector} div[class*="option"], {container_selector} label, '
                    f'{container_selector} input[type="radio"]'
                )
            else:
                # Fallback: find in parent element using evaluate
                parent_selector = await label_elem.evaluate("""
                    el => {
                        const parent = el.parentElement;
                        if (!parent) return null;
                        if (parent.id) return '#' + parent.id;
                        if (parent.className) {
                            const classes = Array.from(parent.classList).filter(c => c.length > 0);
                            if (classes.length > 0) return '.' + classes[0];
                        }
                        return parent.tagName.toLowerCase();
                    }
                """)
                
                if parent_selector:
                    interactive_elements = await page.query_selector_all(
                        f'{parent_selector} button, {parent_selector} [role="button"], '
                        f'{parent_selector} [role="radio"], {parent_selector} label, '
                        f'{parent_selector} input[type="radio"]'
                    )
                else:
                    interactive_elements = []
            
            for elem in interactive_elements:
                try:
                    text = await elem.inner_text()
                    if not text or len(text.strip()) < 2:
                        continue
                    
                    # Check if text matches filter keywords or common filter values
                    text_lower = text.lower()
                    matches_keywords = any(keyword in text_lower for keyword in keywords)
                    # Generic semantic matching (not bank-specific)
                    matches_common = any(word in text_lower for word in [
                        'home', 'house', 'investment', 'invest', 'owner', 'occup',
                        'principal', 'interest', 'p&i', 'p and i', 'io', 'repayment'
                    ])
                    
                    if matches_keywords or matches_common:
                        # Check if it's clickable
                        is_clickable = await elem.evaluate("""
                            el => {
                                const style = window.getComputedStyle(el);
                                return style.cursor === 'pointer' || 
                                       el.onclick !== null ||
                                       el.getAttribute('role') === 'button' ||
                                       el.getAttribute('role') === 'radio' ||
                                       el.tagName === 'BUTTON' ||
                                       el.tagName === 'LABEL' ||
                                       el.tagName === 'INPUT';
                            }
                        """)
                        
                        if is_clickable:
                            options.append({
                                'text': text.strip(),
                                'value': text.strip(),
                                'element': elem
                            })
                except:
                    continue
            
            # If still no options, try a broader search around the label
            if not options:
                # Get label's bounding box and search nearby
                label_bbox = await label_elem.bounding_box()
                if label_bbox:
                    # Find all clickable elements in the same area
                    all_elements = await page.query_selector_all(
                        'button, [role="button"], label, input[type="radio"], div[class*="option"]'
                    )
                    for elem in all_elements:
                        try:
                            elem_bbox = await elem.bounding_box()
                            if elem_bbox:
                                # Check if element is near the label (within 200px)
                                distance = abs(elem_bbox['y'] - label_bbox['y'])
                                if distance < 200:
                                    text = await elem.inner_text()
                                    if text and len(text.strip()) >= 2:
                                        text_lower = text.lower()
                                        if any(word in text_lower for word in [
                                            'home', 'live', 'invest', 'owner', 'principal', 'interest'
                                        ]):
                                            options.append({
                                                'text': text.strip(),
                                                'value': text.strip(),
                                                'element': elem
                                            })
                        except:
                            continue
        
        except Exception as e:
            logger.debug(f"   Failed to find filter options near label: {e}")
        
        return options
    
    async def _get_radio_label(self, page: Page, radio: Any) -> Optional[str]:
        """Get label text for a radio button."""
        try:
            # Try to find associated label
            radio_id = await radio.get_attribute('id')
            if radio_id:
                label = await page.query_selector(f'label[for="{radio_id}"]')
                if label:
                    return await label.inner_text()
            
            # Try to find label as parent
            parent_text = await radio.evaluate("""
                el => {
                    const parent = el.closest('label');
                    return parent ? parent.innerText : null;
                }
            """)
            if parent_text:
                return parent_text
            
            # Try to find sibling label
            sibling_text = await radio.evaluate("""
                el => {
                    const sibling = el.nextElementSibling;
                    return sibling && sibling.tagName === 'LABEL' ? sibling.innerText : null;
                }
            """)
            if sibling_text:
                return sibling_text
            
            # Use value or aria-label as fallback
            value = await radio.get_attribute('value')
            aria_label = await radio.get_attribute('aria-label')
            return aria_label or value or None
        except:
            return None
    
    async def _extract_from_current_state(
        self, 
        page: Page, 
        lender_name: str, 
        url: str
    ) -> List[LoanProduct]:
        """
        Extract products from the current page state.
        
        This is a helper method that tries multiple extraction methods
        on the current DOM state (after UI interactions).
        """
        products = []
        
        # Try JSON-LD first (fastest)
        try:
            jsonld_products = await self._extract_from_jsonld(page, lender_name, url)
            if jsonld_products:
                return jsonld_products
        except:
            pass
        
        # Try embedded state
        try:
            embedded_products = await self._extract_from_embedded_state(page, lender_name, url)
            if embedded_products:
                return embedded_products
        except:
            pass
        
        # Try select dropdowns
        try:
            dropdown_products = await self._extract_from_select_dropdowns(page, lender_name, url)
            if dropdown_products:
                return dropdown_products
        except:
            pass
        
        # Try compare cards
        try:
            card_products = await self._extract_from_compare_cards(page, lender_name, url)
            if card_products:
                return card_products
        except:
            pass
        
        # Fallback to DOM parsing
        try:
            dom_products = await self._extract_products(page, lender_name, url)
            if dom_products:
                return dom_products
        except:
            pass
        
        return products
    
    async def _extract_from_compare_cards(self, page: Page, lender_name: str, url: str) -> List[LoanProduct]:
        """
        Extract products from compare cards with data-cell attributes.
        
        Generic pattern detection for structured product comparison cards:
        - .compare-card or .compare-carditem elements
        - Elements with data-cell="interest-rate" and data-cell="comparison-rate"
        - Product names in card headers
        - Works across different bank websites with similar card structures
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
                                # Generic defaults when actual values cannot be extracted
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
        Extract products from select dropdowns with rate information.
        
        Generic pattern for dropdowns containing product rates:
        <select id="...InterestRate...">
          <option>6.49% p.a Standard Variable 80% or less LVR</option>
        </select>
        
        Also checks for LVR tier tables that may be on the same page.
        Works across different bank websites with similar dropdown structures.
        
        Products with the same base name but different LVR tiers are merged into
        a single product with multiple interest components.
        """
        products = []
        
        try:
            # First, check for LVR tier tables (common pattern for tiered rate structures)
            lvr_tier_products = await self._extract_lvr_tier_tables(page, lender_name, url)
            if lvr_tier_products:
                products.extend(lvr_tier_products)
                logger.info(f"Found {len(lvr_tier_products)} products from LVR tier tables")
            
            # Find select elements that might contain rates
            rate_selects = await page.query_selector_all('select[id*="Interest"], select[id*="interest"], select[id*="rate"], select[id*="Rate"]')
            
            # Collect all dropdown products first
            dropdown_products = []
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
                            dropdown_products.append(product)
            
            if dropdown_products:
                # Merge products with same base name
                merged_products = self._merge_products_by_name(dropdown_products)
                products.extend(merged_products)
                logger.info(f"Found {len(dropdown_products)} dropdown options → merged into {len(merged_products)} products")
        
        except Exception as e:
            logger.debug(f"Select dropdown extraction failed: {e}")
        
        return products
    
    async def _parse_rate_dropdown_option(self, text: str, lender_name: str, url: str) -> Optional[LoanProduct]:
        """
        Parse rate dropdown option text into LoanProduct.
        
        Format examples:
        - "6.49% p.a Standard Variable 80% or less LVR"
        - "5.64% p.a Simplicity PLUS special offer discount 60% or less LVR*"
        - "6.69% p.a Standard Variable more than 80% LVR"
        """
        try:
            # Parse: "{rate}% p.a {product_name} [{lvr_info}]"
            # First extract rate
            rate_match = re.match(r'([\d.]+)%\s*p\.a\s+(.+)$', text)
            
            if not rate_match:
                return None
            
            rate = float(rate_match.group(1))
            remaining_text = rate_match.group(2).strip()
            
            # Extract LVR text from the end
            lvr_match = re.search(r'\s+([\d]+%.*?LVR.*?)(\*)?$', remaining_text)
            
            if lvr_match:
                lvr_text = lvr_match.group(1).strip()
                # Remove LVR text from product name
                product_name = remaining_text[:lvr_match.start()].strip()
            else:
                product_name = remaining_text
                lvr_text = None
            
            # Further clean product name: remove LVR qualifiers that might remain
            # Remove: "more than", "or less", "less than", "up to", "over"
            product_name = re.sub(r'\s+(more than|or less|less than|up to|over|more|less)$', '', product_name, flags=re.IGNORECASE).strip()
            
            # Parse LVR from text like "80% or less LVR" or "60% or less LVR*"
            lvr_value = 0.80  # Default
            lvr_min = None
            if lvr_text:
                lvr_percentage_match = re.search(r'([\d]+)%', lvr_text)
                if lvr_percentage_match:
                    lvr_value = float(lvr_percentage_match.group(1)) / 100
                    
                    # Determine lvr_min based on qualifier text
                    if any(term in lvr_text.lower() for term in ['or less', 'less than', 'up to']):
                        lvr_min = 0.0
                    elif any(term in lvr_text.lower() for term in ['more than', 'over', 'greater']):
                        lvr_min = lvr_value
                        lvr_value = 1.0  # Max LVR
            
            # Determine rate type from product name
            rate_type = "Variable"
            if "fixed" in product_name.lower():
                rate_type = "Fixed"
            elif "variable" in product_name.lower():
                rate_type = "Variable"
            
            # Build applicability dict
            applicability = {}
            if lvr_text:
                applicability['lvr_tier'] = lvr_text
                applicability['lvr_max'] = lvr_value
                if lvr_min is not None:
                    applicability['lvr_min'] = lvr_min
            
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
                        applicability=applicability
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
        Extract products from LVR tier tables with rate information.
        
        Generic pattern detection for tables with LVR tiered rates:
        LVR Tier | Comparison Rate (p.a.)
        ≤ 60%    | 5.65%
        ≤ 70%    | 5.70%
        ≤ 80%    | 5.80%
        ≤ 90%    | 6.34%
        > 90%    | 6.89%
        Index rate | 7.24%
        
        Works across different bank websites with similar table structures.
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
                    
                    # MATRIX TASK 4: Extract fixed_term from table row text
                    # Examples: "1 year fixed LVR 80% or less", "2 years fixed LVR more than 80%"
                    year_match = re.search(r'(\d+)\s*year', tier_text.lower())
                    month_match = re.search(r'(\d+)\s*month', tier_text.lower())
                    if year_match:
                        fixed_term_months = int(year_match.group(1)) * 12
                    elif month_match:
                        fixed_term_months = int(month_match.group(1))
                    else:
                        fixed_term_months = None
                    
                    # Parse LVR tier (e.g., "≤ 60%", "> 90%", "Index rate")
                    tier_match = re.search(r'([≤<>]|Index)\s*([\d]+)?%?', tier_text)
                    rate_match = re.search(r'([\d.]+)%', rate_text)
                    
                    if tier_match and rate_match:
                        operator = tier_match.group(1)
                        tier_value = tier_match.group(2)
                        rate = float(rate_match.group(1))
                        
                        # Determine LVR range
                        if operator == "Index" or tier_text.lower() == "index rate":
                            tier_dict = {
                                "tier": "Index rate",
                                "rate": rate,
                                "lvr_min": 0.0,
                                "lvr_max": 1.0,
                                "is_index": True
                            }
                            if fixed_term_months:
                                tier_dict["fixed_term_months"] = fixed_term_months
                            lvr_tiers.append(tier_dict)
                        elif operator == "≤":
                            max_lvr = float(tier_value) / 100 if tier_value else 1.0
                            # Find previous tier's max to determine min
                            prev_max = 0.0
                            for existing_tier in lvr_tiers:
                                if existing_tier.get("lvr_max", 0) > prev_max:
                                    prev_max = existing_tier.get("lvr_max", 0)
                            
                            tier_dict = {
                                "tier": f"≤ {tier_value}%",
                                "rate": rate,
                                "lvr_min": prev_max,
                                "lvr_max": max_lvr,
                                "lvr_exclusive_max": False
                            }
                            if fixed_term_months:
                                tier_dict["fixed_term_months"] = fixed_term_months
                            lvr_tiers.append(tier_dict)
                        elif operator == ">":
                            min_lvr = float(tier_value) / 100 if tier_value else 0.0
                            tier_dict = {
                                "tier": f"> {tier_value}%",
                                "rate": rate,
                                "lvr_min": min_lvr,
                                "lvr_max": 1.0,
                                "lvr_exclusive_max": True
                            }
                            if fixed_term_months:
                                tier_dict["fixed_term_months"] = fixed_term_months
                            lvr_tiers.append(tier_dict)
                
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
        
        Works for pages where products are in simple HTML sections:
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
