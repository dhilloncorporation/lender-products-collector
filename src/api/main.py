"""FastAPI application for loan product data collection."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import products, matches

app = FastAPI(
    title="Lender Products Collector API",
    description="Collect and serve loan product data from lenders",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Lender Products Collector API is running"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "collector": "operational",
            "scheduler": "operational"
        }
    }
