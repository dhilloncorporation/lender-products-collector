"""Test cases for JSONStorageService."""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.services.json_storage import JSONStorageService
from src.models import LoanProduct, InterestComponent, FeeStructure, ProductFeatures, EligibilityCriteria
from tests.utils.mock_data import get_mock_products


class TestJSONStorageService:
    """Test cases for JSONStorageService."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir

    @pytest.fixture
    def storage_service(self, temp_dir):
        """Create JSONStorageService instance with temp directory."""
        return JSONStorageService(base_path=temp_dir)

    @pytest.fixture
    def mock_products(self):
        """Get mock products for testing."""
        return get_mock_products()

    def test_init(self, storage_service, temp_dir):
        """Test service initialization."""
        assert storage_service.base_path == Path(temp_dir)
        
        # Check that directories were created
        assert (Path(temp_dir) / "current").exists()
        assert (Path(temp_dir) / "current" / "by_lender").exists()
        assert (Path(temp_dir) / "snapshots" / "raw").exists()
        assert (Path(temp_dir) / "snapshots" / "parsed").exists()
        assert (Path(temp_dir) / "diffs").exists()

    def test_init_custom_path(self):
        """Test initialization with custom path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = JSONStorageService(base_path=tmp_dir)
            assert service.base_path == Path(tmp_dir)

    @pytest.mark.asyncio
    async def test_save_current_products_with_lender(self, storage_service, mock_products):
        """Test saving current products with lender specified."""
        file_path = await storage_service.save_current_products(mock_products, "ANZ")
        
        assert file_path.endswith("ANZ.json")
        assert Path(file_path).exists()
        
        # Verify file content
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert len(data) == 2
            assert data[0]["lender"] == "ANZ"
            assert data[1]["lender"] == "CBA"

    @pytest.mark.asyncio
    async def test_save_current_products_without_lender(self, storage_service, mock_products):
        """Test saving current products without lender specified."""
        file_path = await storage_service.save_current_products(mock_products)
        
        assert file_path.endswith("products.json")
        assert Path(file_path).exists()
        
        # Verify file content
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_save_current_products_empty_list(self, storage_service):
        """Test saving empty product list."""
        file_path = await storage_service.save_current_products([], "ANZ")
        
        assert Path(file_path).exists()
        
        # Verify file content
        with open(file_path, 'r') as f:
            data = json.load(f)
            assert data == []

    @pytest.mark.asyncio
    async def test_save_snapshot_parsed_only(self, storage_service, mock_products):
        """Test saving snapshot with parsed products only."""
        saved_files = await storage_service.save_snapshot(mock_products, "ANZ")
        
        assert "parsed" in saved_files
        assert Path(saved_files["parsed"]).exists()
        
        # Verify file content
        with open(saved_files["parsed"], 'r') as f:
            data = json.load(f)
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_save_snapshot_with_raw_html(self, storage_service, mock_products):
        """Test saving snapshot with raw HTML."""
        raw_html = {
            "https://example.com/page1": "<html>Page 1 content</html>",
            "https://example.com/page2": "<html>Page 2 content</html>"
        }
        
        saved_files = await storage_service.save_snapshot(mock_products, "ANZ", raw_html)
        
        assert "parsed" in saved_files
        assert "raw_page1" in saved_files
        assert "raw_page2" in saved_files
        
        # Verify parsed file
        assert Path(saved_files["parsed"]).exists()
        
        # Verify raw HTML files
        with open(saved_files["raw_page1"], 'r') as f:
            assert f.read() == "<html>Page 1 content</html>"
        
        with open(saved_files["raw_page2"], 'r') as f:
            assert f.read() == "<html>Page 2 content</html>"

    @pytest.mark.asyncio
    async def test_load_current_products_with_lender(self, storage_service, mock_products):
        """Test loading current products with lender specified."""
        # Save products first
        await storage_service.save_current_products(mock_products, "ANZ")
        
        # Load products
        loaded_products = await storage_service.load_current_products("ANZ")
        
        assert len(loaded_products) == 2
        assert loaded_products[0].lender == "ANZ"
        assert loaded_products[1].lender == "CBA"
        assert isinstance(loaded_products[0], LoanProduct)

    @pytest.mark.asyncio
    async def test_load_current_products_without_lender(self, storage_service, mock_products):
        """Test loading current products without lender specified."""
        # Save products first
        await storage_service.save_current_products(mock_products)
        
        # Load products
        loaded_products = await storage_service.load_current_products()
        
        assert len(loaded_products) == 2
        assert isinstance(loaded_products[0], LoanProduct)

    @pytest.mark.asyncio
    async def test_load_current_products_file_not_exists(self, storage_service):
        """Test loading products when file doesn't exist."""
        products = await storage_service.load_current_products("NONEXISTENT")
        assert products == []

    @pytest.mark.asyncio
    async def test_load_current_products_invalid_json(self, storage_service):
        """Test loading products with invalid JSON."""
        # Create file with invalid JSON
        file_path = storage_service.base_path / "current" / "by_lender" / "INVALID.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write("invalid json content")
        
        # Should handle gracefully
        products = await storage_service.load_current_products("INVALID")
        assert products == []

    @pytest.mark.asyncio
    async def test_update_index_new_file(self, storage_service):
        """Test updating index when file doesn't exist."""
        await storage_service.update_index(
            lender="ANZ",
            status="success",
            products_count=5,
            snapshot_path="data/snapshots/parsed/ANZ/2025-01-01-12-00-00.json"
        )
        
        index_file = storage_service.base_path / "index.json"
        assert index_file.exists()
        
        with open(index_file, 'r') as f:
            data = json.load(f)
            
            assert data["last_updated"] is not None
            assert len(data["collections"]) == 1
            assert data["collections"][0]["lender"] == "ANZ"
            assert data["collections"][0]["status"] == "success"
            assert data["collections"][0]["products_found"] == 5
            
            assert "ANZ" in data["lenders"]
            assert data["lenders"]["ANZ"]["total_products"] == 5

    @pytest.mark.asyncio
    async def test_update_index_existing_file(self, storage_service):
        """Test updating index when file already exists."""
        # Create initial index
        await storage_service.update_index(
            lender="ANZ",
            status="success",
            products_count=5,
            snapshot_path="data/snapshots/parsed/ANZ/2025-01-01-12-00-00.json"
        )
        
        # Update with new collection
        await storage_service.update_index(
            lender="CBA",
            status="success",
            products_count=3,
            snapshot_path="data/snapshots/parsed/CBA/2025-01-01-13-00-00.json"
        )
        
        index_file = storage_service.base_path / "index.json"
        
        with open(index_file, 'r') as f:
            data = json.load(f)
            
            assert len(data["collections"]) == 2
            assert data["collections"][0]["lender"] == "ANZ"
            assert data["collections"][1]["lender"] == "CBA"
            
            assert "ANZ" in data["lenders"]
            assert "CBA" in data["lenders"]

    @pytest.mark.asyncio
    async def test_update_index_failure_status(self, storage_service):
        """Test updating index with failure status."""
        await storage_service.update_index(
            lender="ANZ",
            status="failure",
            products_count=0,
            snapshot_path=""
        )
        
        index_file = storage_service.base_path / "index.json"
        
        with open(index_file, 'r') as f:
            data = json.load(f)
            
            assert len(data["collections"]) == 1
            assert data["collections"][0]["status"] == "failure"
            assert data["collections"][0]["products_found"] == 0
            
            # Lender should not be in lenders dict for failures
            assert "ANZ" not in data["lenders"]

    @pytest.mark.asyncio
    async def test_get_index_existing_file(self, storage_service):
        """Test getting index when file exists."""
        # Create index first
        await storage_service.update_index(
            lender="ANZ",
            status="success",
            products_count=5,
            snapshot_path="data/snapshots/parsed/ANZ/2025-01-01-12-00-00.json"
        )
        
        index_data = await storage_service.get_index()
        
        assert index_data["last_updated"] is not None
        assert len(index_data["collections"]) == 1
        assert "ANZ" in index_data["lenders"]

    @pytest.mark.asyncio
    async def test_get_index_no_file(self, storage_service):
        """Test getting index when file doesn't exist."""
        index_data = await storage_service.get_index()
        
        assert index_data["last_updated"] is None
        assert index_data["collections"] == []
        assert index_data["lenders"] == {}

    @pytest.mark.asyncio
    async def test_get_index_invalid_json(self, storage_service):
        """Test getting index with invalid JSON."""
        # Create file with invalid JSON
        index_file = storage_service.base_path / "index.json"
        
        with open(index_file, 'w') as f:
            f.write("invalid json content")
        
        # Should return default structure
        index_data = await storage_service.get_index()
        
        assert index_data["last_updated"] is None
        assert index_data["collections"] == []
        assert index_data["lenders"] == {}

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self, storage_service, mock_products):
        """Test complete save and load roundtrip."""
        # Save products
        await storage_service.save_current_products(mock_products, "ANZ")
        
        # Load products
        loaded_products = await storage_service.load_current_products("ANZ")
        
        # Verify data integrity
        assert len(loaded_products) == len(mock_products)
        
        for original, loaded in zip(mock_products, loaded_products):
            assert original.product_id == loaded.product_id
            assert original.name == loaded.name
            assert original.lender == loaded.lender
            assert len(original.interest_components) == len(loaded.interest_components)
            assert original.interest_components[0].comparison_rate_pct_au == loaded.interest_components[0].comparison_rate_pct_au

    @pytest.mark.asyncio
    async def test_snapshot_timestamp_format(self, storage_service, mock_products):
        """Test snapshot timestamp format."""
        saved_files = await storage_service.save_snapshot(mock_products, "ANZ")
        
        # Extract timestamp from filename
        parsed_file = Path(saved_files["parsed"])
        timestamp_str = parsed_file.stem
        
        # Should be in format YYYY-MM-DD-HH-MM-SS
        assert len(timestamp_str) == 19  # 4+1+2+1+2+1+2+1+2+1+2
        assert timestamp_str.count('-') == 5
        
        # Should be parseable as datetime
        try:
            datetime.strptime(timestamp_str, "%Y-%m-%d-%H-%M-%S")
        except ValueError:
            pytest.fail("Timestamp format is invalid")

    @pytest.mark.asyncio
    async def test_concurrent_saves(self, storage_service, mock_products):
        """Test concurrent save operations."""
        # Create multiple tasks for concurrent saves
        tasks = []
        for i in range(5):
            task = storage_service.save_current_products(mock_products, f"LENDER{i}")
            tasks.append(task)
        
        # Execute all saves concurrently
        file_paths = await asyncio.gather(*tasks)
        
        # Verify all files were created
        assert len(file_paths) == 5
        for file_path in file_paths:
            assert Path(file_path).exists()

    @pytest.mark.asyncio
    async def test_large_product_list(self, storage_service):
        """Test handling large product lists."""
        # Create a large list of products
        large_product_list = []
        for i in range(100):
            product = LoanProduct(
                product_id=f"product-{i}",
                version="1.0",
                status="active",
                name=f"Product {i}",
                short_name=f"Prod{i}",
                description=f"Description for product {i}",
                purpose="OwnerOccupied_Purchase",
                channels=["Branch", "Online"],
                interest_components=[
                    InterestComponent(
                        name=f"Rate {i}",
                        rate_type="Variable",
                        comparison_rate_pct_au=6.0 + (i * 0.01),
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
                lender="TEST",
                source_url=f"https://example.com/product{i}"
            )
            large_product_list.append(product)
        
        # Save large list
        file_path = await storage_service.save_current_products(large_product_list, "TEST")
        
        # Load and verify
        loaded_products = await storage_service.load_current_products("TEST")
        
        assert len(loaded_products) == 100
        assert loaded_products[0].product_id == "product-0"
        assert loaded_products[99].product_id == "product-99"

    @pytest.mark.asyncio
    async def test_error_handling_file_write(self, storage_service, mock_products):
        """Test error handling during file write."""
        # Mock aio_open to raise an exception
        with patch('aiofiles.open') as mock_open:
            mock_open.side_effect = IOError("Disk full")
            
            with pytest.raises(IOError):
                await storage_service.save_current_products(mock_products, "ANZ")

    @pytest.mark.asyncio
    async def test_error_handling_file_read(self, storage_service):
        """Test error handling during file read."""
        # Mock aio_open to raise an exception
        with patch('aiofiles.open') as mock_open:
            mock_open.side_effect = IOError("File not found")
            
            with pytest.raises(IOError):
                await storage_service.load_current_products("ANZ")

