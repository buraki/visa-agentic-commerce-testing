"""
Mock Merchant Application

A simulated e-commerce site for testing Visa agentic commerce APIs.
Supports TAP (Trusted Agent Protocol) signature verification.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from .routes import products_router, cart_router, checkout_router
from .security.tap_middleware import TAPVerificationMiddleware, get_tap_verifier

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Mock Merchant starting up...")
    logger.info(f"TAP verification: {'enabled' if os.getenv('TAP_AGENT_PUBLIC_KEY') else 'disabled'}")
    yield
    logger.info("Mock Merchant shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Mock Merchant",
    description="Simulated e-commerce site for Visa agentic commerce testing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TAP verification middleware
tap_verifier = get_tap_verifier()
app.add_middleware(TAPVerificationMiddleware, verifier=tap_verifier)

# Static files and templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir) if os.path.exists(templates_dir) else None

# Include API routers
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(checkout_router)


@app.get("/")
async def home(request: Request):
    """Merchant storefront home page"""
    if templates:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "title": "Mock Merchant Store"},
        )
    return {
        "message": "Mock Merchant API",
        "docs": "/docs",
        "endpoints": {
            "products": "/api/products",
            "cart": "/api/cart",
            "checkout": "/api/checkout",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock-merchant"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
