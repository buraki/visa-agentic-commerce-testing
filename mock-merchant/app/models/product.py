"""Product models for mock merchant"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    HOME = "home"
    SPORTS = "sports"
    BOOKS = "books"


class Product(BaseModel):
    """Product in the catalog"""
    id: str
    name: str
    description: str
    price: float = Field(gt=0)
    currency: str = "USD"
    category: ProductCategory
    sku: str
    image_url: Optional[str] = None
    in_stock: bool = True
    stock_quantity: int = Field(ge=0, default=100)

    class Config:
        from_attributes = True


class ProductSearchRequest(BaseModel):
    """Request to search products"""
    query: Optional[str] = None
    category: Optional[ProductCategory] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock_only: bool = True
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


class ProductSearchResponse(BaseModel):
    """Response from product search"""
    products: list[Product]
    total: int
    limit: int
    offset: int
