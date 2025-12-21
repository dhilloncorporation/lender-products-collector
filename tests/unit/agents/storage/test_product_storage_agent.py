"""Test cases for ProductStorageAgent."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from src.agents.storage.product_storage import ProductStorageAgent
from src.models import LoanProduct
from tests.utils.mock_data import get_mock_products


class TestProductStorageAgent:
    """Test cases for ProductStorageAgent."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir

    @pytest.fixture
    def storage_agent(self, temp_dir):
        """Create ProductStorageAgent instance with temp directory."""
        return ProductStorageAgent(storage_path=temp_dir)

    @pytest.fixture
    def mock_products(self):
        """Get mock products for testing."""
        return get_mock_products()

    def test_init(self, storage_agent, temp_dir):
        """Test storage agent initialization."""
        assert storage_agent.storage_path == Path(temp_dir)
        assert storage_agent.product_index == {}
        assert storage_agent.storage_path.exists()

    def test_init_with_existing_index(self, temp_dir):
        """Test initialization with existing index file."""
        # Create existing index
        index_file = Path(temp_dir) / "index.json"
        existing_index = {"hash1": "path1.json", "hash2": "path2.json"}
        with open(index_file, 'w') as f:
            json.dump(existing_index, f)
        
        agent = ProductStorageAgent(storage_path=temp_dir)
        assert len(agent.product_index) == 2
        assert agent.product_index == existing_index

    def test_store_products_success(self, storage_agent, mock_products):
        """Test successful product storage."""
        result = storage_agent.store_products(mock_products)
        
        assert result["stored"] == 2
        assert result["duplicates"] == 0
        assert result["errors"] == 0
        assert "batch_id" in result
        
        # Verify files were created
        batch_dirs = list(storage_agent.storage_path.glob("*"))
        assert len(batch_dirs) == 1
        assert batch_dirs[0].is_dir()

    def test_store_products_with_duplicates(self, storage_agent, mock_products):
        """Test storing products with duplicates."""
        # Store products first time
        storage_agent.store_products(mock_products)
        
        # Store same products again
        result = storage_agent.store_products(mock_products)
        
        assert result["stored"] == 0
        assert result["duplicates"] == 2
        assert result["errors"] == 0

    def test_store_products_empty_list(self, storage_agent):
        """Test storing empty product list."""
        result = storage_agent.store_products([])
        
        assert result["stored"] == 0
        assert result["duplicates"] == 0
        assert result["errors"] == 0

    def test_get_products_no_filters(self, storage_agent, mock_products):
        """Test getting products without filters."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent.get_products()
        
        assert len(products) == 2
        assert all(isinstance(p, LoanProduct) for p in products)

    def test_get_products_with_lender_filter(self, storage_agent, mock_products):
        """Test getting products filtered by lender."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent.get_products(lender="ANZ")
        
        assert len(products) == 1
        assert products[0].lender == "ANZ"

    def test_get_products_with_rate_type_filter(self, storage_agent, mock_products):
        """Test getting products filtered by rate type."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent.get_products(rate_type="Variable")
        
        assert len(products) >= 1
        assert all(p.rate_type.lower() == "variable" for p in products)

    def test_get_products_with_rate_range(self, storage_agent, mock_products):
        """Test getting products filtered by rate range."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent.get_products(min_rate=6.0, max_rate=7.0)
        
        assert all(6.0 <= float(p.rate_percent) <= 7.0 for p in products)

    def test_get_products_with_limit(self, storage_agent, mock_products):
        """Test getting products with limit."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent.get_products(limit=1)
        
        assert len(products) == 1

    def test_get_product_changes(self, storage_agent, mock_products):
        """Test getting product changes."""
        storage_agent.store_products(mock_products)
        
        changes = storage_agent.get_product_changes(days=7)
        
        assert "period_days" in changes
        assert "products_changed" in changes
        assert "products" in changes
        assert changes["period_days"] == 7
        assert changes["products_changed"] >= 0

    def test_get_product_changes_old_products(self, storage_agent, mock_products):
        """Test getting changes with old products."""
        # Store products
        storage_agent.store_products(mock_products)
        
        # Manually modify collected_at to be old
        for product_file in storage_agent.storage_path.rglob("*.json"):
            with open(product_file, 'r') as f:
                product_dict = json.load(f)
            product_dict["collected_at"] = (datetime.now() - timedelta(days=10)).isoformat()
            with open(product_file, 'w') as f:
                json.dump(product_dict, f)
        
        changes = storage_agent.get_product_changes(days=7)
        
        assert changes["products_changed"] == 0

    def test_get_storage_stats(self, storage_agent, mock_products):
        """Test getting storage statistics."""
        storage_agent.store_products(mock_products)
        
        stats = storage_agent.get_storage_stats()
        
        assert stats["total_products"] == 2
        assert stats["unique_products"] == 2
        assert "lender_breakdown" in stats
        assert "rate_type_breakdown" in stats
        assert "ANZ" in stats["lender_breakdown"]
        assert "CBA" in stats["lender_breakdown"]

    def test_generate_product_hash(self, storage_agent, mock_products):
        """Test product hash generation."""
        product = mock_products[0]
        hash1 = storage_agent._generate_product_hash(product)
        hash2 = storage_agent._generate_product_hash(product)
        
        # Same product should generate same hash
        assert hash1 == hash2
        
        # Different product should generate different hash
        product2 = mock_products[1]
        hash3 = storage_agent._generate_product_hash(product2)
        assert hash1 != hash3

    def test_store_single_product(self, storage_agent, mock_products):
        """Test storing a single product."""
        product = mock_products[0]
        batch_id = "test_batch_001"
        
        file_path = storage_agent._store_single_product(product, batch_id)
        
        assert file_path.exists()
        assert batch_id in str(file_path)
        
        # Verify file content
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert data["lender"] == product.lender
            assert data["product_name"] == product.product_name

    def test_product_to_dict(self, storage_agent, mock_products):
        """Test product to dictionary conversion."""
        product = mock_products[0]
        product_dict = storage_agent._product_to_dict(product)
        
        assert product_dict["lender"] == product.lender
        assert product_dict["product_name"] == product.product_name
        assert float(product_dict["rate_percent"]) == float(product.rate_percent)
        assert "collected_at" in product_dict

    def test_dict_to_product(self, storage_agent, mock_products):
        """Test dictionary to product conversion."""
        product = mock_products[0]
        product_dict = storage_agent._product_to_dict(product)
        
        converted_product = storage_agent._dict_to_product(product_dict)
        
        assert converted_product is not None
        assert converted_product.lender == product.lender
        assert converted_product.product_name == product.product_name
        assert float(converted_product.rate_percent) == float(product.rate_percent)

    def test_dict_to_product_invalid(self, storage_agent):
        """Test dictionary to product conversion with invalid data."""
        invalid_dict = {"invalid": "data"}
        
        product = storage_agent._dict_to_product(invalid_dict)
        
        assert product is None

    def test_load_all_products(self, storage_agent, mock_products):
        """Test loading all products from storage."""
        storage_agent.store_products(mock_products)
        
        products = storage_agent._load_all_products()
        
        assert len(products) == 2
        assert all(isinstance(p, LoanProduct) for p in products)

    def test_update_index(self, storage_agent, mock_products):
        """Test updating product index."""
        storage_agent.store_products(mock_products)
        
        index_file = storage_agent.storage_path / "index.json"
        assert index_file.exists()
        
        with open(index_file, 'r') as f:
            index_data = json.load(f)
        
        assert len(index_data) == 2

    def test_load_existing_products(self, temp_dir):
        """Test loading existing products on initialization."""
        # Create index file
        index_file = Path(temp_dir) / "index.json"
        existing_index = {"hash1": "path1.json", "hash2": "path2.json"}
        with open(index_file, 'w') as f:
            json.dump(existing_index, f)
        
        agent = ProductStorageAgent(storage_path=temp_dir)
        
        assert len(agent.product_index) == 2
        assert agent.product_index == existing_index

    def test_load_existing_products_no_index(self, temp_dir):
        """Test initialization when no index exists."""
        agent = ProductStorageAgent(storage_path=temp_dir)
        
        assert agent.product_index == {}

    def test_error_handling_invalid_product(self, storage_agent):
        """Test error handling with invalid product data."""
        # Create invalid product file
        invalid_file = storage_agent.storage_path / "batch1" / "invalid.json"
        invalid_file.parent.mkdir(exist_ok=True)
        with open(invalid_file, 'w') as f:
            json.dump({"invalid": "data"}, f)
        
        products = storage_agent._load_all_products()
        
        # Should skip invalid file
        assert len(products) == 0

    def test_deduplication_logic(self, storage_agent, mock_products):
        """Test product deduplication logic."""
        # Store products
        result1 = storage_agent.store_products(mock_products)
        assert result1["stored"] == 2
        
        # Store same products again
        result2 = storage_agent.store_products(mock_products)
        assert result2["stored"] == 0
        assert result2["duplicates"] == 2
        
        # Store new product
        new_product = LoanProduct(
            lender="NAB",
            product_name="NAB New Product",
            rate_percent=Decimal("6.5"),
            comparison_rate_percent=Decimal("6.8"),
            term_months=360,
            rate_type="Variable",
            fees_breakdown={},
            features=[],
            lvr_max=Decimal("95"),
            dti_max=None,
            postcode_flags=[],
            source_url="https://nab.com.au",
            collected_at=datetime.now()
        )
        
        result3 = storage_agent.store_products([new_product])
        assert result3["stored"] == 1
        assert result3["duplicates"] == 0

