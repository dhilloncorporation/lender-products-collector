"""Integration tests for Google Custom Search API."""

import pytest
import asyncio
import os
from unittest.mock import patch, Mock
from src.agents.discovery.google_custom_search import GoogleCustomSearchAPI
from src.agents.discovery.web_search_discovery import WebSearchDiscovery
from src.configs.settings_manager import YamlSettingsManager


class TestGoogleCustomSearchIntegration:
    """Integration tests for Google Custom Search API."""
    
    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        return {
            'CUSTOM_SEARCH_API_KEY': 'test_api_key_12345',
            'CUSTOM_SEARCH_CX': 'test_search_engine_id:abc123'
        }
    
    @pytest.fixture
    def mock_settings_manager(self):
        """Mock settings manager with Google Custom Search config."""
        settings = Mock(spec=YamlSettingsManager)
        
        # Mock web search config
        web_search_config = Mock()
        web_search_config.google_custom_search = Mock()
        web_search_config.google_custom_search.enabled = True
        web_search_config.google_custom_search.name = "Google Custom Search API"
        web_search_config.google_custom_search.priority = 1
        web_search_config.google_custom_search.api_key_env = "CUSTOM_SEARCH_API_KEY"
        web_search_config.google_custom_search.search_engine_id_env = "CUSTOM_SEARCH_CX"
        web_search_config.google_custom_search.base_url = "https://www.googleapis.com/customsearch/v1"
        web_search_config.google_custom_search.daily_limit = 100
        web_search_config.google_custom_search.cost_per_1000 = 5.00
        web_search_config.google_custom_search.timeout_seconds = 30
        web_search_config.google_custom_search.search_delay_seconds = 1
        web_search_config.google_custom_search.between_queries_delay_seconds = 2
        web_search_config.google_custom_search.human_like_delays = False
        web_search_config.google_custom_search.random_jitter = False
        
        settings.get_web_search.return_value = web_search_config
        
        # Mock rate limits
        rate_limits = Mock()
        rate_limits.search_delay_seconds = 1
        rate_limits.search_between_queries_seconds = 2
        rate_limits.search_daily_limit = 100
        settings.get_rate_limits.return_value = rate_limits
        
        return settings
    
    @pytest.mark.asyncio
    async def test_google_custom_search_api_initialization(self, mock_env_vars, mock_settings_manager):
        """Test Google Custom Search API initialization."""
        with patch.dict(os.environ, mock_env_vars):
            api = GoogleCustomSearchAPI(mock_settings_manager)
            
            assert api.api_key == 'test_api_key_12345'
            assert api.search_engine_id == 'test_search_engine_id:abc123'
            assert api.base_url == "https://www.googleapis.com/customsearch/v1"
            assert api.daily_limit == 100
            assert api.cost_per_1000 == 5.00
    
    @pytest.mark.asyncio
    async def test_web_search_discovery_with_google_custom_search(self, mock_env_vars, mock_settings_manager):
        """Test WebSearchDiscovery integration with Google Custom Search API."""
        with patch.dict(os.environ, mock_env_vars):
            discovery = WebSearchDiscovery(mock_settings_manager)
            
            # Should have Google Custom Search API initialized
            assert discovery.google_custom_search is not None
            assert discovery.google_custom_search.api_key == 'test_api_key_12345'
            assert discovery.google_custom_search.search_engine_id == 'test_search_engine_id:abc123'
    
    @pytest.mark.asyncio
    async def test_discover_lender_pages_integration(self, mock_env_vars, mock_settings_manager):
        """Test full integration of lender page discovery."""
        mock_search_response = {
            "items": [
                {"title": "Home Loan Rates", "link": "https://commbank.com.au/personal/home-loans/interest-rates", "snippet": "Current home loan rates"},
                {"title": "Home Loan Products", "link": "https://commbank.com.au/personal/home-loans/our-home-loans", "snippet": "Our home loan products"},
                {"title": "Compare Home Loans", "link": "https://commbank.com.au/personal/home-loans/compare", "snippet": "Compare our home loans"}
            ],
            "searchInformation": {"totalResults": "3"}
        }
        
        with patch.dict(os.environ, mock_env_vars):
            with patch('httpx.AsyncClient') as mock_client:
                # Mock successful HTTP response
                mock_response = Mock()
                mock_response.json.return_value = mock_search_response
                mock_response.raise_for_status.return_value = None
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                discovery = WebSearchDiscovery(mock_settings_manager)
                result = await discovery.discover_lender_pages(
                    "Commonwealth Bank", "commbank.com.au"
                )
                
                # Should use Google Custom Search API
                assert discovery.google_custom_search is not None
                
                # Check result structure
                assert isinstance(result, dict)
                assert "interest_rates" in result
                assert "products" in result
                assert "comparison" in result
                assert "fees" in result
                
                # All categories should be lists
                for category, urls in result.items():
                    assert isinstance(urls, list)
    
    @pytest.mark.asyncio
    async def test_fallback_to_other_engines_when_google_fails(self, mock_env_vars, mock_settings_manager):
        """Test fallback to other engines when Google Custom Search fails."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('httpx.AsyncClient') as mock_client:
                # Mock HTTP error (e.g., quota exceeded)
                from httpx import HTTPStatusError
                mock_response = Mock()
                mock_response.status_code = 403
                mock_response.text = "Quota exceeded"
                mock_response.raise_for_status.side_effect = HTTPStatusError(
                    "403 Client Error", request=Mock(), response=mock_response
                )
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                discovery = WebSearchDiscovery(mock_settings_manager)
                
                # Should fall back to other engines
                with patch.object(discovery, '_search_with_fallback', return_value=[]) as mock_fallback:
                    result = await discovery.discover_lender_pages(
                        "Commonwealth Bank", "commbank.com.au"
                    )
                    
                    # Should have tried Google Custom Search first, then fallback
                    assert mock_fallback.called
    
    @pytest.mark.asyncio
    async def test_usage_tracking_integration(self, mock_env_vars, mock_settings_manager):
        """Test usage tracking across multiple searches."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {"items": [], "searchInformation": {"totalResults": "0"}}
                mock_response.raise_for_status.return_value = None
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                discovery = WebSearchDiscovery(mock_settings_manager)
                
                # Perform multiple searches
                await discovery.discover_lender_pages("CBA", "commbank.com.au")
                await discovery.discover_lender_pages("ANZ", "anz.com")
                
                # Check usage stats
                stats = discovery.google_custom_search.get_usage_stats()
                assert stats["queries_used"] > 0
                assert stats["queries_remaining"] < 100
                assert stats["estimated_cost"] > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_env_vars, mock_settings_manager):
        """Test error handling in integration scenarios."""
        with patch.dict(os.environ, mock_env_vars):
            discovery = WebSearchDiscovery(mock_settings_manager)
            
            # Test with invalid domain
            result = await discovery.discover_lender_pages("Test Bank", "invalid-domain")
            
            # Should return empty results but not crash
            assert isinstance(result, dict)
            assert "interest_rates" in result
            assert "products" in result
    
    @pytest.mark.asyncio
    async def test_environment_variable_validation(self):
        """Test validation of required environment variables."""
        # Test missing API key
        with patch.dict(os.environ, {'CUSTOM_SEARCH_CX': 'test_id'}, clear=True):
            with pytest.raises(ValueError, match="CUSTOM_SEARCH_API_KEY environment variable not set"):
                GoogleCustomSearchAPI(None)
        
        # Test missing search engine ID
        with patch.dict(os.environ, {'CUSTOM_SEARCH_API_KEY': 'test_key'}, clear=True):
            with pytest.raises(ValueError, match="CUSTOM_SEARCH_CX environment variable not set"):
                GoogleCustomSearchAPI(None)


