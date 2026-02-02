"""
Agent Service Application

AI-powered shopping assistant for Visa agentic commerce testing.
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

from .routes import chat_router, auth_router
from .core.config import settings

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env"))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Shopping Agent starting up...")
    logger.info(f"Merchant URL: {settings.merchant_base_url}")
    logger.info(f"Visa API configured: {settings.visa_credentials_configured}")

    yield

    logger.info("Shopping Agent shutting down...")
    # Cleanup merchant client
    from .routes.chat import merchant_client
    if merchant_client:
        await merchant_client.close()


# Create FastAPI app
app = FastAPI(
    title="Shopping Agent",
    description="AI-powered shopping assistant for Visa agentic commerce",
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

# Static files and templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir) if os.path.exists(templates_dir) else None

# Include routers
app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/")
async def home(request: Request):
    """Agent chat UI"""
    if templates:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": settings.app_name,
                "merchant_url": settings.merchant_base_url,
            },
        )
    return {
        "message": "Shopping Agent API",
        "docs": "/docs",
        "endpoints": {
            "chat": "/api/chat",
            "auth": "/api/auth",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "shopping-agent",
        "merchant_configured": bool(settings.merchant_base_url),
        "visa_configured": settings.visa_credentials_configured,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
