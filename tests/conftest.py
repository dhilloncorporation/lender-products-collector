"""Pytest configuration and fixtures."""

import pytest
import os
import tempfile
from unittest.mock import Mock


@pytest.fixture(scope="session")
def test_config_dir():
    """Create temporary config directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for tests."""
    with pytest.MonkeyPatch().context() as m:
        m.setenv("FIRECRAWL_API_KEY", "test_firecrawl_key")
        m.setenv("OPENAI_API_KEY", "test_openai_key")
        yield


@pytest.fixture
def mock_settings_manager():
    """Mock settings manager for tests."""
    settings = Mock()
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
def mock_lender_config_manager():
    """Mock lender config manager for tests."""
    config = Mock()
    config.get_enabled_lenders.return_value = [
        {
            "abbreviation": "ANZ",
            "lender_name": "Australia and New Zealand Banking Group",
            "lender_type": "major_bank",
            "priority": 1
        },
        {
            "abbreviation": "CBA", 
            "lender_name": "Commonwealth Bank of Australia",
            "lender_type": "major_bank",
            "priority": 1
        }
    ]
    return config
