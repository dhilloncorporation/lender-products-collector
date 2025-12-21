"""Test cases for ProductAPIAgent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.agents.api.product_api import ProductAPIAgent
from src.models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria
from tests.utils.mock_data import get_mock_products


class TestProductAPIAgent:
    """Test cases for ProductAPIAgent."""

    @pytest.fixture
    def mock_storage_agent(self):
        """Mock storage agent."""
        storage = Mock()
        storage.get_products = Mock(return_value=get_mock_products())
        storage.get_storage_stats = Mock(return_value={
            "total_products": 2,
            "lenders": ["ANZ", "CBA"],
            "last_updated": "2025-01-01T12:00:00"
        })
        storage.get_product_changes = Mock(return_value={
            "changes_count": 0,
            "changed_products": []
        })
        return storage

    @pytest.fixture
    def mock_monitor_agent(self):
        """Mock monitor agent."""
        monitor = Mock()
        monitor.log_collection_start = Mock()
        monitor.get_system_health = Mock(return_value={
            "status": "healthy",
            "timestamp": "2025-01-01T12:00:00"
        })
        monitor.get_collection_stats = Mock(return_value={
            "successful_collections": 2,
            "failed_collections": 0,
            "total_products_collected": 8
        })
        return monitor

    @pytest.fixture
    def api_agent(self, mock_storage_agent, mock_monitor_agent):
        """Create ProductAPIAgent instance."""
        return ProductAPIAgent(mock_storage_agent, mock_monitor_agent)

    @pytest.fixture
    def test_client(self, api_agent):
        """Create test client for API testing."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(api_agent.get_router())
        return TestClient(app)

    def test_init(self, api_agent, mock_storage_agent, mock_monitor_agent):
        """Test API agent initialization."""
        assert api_agent.storage_agent == mock_storage_agent
        assert api_agent.monitor_agent == mock_monitor_agent
        assert api_agent.router is not None

    def test_get_router(self, api_agent):
        """Test getting the FastAPI router."""
        router = api_agent.get_router()
        assert router is not None
        assert len(router.routes) > 0

    def test_get_products_no_filters(self, test_client, mock_storage_agent):
        """Test getting products without filters."""
        response = test_client.get("/products")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["lender"] == "ANZ"
        assert data[1]["lender"] == "CBA"
        
        # Verify storage agent was called
        mock_storage_agent.get_products.assert_called_once_with(
            lender=None,
            rate_type=None,
            min_rate=None,
            max_rate=None,
            limit=100
        )

    def test_get_products_with_filters(self, test_client, mock_storage_agent):
        """Test getting products with filters."""
        response = test_client.get("/products?lender=ANZ&rate_type=variable&min_rate=6.0&max_rate=7.0&limit=50")
        
        assert response.status_code == 200
        
        # Verify storage agent was called with filters
        mock_storage_agent.get_products.assert_called_once_with(
            lender="ANZ",
            rate_type="variable",
            min_rate=6.0,
            max_rate=7.0,
            limit=50
        )

    def test_get_products_storage_error(self, test_client, mock_storage_agent):
        """Test getting products when storage agent raises error."""
        mock_storage_agent.get_products.side_effect = Exception("Storage error")
        
        response = test_client.get("/products")
        
        assert response.status_code == 500
        assert "Storage error" in response.json()["detail"]

    def test_get_products_by_lender_success(self, test_client, mock_storage_agent):
        """Test getting products by specific lender."""
        # Mock storage to return only ANZ products
        anz_products = [p for p in get_mock_products() if p.lender == "ANZ"]
        mock_storage_agent.get_products.return_value = anz_products
        
        response = test_client.get("/products/ANZ")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lender"] == "ANZ"
        
        # Verify storage agent was called with lender filter
        mock_storage_agent.get_products.assert_called_once_with(
            lender="ANZ",
            limit=50
        )

    def test_get_products_by_lender_not_found(self, test_client, mock_storage_agent):
        """Test getting products for non-existent lender."""
        mock_storage_agent.get_products.return_value = []
        
        response = test_client.get("/products/NONEXISTENT")
        
        assert response.status_code == 404
        assert "No products found for lender: NONEXISTENT" in response.json()["detail"]

    def test_get_product_stats_success(self, test_client, mock_storage_agent):
        """Test getting product statistics."""
        response = test_client.get("/products/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] == 2
        assert "ANZ" in data["lenders"]
        assert "CBA" in data["lenders"]
        assert "last_updated" in data

    def test_health_check_success(self, test_client, mock_monitor_agent):
        """Test health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_get_monitoring_stats_success(self, test_client, mock_monitor_agent):
        """Test getting monitoring statistics."""
        response = test_client.get("/monitoring/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["successful_collections"] == 2
        assert data["failed_collections"] == 0
        assert data["total_products_collected"] == 8

    def test_api_logging(self, test_client, mock_monitor_agent):
        """Test that API requests are logged."""
        response = test_client.get("/products")
        
        assert response.status_code == 200
        
        # Verify monitor agent was called to log the request
        mock_monitor_agent.log_collection_start.assert_called_once_with(
            "api_request", "product_query"
        )

    def test_route_setup(self, api_agent):
        """Test that all routes are properly set up."""
        router = api_agent.get_router()
        
        # Get all route paths
        route_paths = [route.path for route in router.routes]
        
        # Verify all expected routes exist
        assert "/products" in route_paths
        assert "/products/{lender}" in route_paths
        assert "/products/stats" in route_paths
        assert "/products/changes" in route_paths
        assert "/health" in route_paths
        assert "/monitoring/stats" in route_paths

    def test_response_model_validation(self, test_client, mock_storage_agent):
        """Test that response models are properly validated."""
        # Mock products with proper structure
        mock_products = get_mock_products()
        mock_storage_agent.get_products.return_value = mock_products
        
        response = test_client.get("/products")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches LoanProduct model
        for product in data:
            assert "product_id" in product
            assert "name" in product
            assert "lender" in product
            assert "interest_components" in product
            assert "eligibility" in product

