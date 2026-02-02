"""Cart API routes for mock merchant"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

from ..models.cart import (
    Cart,
    AddToCartRequest,
    UpdateCartItemRequest,
    CartResponse,
)
from ..database.carts import cart_db
from ..database.products import product_db
from ..security.tap_middleware import optional_tap
from tap.models import VerificationResult

router = APIRouter(prefix="/api/cart", tags=["Cart"])


def get_cart_id(x_cart_id: Optional[str] = Header(None)) -> Optional[str]:
    """Extract cart ID from header"""
    return x_cart_id


@router.post("", response_model=CartResponse)
async def create_cart():
    """Create a new shopping cart"""
    cart = cart_db.create_cart()
    return CartResponse(cart=cart, message="Cart created")


@router.get("/{cart_id}", response_model=CartResponse)
async def get_cart(
    cart_id: str,
    tap: VerificationResult = Depends(optional_tap),
):
    """Get cart by ID"""
    cart = cart_db.get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return CartResponse(cart=cart)


@router.post("/{cart_id}/items", response_model=CartResponse)
async def add_to_cart(
    cart_id: str,
    request: AddToCartRequest,
    tap: VerificationResult = Depends(optional_tap),
):
    """Add an item to the cart"""
    # Verify cart exists
    cart = cart_db.get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    # Verify product exists and is in stock
    product = product_db.get_product(request.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if not product.in_stock or product.stock_quantity < request.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Available: {product.stock_quantity}",
        )

    # Add to cart
    updated_cart = cart_db.add_item(cart_id, product, request.quantity)
    return CartResponse(
        cart=updated_cart,
        message=f"Added {request.quantity}x {product.name} to cart",
    )


@router.put("/{cart_id}/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    cart_id: str,
    product_id: str,
    request: UpdateCartItemRequest,
    tap: VerificationResult = Depends(optional_tap),
):
    """Update item quantity in cart"""
    cart = cart_db.get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    # Verify product exists
    product = product_db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check stock
    if request.quantity > product.stock_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Available: {product.stock_quantity}",
        )

    updated_cart = cart_db.update_item_quantity(cart_id, product_id, request.quantity)
    if not updated_cart:
        raise HTTPException(status_code=404, detail="Item not in cart")

    return CartResponse(cart=updated_cart, message="Cart updated")


@router.delete("/{cart_id}/items/{product_id}", response_model=CartResponse)
async def remove_from_cart(
    cart_id: str,
    product_id: str,
    tap: VerificationResult = Depends(optional_tap),
):
    """Remove an item from the cart"""
    cart = cart_db.get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    updated_cart = cart_db.remove_item(cart_id, product_id)
    return CartResponse(cart=updated_cart, message="Item removed")


@router.delete("/{cart_id}", response_model=CartResponse)
async def clear_cart(
    cart_id: str,
    tap: VerificationResult = Depends(optional_tap),
):
    """Clear all items from cart"""
    cart = cart_db.get_cart(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    updated_cart = cart_db.clear_cart(cart_id)
    return CartResponse(cart=updated_cart, message="Cart cleared")
