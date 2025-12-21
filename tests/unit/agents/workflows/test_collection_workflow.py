"""Unit tests for collection workflow."""

import pytest
from unittest.mock import Mock, patch
from src.agents.workflows.collection_workflow import CollectionWorkflow, CollectionState
from src.configs.settings_manager import YamlSettingsManager
from src.configs.lender_config import LenderConfigManager


class TestCollectionWorkflow:
    """Test cases for CollectionWorkflow."""
    
    @pytest.fixture
    def mock_settings_manager(self):
        """Mock settings manager."""
        settings = Mock(spec=YamlSettingsManager)
        settings.get_ai.return_value = Mock(
            model_name="gpt-4o-mini",
            temperature=0.1,
            max_tokens=4000,
            api_key_env="OPENAI_API_KEY"
        )
        settings.get_collection_settings.return_value = Mock(
            max_retries=3,
            timeout_seconds=30,
            concurrent_collections=5,
            rate_limit_per_minute=60,
            default_frequency="daily",
            volatile_lenders_hourly=True
        )
        return settings
    
    @pytest.fixture
    def mock_lender_config_manager(self):
        """Mock lender config manager."""
        config = Mock(spec=LenderConfigManager)
        config.get_enabled_lenders.return_value = [
            {"abbreviation": "ANZ", "priority": 1},
            {"abbreviation": "CBA", "priority": 1}
        ]
        return config
    
    @pytest.fixture
    def workflow(self, mock_settings_manager, mock_lender_config_manager):
        """Create workflow instance."""
        with patch('src.agents.workflows.collection_workflow.ChatOpenAI'):
            return CollectionWorkflow(mock_settings_manager, mock_lender_config_manager)
    
    def test_initialize_collection(self, workflow):
        """Test collection initialization."""
        state = CollectionState(
            lenders=[],
            current_lender="",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=0,
            success_count=0,
            failure_count=0
        )
        
        result = workflow._initialize_collection(state)
        
        assert result["total_lenders"] == 2
        assert len(result["lenders"]) == 2
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
    
    def test_select_lender(self, workflow):
        """Test lender selection."""
        state = CollectionState(
            lenders=[
                {"abbreviation": "ANZ", "priority": 1},
                {"abbreviation": "CBA", "priority": 2}
            ],
            current_lender="",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=2,
            success_count=0,
            failure_count=0
        )
        
        result = workflow._select_lender(state)
        
        assert result["current_lender"] == "ANZ"  # Lower priority number
    
    def test_should_continue(self, workflow):
        """Test continuation logic."""
        # Should continue
        state = CollectionState(
            lenders=[],
            current_lender="",
            collection_results={},
            errors=[],
            completed_lenders=["ANZ"],
            total_lenders=2,
            success_count=0,
            failure_count=0
        )
        assert workflow._should_continue(state) == "continue"
        
        # Should finish
        state["completed_lenders"] = ["ANZ", "CBA"]
        assert workflow._should_continue(state) == "finish"
    
    @pytest.mark.asyncio
    async def test_discover_urls_with_configured_urls(self, workflow):
        """Test URL discovery with configured URLs (preferred strategy)."""
        # Mock lender config with collection_urls
        mock_lender_config = {
            "abbreviation": "ANZ",
            "lender_name": "ANZ Bank",
            "domain": "anz.com",
            "collection_urls": [
                "https://anz.com/personal/home-loans/our-home-loans",
                "https://anz.com/personal/home-loans/interest-rates"
            ]
        }
        
        workflow.lender_config_manager.get_lender_by_abbreviation.return_value = mock_lender_config
        
        state = CollectionState(
            lenders=[],
            current_lender="ANZ",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=1,
            success_count=0,
            failure_count=0
        )
        
        result = await workflow._discover_urls(state)
        
        # Should use configured URLs
        assert result["current_lender_urls"] == mock_lender_config["collection_urls"]
        assert len(result["current_lender_urls"]) == 2
        assert "errors" not in result or len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_discover_urls_with_google_fallback(self, workflow):
        """Test URL discovery with Google search fallback."""
        # Mock lender config without collection_urls
        mock_lender_config = {
            "abbreviation": "CBA",
            "lender_name": "Commonwealth Bank",
            "domain": "commbank.com.au"
        }
        
        workflow.lender_config_manager.get_lender_by_abbreviation.return_value = mock_lender_config
        
        # Mock discovery results
        mock_discovery_results = {
            "interest_rates": ["https://commbank.com.au/personal/home-loans/interest-rates"],
            "products": ["https://commbank.com.au/personal/home-loans/our-home-loans"],
            "comparison": ["https://commbank.com.au/personal/home-loans/compare"]
        }
        
        workflow.discovery.discover_lender_pages.return_value = mock_discovery_results
        
        state = CollectionState(
            lenders=[],
            current_lender="CBA",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=1,
            success_count=0,
            failure_count=0
        )
        
        result = await workflow._discover_urls(state)
        
        # Should use Google search results
        assert len(result["current_lender_urls"]) == 3
        assert "https://commbank.com.au/personal/home-loans/interest-rates" in result["current_lender_urls"]
        assert "https://commbank.com.au/personal/home-loans/our-home-loans" in result["current_lender_urls"]
        assert "https://commbank.com.au/personal/home-loans/compare" in result["current_lender_urls"]
        assert "errors" not in result or len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_discover_urls_google_search_failure(self, workflow):
        """Test URL discovery when Google search fails."""
        # Mock lender config without collection_urls
        mock_lender_config = {
            "abbreviation": "CBA",
            "lender_name": "Commonwealth Bank",
            "domain": "commbank.com.au"
        }
        
        workflow.lender_config_manager.get_lender_by_abbreviation.return_value = mock_lender_config
        
        # Mock empty discovery results (Google search failed)
        workflow.discovery.discover_lender_pages.return_value = {
            "interest_rates": [],
            "products": [],
            "comparison": []
        }
        
        state = CollectionState(
            lenders=[],
            current_lender="CBA",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=1,
            success_count=0,
            failure_count=0
        )
        
        result = await workflow._discover_urls(state)
        
        # Should return empty URLs and error
        assert result["current_lender_urls"] == []
        assert len(result["errors"]) == 1
        assert "Failed to get URLs for CBA" in result["errors"][0]
        assert "No collection_urls in config AND Google search failed" in result["errors"][0]
    
    @pytest.mark.asyncio
    async def test_discover_urls_lender_not_found(self, workflow):
        """Test URL discovery when lender config is not found."""
        workflow.lender_config_manager.get_lender_by_abbreviation.return_value = None
        
        state = CollectionState(
            lenders=[],
            current_lender="UNKNOWN",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=1,
            success_count=0,
            failure_count=0
        )
        
        result = await workflow._discover_urls(state)
        
        # Should return empty URLs and error
        assert result["current_lender_urls"] == []
        assert len(result["errors"]) == 1
        assert "No configuration found for lender: UNKNOWN" in result["errors"][0]
    
    @pytest.mark.asyncio
    async def test_discover_urls_exception_handling(self, workflow):
        """Test URL discovery exception handling."""
        # Mock lender config
        mock_lender_config = {
            "abbreviation": "CBA",
            "lender_name": "Commonwealth Bank",
            "domain": "commbank.com.au"
        }
        
        workflow.lender_config_manager.get_lender_by_abbreviation.return_value = mock_lender_config
        
        # Mock discovery to raise exception
        workflow.discovery.discover_lender_pages.side_effect = Exception("Network error")
        
        state = CollectionState(
            lenders=[],
            current_lender="CBA",
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=1,
            success_count=0,
            failure_count=0
        )
        
        result = await workflow._discover_urls(state)
        
        # Should return empty URLs and error
        assert result["current_lender_urls"] == []
        assert len(result["errors"]) == 1
        assert "URL discovery exception for CBA: Network error" in result["errors"][0]
