"""
Storage Agent - Data Persistence and Management

ROLE: Worker Agent (Data Storage)
PURPOSE: Handles product data storage, deduplication, and versioning

This agent manages the persistence layer for collected loan products. It
provides functionality for storing, retrieving, filtering, and managing
product data with deduplication and versioning support.

FEATURES:
- Product storage with deduplication (hash-based)
- Versioning and change tracking
- Filtering and querying capabilities
- Statistics and reporting
- Data validation
- JSON file-based storage

STORAGE STRUCTURE:
- Products stored in JSON format
- Hash-based deduplication
- Index for fast lookups
- Version history tracking

DEPENDENCIES:
- LoanProduct models (BIAN schema)
- Pathlib for file operations

USAGE:
    storage = ProductStorageAgent(storage_path="data/products")
    result = storage.store_products(products)
    products = storage.get_products(lender="ANZ", rate_type="Variable")
"""

import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
from ...models import LoanProduct

logger = logging.getLogger(__name__)


class ProductStorageAgent:
    """
    Product storage agent for handling data persistence and deduplication.
    
    This agent manages the storage and retrieval of loan product data with
    built-in deduplication, versioning, and filtering capabilities.
    
    Attributes:
        storage_path: Base directory for storing product data
        product_index: Hash-based index for fast product lookups
    
    Features:
        - Hash-based deduplication (prevents duplicate products)
        - Version tracking (tracks product changes over time)
        - Filtering (by lender, rate_type, date range, etc.)
        - Statistics (product counts, change tracking)
        - JSON file-based storage
    
    Example:
        >>> storage = ProductStorageAgent()
        >>> result = storage.store_products(products)
        >>> print(f"Stored: {result['stored']}, Duplicates: {result['duplicates']}")
        >>> products = storage.get_products(lender="ANZ")
    """
    
    def __init__(self, storage_path: str = "data/products"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.product_index: Dict[str, str] = {}  # product_hash -> file_path
        self.load_existing_products()
    
    def store_products(self, products: List[LoanProduct], collection_batch: str = None) -> Dict[str, Any]:
        """Store products with deduplication and versioning."""
        if not products:
            return {"stored": 0, "duplicates": 0, "errors": 0}
        
        stored_count = 0
        duplicate_count = 0
        error_count = 0
        
        # Generate batch ID if not provided
        if not collection_batch:
            collection_batch = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for product in products:
            try:
                # Generate product hash for deduplication
                product_hash = self._generate_product_hash(product)
                
                # Check if product already exists
                if product_hash in self.product_index:
                    duplicate_count += 1
                    logger.debug(f"Duplicate product found: {product.product_name}")
                    continue
                
                # Store the product
                file_path = self._store_single_product(product, collection_batch)
                self.product_index[product_hash] = str(file_path)
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Failed to store product {product.product_name}: {str(e)}")
                error_count += 1
        
        # Update index file
        self._update_index()
        
        result = {
            "stored": stored_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "batch_id": collection_batch
        }
        
        logger.info(f"Storage completed: {stored_count} stored, {duplicate_count} duplicates, {error_count} errors")
        return result
    
    def get_products(
        self, 
        lender: Optional[str] = None,
        rate_type: Optional[str] = None,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[LoanProduct]:
        """Retrieve products with optional filtering."""
        all_products = self._load_all_products()
        
        # Apply filters
        filtered_products = []
        for product in all_products:
            if lender and product.lender.lower() != lender.lower():
                continue
            if rate_type and product.rate_type.lower() != rate_type.lower():
                continue
            if min_rate and float(product.rate_percent) < min_rate:
                continue
            if max_rate and float(product.rate_percent) > max_rate:
                continue
            
            filtered_products.append(product)
        
        # Apply limit
        if limit:
            filtered_products = filtered_products[:limit]
        
        return filtered_products
    
    def get_product_changes(self, days: int = 7) -> Dict[str, Any]:
        """Get products that have changed in the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_products = []
        
        for product in self._load_all_products():
            if product.collected_at >= cutoff_date:
                recent_products.append(product)
        
        return {
            "period_days": days,
            "products_changed": len(recent_products),
            "products": [self._product_to_dict(p) for p in recent_products]
        }
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        all_products = self._load_all_products()
        
        # Group by lender
        lender_counts = {}
        for product in all_products:
            lender_counts[product.lender] = lender_counts.get(product.lender, 0) + 1
        
        # Group by rate type
        rate_type_counts = {}
        for product in all_products:
            rate_type_counts[product.rate_type] = rate_type_counts.get(product.rate_type, 0) + 1
        
        return {
            "total_products": len(all_products),
            "unique_products": len(self.product_index),
            "lender_breakdown": lender_counts,
            "rate_type_breakdown": rate_type_counts,
            "storage_path": str(self.storage_path),
            "index_size": len(self.product_index)
        }
    
    def _generate_product_hash(self, product: LoanProduct) -> str:
        """Generate a hash for product deduplication."""
        # Create a unique identifier based on key product attributes
        key_attributes = f"{product.lender}|{product.product_name}|{product.rate_percent}|{product.rate_type}"
        return hashlib.md5(key_attributes.encode()).hexdigest()
    
    def _store_single_product(self, product: LoanProduct, batch_id: str) -> Path:
        """Store a single product to file."""
        # Create batch directory
        batch_dir = self.storage_path / batch_id
        batch_dir.mkdir(exist_ok=True)
        
        # Generate filename
        safe_name = "".join(c for c in product.product_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')[:50]  # Limit length
        filename = f"{product.lender}_{safe_name}_{product.rate_percent}.json"
        
        file_path = batch_dir / filename
        
        # Convert product to dict and save
        product_dict = self._product_to_dict(product)
        with open(file_path, 'w') as f:
            json.dump(product_dict, f, indent=2, default=str)
        
        return file_path
    
    def _product_to_dict(self, product: LoanProduct) -> Dict[str, Any]:
        """Convert LoanProduct to dictionary for JSON serialization."""
        return {
            "lender": product.lender,
            "product_name": product.product_name,
            "rate_percent": float(product.rate_percent),
            "comparison_rate_percent": float(product.comparison_rate_percent),
            "term_months": product.term_months,
            "rate_type": product.rate_type,
            "fees_breakdown": product.fees_breakdown,
            "features": product.features,
            "lvr_max": float(product.lvr_max),
            "dti_max": float(product.dti_max) if product.dti_max else None,
            "postcode_flags": product.postcode_flags,
            "source_url": product.source_url,
            "collected_at": product.collected_at.isoformat()
        }
    
    def _load_all_products(self) -> List[LoanProduct]:
        """Load all products from storage."""
        products = []
        
        for file_path in self.storage_path.rglob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    product_dict = json.load(f)
                
                # Convert back to LoanProduct
                product = self._dict_to_product(product_dict)
                if product:
                    products.append(product)
            except Exception as e:
                logger.error(f"Failed to load product from {file_path}: {str(e)}")
                continue
        
        return products
    
    def _dict_to_product(self, product_dict: Dict[str, Any]) -> Optional[LoanProduct]:
        """Convert dictionary back to LoanProduct object."""
        try:
            from decimal import Decimal
            
            return LoanProduct(
                lender=product_dict["lender"],
                product_name=product_dict["product_name"],
                rate_percent=Decimal(str(product_dict["rate_percent"])),
                comparison_rate_percent=Decimal(str(product_dict["comparison_rate_percent"])),
                term_months=product_dict["term_months"],
                rate_type=product_dict["rate_type"],
                fees_breakdown=product_dict["fees_breakdown"],
                features=product_dict["features"],
                lvr_max=Decimal(str(product_dict["lvr_max"])),
                dti_max=Decimal(str(product_dict["dti_max"])) if product_dict.get("dti_max") else None,
                postcode_flags=product_dict["postcode_flags"],
                source_url=product_dict["source_url"],
                collected_at=datetime.fromisoformat(product_dict["collected_at"])
            )
        except Exception as e:
            logger.error(f"Failed to convert dict to product: {str(e)}")
            return None
    
    def _update_index(self):
        """Update the product index file."""
        index_file = self.storage_path / "index.json"
        with open(index_file, 'w') as f:
            json.dump(self.product_index, f, indent=2)
    
    def load_existing_products(self):
        """Load existing product index on startup."""
        index_file = self.storage_path / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    self.product_index = json.load(f)
                logger.info(f"Loaded {len(self.product_index)} existing products from index")
            except Exception as e:
                logger.error(f"Failed to load product index: {str(e)}")
                self.product_index = {}
        else:
            self.product_index = {}
    
    async def save_current_products(
        self, 
        products: List[LoanProduct], 
        lender: Optional[str] = None,
        schema_version: str = "2.0.0"
    ) -> str:
        """
        Save current products to JSON file with specified schema version.
        
        Args:
            products: List of loan products to save
            lender: If provided, saves to lender-specific file
            schema_version: Schema version to use:
                - "2.0.0": State-explicit format (default) - explicit pricing_states array
                - "1.0.0": Hierarchical format - nested loan_types → repayment_types
            
        Returns:
            Path to saved file
        """
        from pathlib import Path
        import aiofiles
        
        # Use data/current structure like JSONStorageService
        base_path = Path("data")
        current_dir = base_path / "current" / "by_lender"
        current_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert products based on schema version
        if schema_version == "2.0.0":
            # v2.0.0: State-explicit format with pricing_states array
            products_data = [p.to_state_explicit_json() for p in products]
            format_name = "state-explicit"
        else:
            # v1.0.0: Hierarchical format (backward compatibility)
            products_data = [p.to_hierarchical_json() for p in products]
            format_name = "hierarchical"
        
        if lender:
            file_path = current_dir / f"{lender}.json"
        else:
            file_path = base_path / "current" / "products.json"
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(products_data, indent=2, default=str))
        
        logger.info(f"Saved {len(products_data)} products in {format_name} format (v{schema_version}) to {file_path}")
        return str(file_path)
    
    async def save_snapshot(
        self, 
        products: List[LoanProduct], 
        lender: str,
        raw_html: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Save historical snapshot of products (compatible with JSONStorageService interface).
        
        Args:
            products: List of loan products
            lender: Lender name
            raw_html: Optional dict of {url: html_content} for raw snapshots
            
        Returns:
            Dict with paths to saved files
        """
        from pathlib import Path
        import aiofiles
        
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        saved_files = {}
        base_path = Path("data")
        
        # Save parsed products
        parsed_dir = base_path / "snapshots" / "parsed" / lender
        parsed_dir.mkdir(parents=True, exist_ok=True)
        parsed_file = parsed_dir / f"{timestamp}.json"
        
        products_data = [p.model_dump() for p in products]
        async with aiofiles.open(parsed_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(products_data, indent=2, default=str))
        saved_files['parsed'] = str(parsed_file)
        
        # Save raw HTML if provided
        if raw_html:
            raw_dir = base_path / "snapshots" / "raw" / lender / timestamp
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            for i, (url, html_content) in enumerate(raw_html.items(), 1):
                raw_file = raw_dir / f"page{i}.html"
                async with aiofiles.open(raw_file, 'w', encoding='utf-8') as f:
                    await f.write(html_content)
                saved_files[f'raw_page{i}'] = str(raw_file)
        
        return saved_files
    
    async def update_index(
        self,
        lender: str,
        status: str,
        products_count: int,
        snapshot_path: str
    ) -> None:
        """
        Update the index.json catalog file (compatible with JSONStorageService interface).
        
        Args:
            lender: Lender name
            status: Collection status (success/failure)
            products_count: Number of products collected
            snapshot_path: Path to snapshot file
        """
        from pathlib import Path
        import aiofiles
        
        index_file = Path("data") / "index.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing index
        index_data = {}
        if index_file.exists():
            async with aiofiles.open(index_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    index_data = json.loads(content)
        
        # Update index with new collection entry
        index_data[lender] = {
            "status": status,
            "products_count": products_count,
            "snapshot_path": snapshot_path,
            "last_updated": datetime.now().isoformat()
        }
        
        # Save updated index
        async with aiofiles.open(index_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(index_data, indent=2, default=str))
