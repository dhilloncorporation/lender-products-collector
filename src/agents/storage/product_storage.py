"""Product storage agent for handling data persistence and deduplication."""

import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path
from ...src.models import LoanProduct

logger = logging.getLogger(__name__)


class ProductStorageAgent:
    """Agent that handles product data storage, deduplication, and versioning."""
    
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
