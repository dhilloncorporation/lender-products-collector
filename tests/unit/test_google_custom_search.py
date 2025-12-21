"""Unit tests for Google Custom Search API."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import os
import asyncio
from src.agents.discovery.google_custom_search import GoogleCustomSearchAPI


class TestGoogleCustomSearchAPI:
    """Test cases for GoogleCustomSearchAPI."""
    
    @pytest.fixture
    def mock_settings_manager(self):
        """Mock settings manager."""
        settings = Mock()
        return settings
    
    @pytest.fixture
    def api_with_env_vars(self, mock_settings_manager):
        """Create API instance with mocked environment variables."""
        with patch.dict(os.environ, {
            'CUSTOM_SEARCH_API_KEY': 'test_api_key',
            'CUSTOM_SEARCH_CX': 'test_search_engine_id'
        }):
            return GoogleCustomSearchAPI(mock_settings_manager)
    
    def test_init_with_valid_env_vars(self, mock_settings_manager):
        """Test initialization with valid environment variables."""
        with patch.dict(os.environ, {
            'CUSTOM_SEARCH_API_KEY': 'test_api_key',
            'CUSTOM_SEARCH_CX': 'test_search_engine_id'
        }):
            api = GoogleCustomSearchAPI(mock_settings_manager)
            assert api.api_key == 'test_api_key'
            assert api.search_engine_id == 'test_search_engine_id'
            assert api.base_url == "https://www.googleapis.com/customsearch/v1"
            assert api.daily_limit == 100
    
    def test_init_missing_api_key(self, mock_settings_manager):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {'CUSTOM_SEARCH_CX': 'test_id'}, clear=True):
            with pytest.raises(ValueError, match="CUSTOM_SEARCH_API_KEY environment variable not set"):
                GoogleCustomSearchAPI(mock_settings_manager)
    
    def test_init_missing_search_engine_id(self, mock_settings_manager):
        """Test initialization fails without search engine ID."""
        with patch.dict(os.environ, {'CUSTOM_SEARCH_API_KEY': 'test_key'}, clear=True):
            with pytest.raises(ValueError, match="CUSTOM_SEARCH_CX environment variable not set"):
                GoogleCustomSearchAPI(mock_settings_manager)
    
    @pytest.mark.asyncio
    async def test_search_success(self, api_with_env_vars):
        """Test successful search."""
        mock_response_data = {
            "items": [
                {"title": "Test Result 1", "link": "https://example.com/1", "snippet": "Test snippet 1"},
                {"title": "Test Result 2", "link": "https://example.com/2", "snippet": "Test snippet 2"}
            ],
            "searchInformation": {"totalResults": "2"}
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await api_with_env_vars.search("test query", num_results=5)
            
            assert result["query"] == "test query"
            assert len(result["urls"]) == 2
            assert result["urls"][0] == "https://example.com/1"
            assert result["urls"][1] == "https://example.com/2"
            assert result["total_results"] == "2"
            assert result["engine"] == "google_custom_search"
            assert result["queries_used"] == 1
            assert result["queries_remaining"] == 99
    
    @pytest.mark.asyncio
    async def test_search_http_error_403(self, api_with_env_vars):
        """Test search with HTTP 403 error (quota exceeded)."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = "Quota exceeded"
            
            from httpx import HTTPStatusError
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "403 Client Error", request=Mock(), response=mock_response
            )
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with pytest.raises(Exception, match="Google Custom Search API quota exceeded"):
                await api_with_env_vars.search("test query")
    
    @pytest.mark.asyncio
    async def test_search_http_error_400(self, api_with_env_vars):
        """Test search with HTTP 400 error (invalid parameters)."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invalid parameters"
            
            from httpx import HTTPStatusError
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "400 Client Error", request=Mock(), response=mock_response
            )
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with pytest.raises(Exception, match="Invalid search request parameters"):
                await api_with_env_vars.search("test query")
    
    @pytest.mark.asyncio
    async def test_search_daily_limit_exceeded(self, api_with_env_vars):
        """Test search when daily limit is exceeded."""
        api_with_env_vars.queries_today = 100  # Set to daily limit
        
        with pytest.raises(Exception, match="Daily limit reached"):
            await api_with_env_vars.search("test query")
    
    @pytest.mark.asyncio
    async def test_discover_lender_pages_success(self, api_with_env_vars):
        """Test successful lender page discovery."""
        mock_search_results = {
            "items": [
                {"title": "Home Loan Rates", "link": "https://commbank.com.au/rates", "snippet": "Current rates"},
                {"title": "Home Loan Products", "link": "https://commbank.com.au/products", "snippet": "Our products"}
            ],
            "searchInformation": {"totalResults": "2"}
        }
        
        with patch.object(api_with_env_vars, 'search', return_value={
            "urls": ["https://commbank.com.au/rates", "https://commbank.com.au/products"],
            "total_results": "2"
        }) as mock_search:
            result = await api_with_env_vars.discover_lender_pages(
                "Commonwealth Bank", "commbank.com.au"
            )
            
            # Should have called search multiple times (once per template)
            assert mock_search.call_count >= 4  # At least 4 templates
            
            # Check result structure
            assert "interest_rates" in result
            assert "products" in result
            assert "comparison" in result
            assert "fees" in result
            
            # All categories should be lists
            for category, urls in result.items():
                assert isinstance(urls, list)
    
    @pytest.mark.asyncio
    async def test_discover_lender_pages_with_exceptions(self, api_with_env_vars):
        """Test lender page discovery with some search failures."""
        with patch.object(api_with_env_vars, 'search', side_effect=[
            Exception("Search failed"),  # First search fails
            {"urls": ["https://commbank.com.au/products"], "total_results": "1"},  # Second succeeds
            Exception("Search failed"),  # Third fails
            {"urls": ["https://commbank.com.au/rates"], "total_results": "1"}   # Fourth succeeds
        ]):
            result = await api_with_env_vars.discover_lender_pages(
                "Commonwealth Bank", "commbank.com.au"
            )
            
            # Should still return results for successful searches
            assert isinstance(result, dict)
            assert "interest_rates" in result
            assert "products" in result
    
    def test_is_valid_lender_url(self, api_with_env_vars):
        """Test URL validation."""
        # Valid URLs
        assert api_with_env_vars._is_valid_lender_url("https://commbank.com.au/rates", "commbank.com.au")
        assert api_with_env_vars._is_valid_lender_url("https://commbank.com.au/personal/home-loans", "commbank.com.au")
        
        # Invalid URLs
        assert not api_with_env_vars._is_valid_lender_url("", "commbank.com.au")
        assert not api_with_env_vars._is_valid_lender_url(None, "commbank.com.au")
        assert not api_with_env_vars._is_valid_lender_url("https://other.com/rates", "commbank.com.au")
        assert not api_with_env_vars._is_valid_lender_url("https://commbank.com.au/document.pdf", "commbank.com.au")
        assert not api_with_env_vars._is_valid_lender_url("https://commbank.com.au/privacy", "commbank.com.au")
        assert not api_with_env_vars._is_valid_lender_url("https://commbank.com.au/#section", "commbank.com.au")
    
    def test_get_usage_stats(self, api_with_env_vars):
        """Test usage statistics."""
        api_with_env_vars.queries_today = 25
        
        stats = api_with_env_vars.get_usage_stats()
        
        assert stats["queries_used"] == 25
        assert stats["queries_remaining"] == 75
        assert stats["daily_limit"] == 100
        assert stats["cost_per_1000"] == 5.00
        assert stats["estimated_cost"] == 0.125  # (25/1000) * 5.00


if __name__ == "__main__":
    pytest.main([__file__])
