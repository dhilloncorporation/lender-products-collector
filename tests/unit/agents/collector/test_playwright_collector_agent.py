"""Test cases for PlaywrightCollectorAgent."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from playwright.async_api import Page, Browser, BrowserContext
from decimal import Decimal

from src.agents.collector.playwright_collector import PlaywrightCollectorAgent
from src.models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria
from tests.utils.mock_data import get_mock_products


class TestPlaywrightCollectorAgent:
    """Test cases for PlaywrightCollectorAgent."""

    @pytest.fixture
    def mock_page(self):
        """Mock Playwright page."""
        page = Mock(spec=Page)
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.close = AsyncMock()
        page.query_selector_all = AsyncMock()
        page.evaluate = AsyncMock()
        page.content = AsyncMock()
        page.screenshot = AsyncMock()
        return page

    @pytest.fixture
    def mock_browser(self):
        """Mock Playwright browser."""
        browser = Mock(spec=Browser)
        browser.new_page = AsyncMock()
        browser.close = AsyncMock()
        return browser

    @pytest.fixture
    def mock_playwright(self):
        """Mock Playwright instance."""
        playwright = Mock()
        playwright.chromium.launch = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright

    @pytest.fixture
    def collector_agent(self):
        """Create PlaywrightCollectorAgent instance."""
        return PlaywrightCollectorAgent(headless=True, timeout=30000)

    @pytest.mark.asyncio
    async def test_init(self):
        """Test agent initialization."""
        agent = PlaywrightCollectorAgent(headless=False, timeout=15000)
        
        assert agent.headless is False
        assert agent.timeout == 15000
        assert agent.browser is None
        assert agent.collected_products == []

    @pytest.mark.asyncio
    async def test_context_manager_entry(self, collector_agent, mock_playwright, mock_browser):
        """Test async context manager entry."""
        with patch('playwright.async_api.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright
            mock_playwright.chromium.launch.return_value = mock_browser
            
            async with collector_agent as agent:
                assert agent.browser == mock_browser
                mock_playwright.chromium.launch.assert_called_once_with(headless=True)

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, collector_agent, mock_browser):
        """Test async context manager exit."""
        collector_agent.browser = mock_browser
        collector_agent.playwright = Mock()
        collector_agent.playwright.stop = AsyncMock()
        
        await collector_agent.__aexit__(None, None, None)
        
        mock_browser.close.assert_called_once()
        collector_agent.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_from_url_no_browser(self, collector_agent):
        """Test collect_from_url without initialized browser."""
        with pytest.raises(RuntimeError, match="Browser not initialized"):
            await collector_agent.collect_from_url("https://example.com", "Test Lender")

    @pytest.mark.asyncio
    async def test_collect_from_url_success(self, collector_agent, mock_browser, mock_page):
        """Test successful collection from URL."""
        collector_agent.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        # Mock successful extraction
        mock_products = get_mock_products()[:1]
        
        with patch.object(collector_agent, '_smart_extract_products', return_value=mock_products):
            products = await collector_agent.collect_from_url(
                "https://example.com", 
                "Test Lender"
            )
            
            assert len(products) == 1
            assert products[0].lender == "Test Lender"
            mock_page.goto.assert_called_once()
            mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_from_url_error(self, collector_agent, mock_browser, mock_page):
        """Test collection error handling."""
        collector_agent.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.side_effect = Exception("Network error")
        
        products = await collector_agent.collect_from_url(
            "https://example.com", 
            "Test Lender"
        )
        
        assert products == []
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_extract_products_network_introspection(self, collector_agent, mock_page):
        """Test network introspection strategy."""
        mock_page.lender_name = "Test Lender"
        mock_page.url = "https://example.com"
        
        # Mock captured APIs with product data
        captured_apis = [
            {
                'url': 'https://api.example.com/products',
                'status': 200,
                'response': Mock()
            }
        ]
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'products': [
                {
                    'name': 'Test Product',
                    'rate': '6.5',
                    'description': 'Test product description'
                }
            ]
        }
        captured_apis[0]['response'] = mock_response
        
        with patch.object(collector_agent, '_extract_from_captured_apis', return_value=get_mock_products()[:1]):
            products = await collector_agent._smart_extract_products(
                mock_page, "Test Lender", "https://example.com", None, captured_apis
            )
            
            assert len(products) == 1
            assert products[0].lender == "Test Lender"

    @pytest.mark.asyncio
    async def test_smart_extract_products_jsonld(self, collector_agent, mock_page):
        """Test JSON-LD extraction strategy."""
        mock_page.lender_name = "Test Lender"
        mock_page.url = "https://example.com"
        
        # Mock JSON-LD script
        mock_script = Mock()
        mock_script.inner_text.return_value = '''
        {
            "@type": "FinancialProduct",
            "name": "Test Loan Product",
            "offers": {"price": "6.5"}
        }
        '''
        mock_page.query_selector_all.return_value = [mock_script]
        
        with patch.object(collector_agent, '_extract_from_jsonld', return_value=get_mock_products()[:1]):
            products = await collector_agent._smart_extract_products(
                mock_page, "Test Lender", "https://example.com"
            )
            
            assert len(products) == 1

    @pytest.mark.asyncio
    async def test_smart_extract_products_embedded_state(self, collector_agent, mock_page):
        """Test embedded state extraction strategy."""
        mock_page.lender_name = "Test Lender"
        mock_page.url = "https://example.com"
        
        # Mock embedded state
        mock_page.evaluate.return_value = {
            'dataLayer': [
                {
                    'ecommerce': {
                        'items': [
                            {'name': 'Test Product', 'price': 6.5}
                        ]
                    }
                }
            ]
        }
        
        with patch.object(collector_agent, '_extract_from_embedded_state', return_value=get_mock_products()[:1]):
            products = await collector_agent._smart_extract_products(
                mock_page, "Test Lender", "https://example.com"
            )
            
            assert len(products) == 1

    @pytest.mark.asyncio
    async def test_smart_extract_products_select_dropdown(self, collector_agent, mock_page):
        """Test select dropdown extraction strategy."""
        mock_page.lender_name = "Test Lender"
        mock_page.url = "https://example.com"
        
        # Mock select dropdown
        mock_select = Mock()
        mock_option = Mock()
        mock_option.inner_text.return_value = "6.49% p.a Standard Variable 80% or less LVR"
        mock_select.query_selector_all.return_value = [mock_option]
        mock_page.query_selector_all.return_value = [mock_select]
        
        with patch.object(collector_agent, '_extract_from_select_dropdowns', return_value=get_mock_products()[:1]):
            products = await collector_agent._smart_extract_products(
                mock_page, "Test Lender", "https://example.com"
            )
            
            assert len(products) == 1

    @pytest.mark.asyncio
    async def test_smart_extract_products_dom_parsing_fallback(self, collector_agent, mock_page):
        """Test DOM parsing fallback strategy."""
        mock_page.lender_name = "Test Lender"
        mock_page.url = "https://example.com"
        
        # Mock DOM elements
        mock_heading = Mock()
        mock_heading.inner_text.return_value = "Test Loan Product"
        mock_heading.evaluate_handle.return_value = Mock()
        mock_page.query_selector_all.return_value = [mock_heading]
        
        with patch.object(collector_agent, '_extract_products', return_value=get_mock_products()[:1]):
            products = await collector_agent._smart_extract_products(
                mock_page, "Test Lender", "https://example.com"
            )
            
            assert len(products) == 1

    @pytest.mark.asyncio
    async def test_extract_from_captured_apis(self, collector_agent):
        """Test extraction from captured API responses."""
        captured_apis = [
            {
                'url': 'https://api.example.com/products',
                'status': 200,
                'response': Mock()
            }
        ]
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'products': [
                {
                    'name': 'Test Product',
                    'rate': '6.5',
                    'description': 'Test product description'
                }
            ]
        }
        captured_apis[0]['response'] = mock_response
        
        products = await collector_agent._extract_from_captured_apis(
            captured_apis, "Test Lender", "https://example.com"
        )
        
        assert len(products) == 1
        assert products[0].name == "Test Lender Test Product"
        assert products[0].interest_components[0].comparison_rate_pct_au == Decimal("6.5")

    @pytest.mark.asyncio
    async def test_extract_from_jsonld(self, collector_agent, mock_page):
        """Test JSON-LD extraction."""
        # Mock JSON-LD script
        mock_script = Mock()
        mock_script.inner_text.return_value = '''
        {
            "@type": "FinancialProduct",
            "name": "Test Loan Product",
            "description": "Test description",
            "offers": {"price": "6.5"}
        }
        '''
        mock_page.query_selector_all.return_value = [mock_script]
        
        products = await collector_agent._extract_from_jsonld(
            mock_page, "Test Lender", "https://example.com"
        )
        
        assert len(products) == 1
        assert products[0].name == "Test Lender Test Loan Product"
        assert products[0].interest_components[0].comparison_rate_pct_au == Decimal("6.5")

    @pytest.mark.asyncio
    async def test_extract_from_select_dropdowns(self, collector_agent, mock_page):
        """Test select dropdown extraction."""
        # Mock select dropdown
        mock_select = Mock()
        mock_option = Mock()
        mock_option.inner_text.return_value = "6.49% p.a Standard Variable 80% or less LVR"
        mock_select.query_selector_all.return_value = [mock_option]
        mock_page.query_selector_all.return_value = [mock_select]
        
        products = await collector_agent._extract_from_select_dropdowns(
            mock_page, "Test Lender", "https://example.com"
        )
        
        assert len(products) == 1
        assert products[0].name == "Test Lender Standard Variable"
        assert products[0].interest_components[0].comparison_rate_pct_au == Decimal("6.49")

    @pytest.mark.asyncio
    async def test_parse_rate_dropdown_option(self, collector_agent):
        """Test parsing rate dropdown option text."""
        text = "6.49% p.a Standard Variable 80% or less LVR"
        
        product = await collector_agent._parse_rate_dropdown_option(
            text, "Test Lender", "https://example.com"
        )
        
        assert product is not None
        assert product.name == "Test Lender Standard Variable"
        assert product.interest_components[0].comparison_rate_pct_au == Decimal("6.49")
        assert product.interest_components[0].rate_type == "Variable"
        assert product.eligibility.max_lvr_by_segment[0]["maxLVR"] == 0.8

    @pytest.mark.asyncio
    async def test_parse_rate_dropdown_option_invalid(self, collector_agent):
        """Test parsing invalid rate dropdown option text."""
        text = "Invalid text without rate"
        
        product = await collector_agent._parse_rate_dropdown_option(
            text, "Test Lender", "https://example.com"
        )
        
        assert product is None

    @pytest.mark.asyncio
    async def test_extract_products_dom_parsing(self, collector_agent, mock_page):
        """Test DOM parsing extraction."""
        # Mock heading element
        mock_heading = Mock()
        mock_heading.inner_text.return_value = "Test Loan Product"
        mock_heading.evaluate_handle.return_value = Mock()
        
        # Mock parent container
        mock_parent = Mock()
        mock_parent.inner_text.return_value = "Test Loan Product 6.5% p.a"
        mock_heading.evaluate_handle.return_value = mock_parent
        
        mock_page.query_selector_all.return_value = [mock_heading]
        
        products = await collector_agent._extract_products(
            mock_page, "Test Lender", "https://example.com"
        )
        
        assert len(products) == 1
        assert products[0].name == "Test Lender Test Loan Product"
        assert products[0].interest_components[0].comparison_rate_pct_au == Decimal("6.5")

    def test_looks_like_loan_product(self, collector_agent):
        """Test loan product name validation."""
        # Valid product names
        assert collector_agent._looks_like_loan_product("Standard Variable Home Loan")
        assert collector_agent._looks_like_loan_product("Fixed Rate Mortgage")
        assert collector_agent._looks_like_loan_product("Basic Home Loan")
        
        # Invalid product names
        assert not collector_agent._looks_like_loan_product("Contact Us")
        assert not collector_agent._looks_like_loan_product("Login")
        assert not collector_agent._looks_like_loan_product("Menu")
        assert not collector_agent._looks_like_loan_product("")
        assert not collector_agent._looks_like_loan_product("A")

    @pytest.mark.asyncio
    async def test_collect_products_method(self, collector_agent):
        """Test the collect_products method."""
        lender_config = {
            'abbreviation': 'ANZ',
            'collection_urls': ['https://example.com']
        }
        
        with patch.object(collector_agent, 'collect_from_url', return_value=get_mock_products()[:1]):
            result = await collector_agent.collect_products(lender_config)
            
            assert result['lender'] == 'ANZ'
            assert result['status'] == 'success'
            assert len(result['products']) == 1
            assert 'timestamp' in result

    @pytest.mark.asyncio
    async def test_collect_products_with_errors(self, collector_agent):
        """Test collect_products with errors."""
        lender_config = {
            'abbreviation': 'ANZ',
            'collection_urls': ['https://example.com']
        }
        
        with patch.object(collector_agent, 'collect_from_url', side_effect=Exception("Network error")):
            result = await collector_agent.collect_products(lender_config)
            
            assert result['lender'] == 'ANZ'
            assert result['status'] == 'partial'
            assert len(result['errors']) == 1
            assert 'Network error' in result['errors'][0]

