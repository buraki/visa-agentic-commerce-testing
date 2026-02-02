"""Order storage for mock merchant"""

import uuid
from datetime import datetime
from typing import Optional

from ..models.checkout import Order, OrderItem, OrderStatus, ShippingAddress, PaymentMethod
from ..models.cart import Cart


class OrderDatabase:
    """In-memory order storage"""

    def __init__(self):
        self.orders: dict[str, Order] = {}

    def create_order(
        self,
        cart: Cart,
        shipping_address: ShippingAddress,
        payment_method: PaymentMethod,
        payment_last_four: Optional[str] = None,
    ) -> Order:
        """Create an order from a cart"""
        now = datetime.utcnow()

        # Convert cart items to order items
        order_items = [
            OrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                sku=item.product_id,  # Would normally come from product
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
            )
            for item in cart.items
        ]

        order = Order(
            order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            status=OrderStatus.COMPLETED,
            items=order_items,
            subtotal=cart.subtotal,
            tax=cart.tax,
            total=cart.total,
            currency=cart.currency,
            shipping_address=shipping_address,
            payment_method=payment_method,
            payment_last_four=payment_last_four,
            created_at=now,
            updated_at=now,
        )

        self.orders[order.order_id] = order
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID"""
        return self.orders.get(order_id)

    def update_status(self, order_id: str, status: OrderStatus) -> Optional[Order]:
        """Update order status"""
        order = self.get_order(order_id)
        if not order:
            return None

        order.status = status
        order.updated_at = datetime.utcnow()
        return order

    def list_orders(self, limit: int = 50) -> list[Order]:
        """List recent orders"""
        orders = list(self.orders.values())
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders[:limit]


# Singleton instance
order_db = OrderDatabase()
