"""Product API routes for mock merchant"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from ..models.product import (
    Product,
    ProductCategory,
    ProductSearchRequest,
    ProductSearchResponse,
)
from ..database.products import product_db
from ..security.tap_middleware import optional_tap, TAPDependency
from tap.models import VerificationResult

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("", response_model=ProductSearchResponse)
async def search_products(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[ProductCategory] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    in_stock_only: bool = Query(True, description="Only show in-stock items"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    tap: VerificationResult = Depends(optional_tap),
):
    """
    Search products in the catalog.

    Accepts TAP signatures but doesn't require them.
    Agent requests will be logged with their identity.
    """
    products, total = product_db.search_products(
        query=query,
        category=category,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        limit=limit,
        offset=offset,
    )

    return ProductSearchResponse(
        products=products,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categories", response_model=list[str])
async def list_categories():
    """List all product categories"""
    return [c.value for c in ProductCategory]


@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: str,
    tap: VerificationResult = Depends(optional_tap),
):
    """
    Get a product by ID.

    Accepts TAP signatures but doesn't require them.
    """
    product = product_db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/category/{category}", response_model=ProductSearchResponse)
async def get_products_by_category(
    category: ProductCategory,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tap: VerificationResult = Depends(optional_tap),
):
    """Get products in a specific category"""
    products, total = product_db.search_products(
        category=category,
        limit=limit,
        offset=offset,
    )

    return ProductSearchResponse(
        products=products,
        total=total,
        limit=limit,
        offset=offset,
    )
