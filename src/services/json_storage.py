"""JSON file storage service for loan product data."""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from aiofiles import open as aio_open

from ..models import LoanProduct


class JSONStorageService:
    """Service for storing and retrieving loan product data in JSON format."""
    
    def __init__(self, base_path: str = "data"):
        """Initialize storage service with base directory path."""
        self.base_path = Path(base_path)
        self._ensure_directory_structure()
    
    def _ensure_directory_structure(self) -> None:
        """Create required directory structure if it doesn't exist."""
        directories = [
            self.base_path / "current",
            self.base_path / "current" / "by_lender",
            self.base_path / "snapshots" / "raw",
            self.base_path / "snapshots" / "parsed",
            self.base_path / "diffs",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def save_current_products(
        self, 
        products: List[LoanProduct], 
        lender: Optional[str] = None
    ) -> str:
        """
        Save current products to JSON file.
        
        Args:
            products: List of loan products to save
            lender: If provided, saves to lender-specific file
            
        Returns:
            Path to saved file
        """
        # Convert products to dict
        products_data = [p.model_dump() for p in products]
        
        if lender:
            # Save to lender-specific file
            file_path = self.base_path / "current" / "by_lender" / f"{lender}.json"
        else:
            # Save to main products file
            file_path = self.base_path / "current" / "products.json"
        
        async with aio_open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(products_data, indent=2, default=str))
        
        return str(file_path)
    
    async def save_snapshot(
        self, 
        products: List[LoanProduct], 
        lender: str,
        raw_html: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Save historical snapshot of products.
        
        Args:
            products: List of loan products
            lender: Lender name
            raw_html: Optional dict of {url: html_content} for raw snapshots
            
        Returns:
            Dict with paths to saved files
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        saved_files = {}
        
        # Save parsed products
        parsed_dir = self.base_path / "snapshots" / "parsed" / lender
        parsed_dir.mkdir(parents=True, exist_ok=True)
        parsed_file = parsed_dir / f"{timestamp}.json"
        
        products_data = [p.model_dump() for p in products]
        async with aio_open(parsed_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(products_data, indent=2, default=str))
        saved_files['parsed'] = str(parsed_file)
        
        # Save raw HTML if provided
        if raw_html:
            raw_dir = self.base_path / "snapshots" / "raw" / lender / timestamp
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            for i, (url, html_content) in enumerate(raw_html.items(), 1):
                raw_file = raw_dir / f"page{i}.html"
                async with aio_open(raw_file, 'w', encoding='utf-8') as f:
                    await f.write(html_content)
                saved_files[f'raw_page{i}'] = str(raw_file)
        
        return saved_files
    
    async def load_current_products(
        self, 
        lender: Optional[str] = None
    ) -> List[LoanProduct]:
        """
        Load current products from JSON file.
        
        Args:
            lender: If provided, loads lender-specific file
            
        Returns:
            List of loan products
        """
        if lender:
            file_path = self.base_path / "current" / "by_lender" / f"{lender}.json"
        else:
            file_path = self.base_path / "current" / "products.json"
        
        if not file_path.exists():
            return []
        
        async with aio_open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            products_data = json.loads(content)
        
        return [LoanProduct(**p) for p in products_data]
    
    async def update_index(
        self,
        lender: str,
        status: str,
        products_count: int,
        snapshot_path: str
    ) -> None:
        """
        Update the index.json catalog file.
        
        Args:
            lender: Lender name
            status: Collection status (success/failure)
            products_count: Number of products collected
            snapshot_path: Path to snapshot file
        """
        index_file = self.base_path / "index.json"
        
        # Load existing index or create new one
        if index_file.exists():
            async with aio_open(index_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                index_data = json.loads(content)
        else:
            index_data = {
                "last_updated": None,
                "collections": [],
                "lenders": {}
            }
        
        # Add new collection entry
        timestamp = datetime.now().isoformat()
        collection_entry = {
            "id": f"col_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": timestamp,
            "lender": lender,
            "status": status,
            "products_found": products_count,
            "snapshot_path": snapshot_path
        }
        index_data["collections"].append(collection_entry)
        
        # Update lender info
        if status == "success":
            index_data["lenders"][lender] = {
                "last_collected": timestamp,
                "total_products": products_count,
                "current_file": f"data/current/by_lender/{lender}.json"
            }
        
        index_data["last_updated"] = timestamp
        
        # Save updated index
        async with aio_open(index_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(index_data, indent=2, default=str))
    
    async def get_index(self) -> Dict[str, Any]:
        """Get the current index data."""
        index_file = self.base_path / "index.json"
        
        if not index_file.exists():
            return {
                "last_updated": None,
                "collections": [],
                "lenders": {}
            }
        
        async with aio_open(index_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