class TestGoogleCustomSearchEndToEnd:
    """End-to-end tests for Google Custom Search API."""
    
    @pytest.mark.asyncio
    async def test_real_api_call_with_mock(self, mock_env_vars):
        """Test real API call structure with mocked response."""
        with patch.dict(os.environ, mock_env_vars):
            with patch('httpx.AsyncClient') as mock_client:
                # Mock a realistic Google Custom Search API response
                mock_response_data = {
                    "kind": "customsearch#search",
                    "url": {
                        "type": "application/json",
                        "template": "https://www.googleapis.com/customsearch/v1?q={searchTerms}&num={count?}&start={startIndex?}&lr={language?}&safe={safe?}&cx={cx?}&cref={cref?}&sort={sort?}&filter={filter?}&gl={gl?}&cr={cr?}&googlehost={googleHost?}&c2coff={c2coff?}&hq={hq?}&hl={hl?}&siteSearch={siteSearch?}&siteSearchFilter={siteSearchFilter?}&exactTerms={exactTerms?}&excludeTerms={excludeTerms?}&linkSite={linkSite?}&orTerms={orTerms?}&relatedSite={relatedSite?}&dateRestrict={dateRestrict?}&lowRange={lowRange?}&highRange={highRange?}&searchType={searchType?}&fileType={fileType?}&rights={rights?}&imgSize={imgSize?}&imgType={imgType?}&imgColorType={imgColorType?}&imgDominantColor={imgDominantColor?}&alt=json"
                    },
                    "queries": {
                        "request": [
                            {
                                "title": "Google Custom Search - site:commbank.com.au home loan rates",
                                "totalResults": "2",
                                "searchTerms": "site:commbank.com.au home loan rates",
                                "count": 10,
                                "startIndex": 1,
                                "inputEncoding": "utf8",
                                "outputEncoding": "utf8",
                                "safe": "off",
                                "cx": "test_search_engine_id:abc123",
                                "gl": "au",
                                "hl": "en"
                            }
                        ]
                    },
                    "context": {
                        "title": "Google Custom Search"
                    },
                    "searchInformation": {
                        "searchTime": 0.123456,
                        "formattedSearchTime": "0.12",
                        "totalResults": "2",
                        "formattedTotalResults": "2"
                    },
                    "items": [
                        {
                            "kind": "customsearch#result",
                            "title": "Home Loan Interest Rates | CommBank",
                            "htmlTitle": "Home Loan Interest Rates | <b>CommBank</b>",
                            "link": "https://www.commbank.com.au/personal/home-loans/interest-rates.html",
                            "displayLink": "www.commbank.com.au",
                            "snippet": "View our current home loan interest rates. Compare variable and fixed rates for owner occupier and investment home loans.",
                            "htmlSnippet": "View our current <b>home loan interest rates</b>. Compare variable and fixed rates for owner occupier and investment <b>home loans</b>.",
                            "formattedUrl": "commbank.com.au/personal/home-loans/interest-rates.html",
                            "pagemap": {
                                "metatags": [
                                    {
                                        "og:title": "Home Loan Interest Rates | CommBank",
                                        "og:description": "View our current home loan interest rates. Compare variable and fixed rates for owner occupier and investment home loans.",
                                        "og:url": "https://www.commbank.com.au/personal/home-loans/interest-rates.html"
                                    }
                                ]
                            }
                        },
                        {
                            "kind": "customsearch#result",
                            "title": "Home Loan Products | CommBank",
                            "htmlTitle": "Home Loan Products | <b>CommBank</b>",
                            "link": "https://www.commbank.com.au/personal/home-loans/our-home-loans.html",
                            "displayLink": "www.commbank.com.au",
                            "snippet": "Explore our range of home loan products. Find the right home loan for your needs with competitive rates and flexible features.",
                            "htmlSnippet": "Explore our range of <b>home loan products</b>. Find the right <b>home loan</b> for your needs with competitive rates and flexible features.",
                            "formattedUrl": "commbank.com.au/personal/home-loans/our-home-loans.html"
                        }
                    ]
                }
                
                mock_response = Mock()
                mock_response.json.return_value = mock_response_data
                mock_response.raise_for_status.return_value = None
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                api = GoogleCustomSearchAPI(None)
                result = await api.search("site:commbank.com.au home loan rates")
                
                # Verify the API call was made with correct parameters
                mock_client.return_value.__aenter__.return_value.get.assert_called_once()
                call_args = mock_client.return_value.__aenter__.return_value.get.call_args
                
                assert call_args[0][0] == "https://www.googleapis.com/customsearch/v1"
                assert call_args[1]["params"]["key"] == "test_api_key_12345"
                assert call_args[1]["params"]["cx"] == "test_search_engine_id:abc123"
                assert call_args[1]["params"]["q"] == "site:commbank.com.au home loan rates"
                assert call_args[1]["params"]["gl"] == "au"
                assert call_args[1]["params"]["hl"] == "en"
                
                # Verify the response parsing
                assert result["query"] == "site:commbank.com.au home loan rates"
                assert result["total_results"] == "2"
                assert len(result["urls"]) == 2
                assert "commbank.com.au/personal/home-loans/interest-rates.html" in result["urls"]
                assert "commbank.com.au/personal/home-loans/our-home-loans.html" in result["urls"]
                assert result["engine"] == "google_custom_search"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
