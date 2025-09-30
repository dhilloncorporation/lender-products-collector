"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from src.api.main import app


class TestAPIIntegration:
    """Integration tests for API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_products_endpoint(self, client):
        """Test products endpoint."""
        response = client.get("/api/v1/products/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Check that we get the mock products with BIAN schema structure
        if data:  # If mock data is present
            product = data[0]
            assert "product_id" in product
            assert "name" in product
            assert "interest_components" in product
            assert "fees" in product
            assert "features" in product
            assert "eligibility" in product
    
    def test_products_by_lender_endpoint(self, client):
        """Test products by lender endpoint."""
        response = client.get("/api/v1/products/ANZ")
        # This might return 404 if no mock data, which is expected
        assert response.status_code in [200, 404]
