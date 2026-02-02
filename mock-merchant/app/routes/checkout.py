"""Checkout API routes for mock merchant"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from ..models.checkout import (
    CheckoutRequest,
    CheckoutResponse,
    Order,
    OrderStatus,
    PaymentMethod,
)
from ..database.carts import cart_db
from ..database.orders import order_db
from ..database.products import product_db
from ..security.tap_middleware import require_checkout, optional_tap
from tap.models import VerificationResult, InteractionType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checkout", tags=["Checkout"])


@router.post("", response_model=CheckoutResponse)
async def checkout(
    request: CheckoutRequest,
    tap: VerificationResult = Depends(optional_tap),
):
    """
    Process checkout.

    For agent requests with Visa tokenized credentials:
    - TAP signature with 'checkout' tag is required
    - Payment uses Visa token

    For regular user requests:
    - No TAP signature needed
    - Would typically redirect to payment form
    """
    # Get cart
    cart = cart_db.get_cart(request.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Determine if this is an agent checkout
    is_agent_checkout = tap.is_valid and tap.interaction_type == InteractionType.CHECKOUT

    # Validate payment based on request type
    if request.payment.method == PaymentMethod.VISA_TOKEN:
        if not is_agent_checkout:
            raise HTTPException(
                status_code=403,
                detail="Visa token payments require TAP checkout signature",
            )

        if not request.payment.token:
            raise HTTPException(
                status_code=400,
                detail="Visa token is required for tokenized payment",
            )

        # In production, would validate the token with Visa
        # For mock, we just accept it
        logger.info(
            f"Processing Visa token payment for agent {tap.agent_id}, "
            f"instruction_id={request.instruction_id}"
        )

    # Check stock availability and reserve
    for item in cart.items:
        product = product_db.get_product(item.product_id)
        if not product or product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {item.product_name}",
            )

    # Process payment (mock - always succeeds)
    payment_success = True

    if not payment_success:
        return CheckoutResponse(
            success=False,
            error_message="Payment processing failed",
        )

    # Update stock
    for item in cart.items:
        product_db.update_stock(item.product_id, -item.quantity)

    # Create order
    payment_last_four = None
    if request.payment.token:
        # Extract last 4 from token (mock)
        payment_last_four = request.payment.token[-4:] if len(request.payment.token) >= 4 else "****"

    order = order_db.create_order(
        cart=cart,
        shipping_address=request.shipping_address,
        payment_method=request.payment.method,
        payment_last_four=payment_last_four,
    )

    # Clear the cart after successful checkout
    cart_db.delete_cart(request.cart_id)

    logger.info(
        f"Order {order.order_id} created: ${order.total} - "
        f"{'agent' if is_agent_checkout else 'user'} checkout"
    )

    return CheckoutResponse(
        success=True,
        order=order,
    )


@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    tap: VerificationResult = Depends(optional_tap),
):
    """Get order details"""
    order = order_db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/orders", response_model=list[Order])
async def list_orders(
    limit: int = 50,
    tap: VerificationResult = Depends(optional_tap),
):
    """List recent orders"""
    return order_db.list_orders(limit=limit)
