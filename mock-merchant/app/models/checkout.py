"""Checkout models for mock merchant"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    VISA_TOKEN = "visa_token"
    CREDIT_CARD = "credit_card"


class ShippingAddress(BaseModel):
    """Shipping address for order"""
    name: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"


class PaymentDetails(BaseModel):
    """Payment details for checkout"""
    method: PaymentMethod = PaymentMethod.VISA_TOKEN
    # For Visa tokenized credentials
    token: Optional[str] = None
    expiry_month: Optional[str] = None
    expiry_year: Optional[str] = None
    cvv: Optional[str] = None
    cardholder_name: Optional[str] = None


class CheckoutRequest(BaseModel):
    """Request to checkout"""
    cart_id: str
    shipping_address: ShippingAddress
    payment: PaymentDetails
    # For agents - the Visa instruction ID
    instruction_id: Optional[str] = None


class OrderItem(BaseModel):
    """Item in an order"""
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit_price: float
    total_price: float


class Order(BaseModel):
    """Completed order"""
    order_id: str
    status: OrderStatus
    items: list[OrderItem]
    subtotal: float
    tax: float
    total: float
    currency: str = "USD"
    shipping_address: ShippingAddress
    payment_method: PaymentMethod
    payment_last_four: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CheckoutResponse(BaseModel):
    """Response from checkout"""
    success: bool
    order: Optional[Order] = None
    error_message: Optional[str] = None
