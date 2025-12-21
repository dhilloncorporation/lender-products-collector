"""
API Agent - REST API Exposure

ROLE: Worker Agent (API Service)
PURPOSE: Exposes collected loan product data via REST API endpoints

This agent provides a FastAPI-based REST API for accessing collected loan
product data. It integrates with Storage Agent and Monitoring Agent to serve
data and provide system health information.

API ENDPOINTS:
- GET /products - Get all products (with filters)
- GET /products/{lender} - Get products by lender
- GET /stats - Get collection statistics
- GET /health - Health check endpoint
- GET /changes - Get recent product changes

FEATURES:
- RESTful API design
- Query parameter filtering (lender, rate_type, min_rate, max_rate)
- Integration with Storage Agent for data access
- Integration with Monitoring Agent for statistics
- Error handling and validation
- FastAPI automatic documentation

DEPENDENCIES:
- FastAPI (web framework)
- Storage Agent (ProductStorageAgent)
- Monitoring Agent (CollectionMonitorAgent)
- LoanProduct models

USAGE:
    storage_agent = ProductStorageAgent()
    monitor_agent = CollectionMonitorAgent()
    api_agent = ProductAPIAgent(storage_agent, monitor_agent)
    # Include router in FastAPI app: app.include_router(api_agent.router)
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from ...models import LoanProduct
from ..storage.product_storage import ProductStorageAgent
from ..monitoring.collection_monitor import CollectionMonitorAgent

logger = logging.getLogger(__name__)


class ProductAPIAgent:
    """
    Product API agent for serving collected data via REST API.
    
    This agent creates FastAPI routes to expose loan product data to external
    systems. It provides endpoints for querying products, getting statistics,
    and checking system health.
    
    Attributes:
        storage_agent: Storage agent for accessing product data
        monitor_agent: Monitoring agent for statistics and health checks
        router: FastAPI router with all API endpoints
    
    Endpoints:
        GET /products - List all products (with optional filters)
        GET /products/{lender} - Get products for specific lender
        GET /stats - Get collection statistics
        GET /health - Health check endpoint
        GET /changes - Get recent product changes
    
    Example:
        >>> storage = ProductStorageAgent()
        >>> monitor = CollectionMonitorAgent()
        >>> api = ProductAPIAgent(storage, monitor)
        >>> app.include_router(api.router, prefix="/api/v1")
    """
    
    def __init__(self, storage_agent: ProductStorageAgent, monitor_agent: CollectionMonitorAgent):
        self.storage_agent = storage_agent
        self.monitor_agent = monitor_agent
        self.router = APIRouter()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.router.get("/products", response_model=List[LoanProduct])
        async def get_products(
            lender: Optional[str] = Query(None, description="Filter by lender"),
            rate_type: Optional[str] = Query(None, description="Filter by rate type"),
            min_rate: Optional[float] = Query(None, description="Minimum interest rate"),
            max_rate: Optional[float] = Query(None, description="Maximum interest rate"),
            limit: Optional[int] = Query(100, description="Maximum number of products to return")
        ):
            """Get loan products with optional filtering."""
            try:
                products = self.storage_agent.get_products(
                    lender=lender,
                    rate_type=rate_type,
                    min_rate=min_rate,
                    max_rate=max_rate,
                    limit=limit
                )
                
                # Log API usage
                self.monitor_agent.log_collection_start("api_request", "product_query")
                
                return products
                
            except Exception as e:
                logger.error(f"Failed to get products: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/products/{lender}", response_model=List[LoanProduct])
        async def get_products_by_lender(
            lender: str,
            limit: Optional[int] = Query(50, description="Maximum number of products to return")
        ):
            """Get products by specific lender."""
            try:
                products = self.storage_agent.get_products(lender=lender, limit=limit)
                
                if not products:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No products found for lender: {lender}"
                    )
                
                return products
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get products for lender {lender}: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/products/stats", response_model=Dict[str, Any])
        async def get_product_stats():
            """Get product collection statistics."""
            try:
                stats = self.storage_agent.get_storage_stats()
                return stats
                
            except Exception as e:
                logger.error(f"Failed to get product stats: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/products/changes", response_model=Dict[str, Any])
        async def get_recent_changes(
            days: int = Query(7, description="Number of days to look back for changes")
        ):
            """Get products that have changed in the last N days."""
            try:
                changes = self.storage_agent.get_product_changes(days=days)
                return changes
                
            except Exception as e:
                logger.error(f"Failed to get recent changes: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/health", response_model=Dict[str, Any])
        async def health_check():
            """Get system health status."""
            try:
                health = self.monitor_agent.get_system_health()
                return health
                
            except Exception as e:
                logger.error(f"Failed to get health status: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/monitoring/stats", response_model=Dict[str, Any])
        async def get_monitoring_stats(
            hours: int = Query(24, description="Number of hours to look back")
        ):
            """Get collection monitoring statistics."""
            try:
                stats = self.monitor_agent.get_collection_stats(hours=hours)
                return stats
                
            except Exception as e:
                logger.error(f"Failed to get monitoring stats: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def get_router(self) -> APIRouter:
        """Get the FastAPI router for this agent."""
        return self.router
