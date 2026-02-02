"""Cart models for mock merchant"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CartItem(BaseModel):
    """Item in a shopping cart"""
    product_id: str
    product_name: str
    quantity: int = Field(gt=0)
    unit_price: float
    total_price: float


class Cart(BaseModel):
    """Shopping cart"""
    cart_id: str
    items: list[CartItem] = []
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    created_at: datetime
    updated_at: datetime


class AddToCartRequest(BaseModel):
    """Request to add item to cart"""
    product_id: str
    quantity: int = Field(default=1, gt=0)


class UpdateCartItemRequest(BaseModel):
    """Request to update cart item quantity"""
    quantity: int = Field(gt=0)


class CartResponse(BaseModel):
    """Cart API response"""
    cart: Cart
    message: Optional[str] = None
