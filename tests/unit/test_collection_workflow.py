"""Unit tests for collection workflow."""

import pytest
from unittest.mock import Mock, patch
from src.agents.workflows.collection_workflow import CollectionWorkflow, CollectionState
from src.configs.settings_manager import SettingsManager
from src.configs.lender_config import LenderConfigManager


class TestCollectionWorkflow:
    """Test cases for CollectionWorkflow."""
    
    @pytest.fixture
    def mock_settings_manager(self):
        """Mock settings manager."""
        settings = Mock(spec=SettingsManager)
        settings.get_langchain_settings.return_value = Mock(
            model_name="gpt-4o-mini",
            temperature=0.1,
            max_tokens=4000,
            api_key_env="OPENAI_API_KEY"
        )
        settings.get_langgraph_settings.return_value = Mock(
            state_management="memory",
            max_iterations=10,
            checkpointer_type="sqlite",
            checkpointer_config={"db_path": "test.db"}
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
