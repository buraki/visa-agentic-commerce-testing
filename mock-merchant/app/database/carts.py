"""Cart storage for mock merchant"""

import uuid
from datetime import datetime
from typing import Optional

from ..models.cart import Cart, CartItem
from ..models.product import Product


class CartDatabase:
    """In-memory cart storage"""

    TAX_RATE = 0.0875  # 8.75% tax

    def __init__(self):
        self.carts: dict[str, Cart] = {}

    def create_cart(self) -> Cart:
        """Create a new cart"""
        now = datetime.utcnow()
        cart = Cart(
            cart_id=str(uuid.uuid4()),
            items=[],
            created_at=now,
            updated_at=now,
        )
        self.carts[cart.cart_id] = cart
        return cart

    def get_cart(self, cart_id: str) -> Optional[Cart]:
        """Get a cart by ID"""
        return self.carts.get(cart_id)

    def get_or_create_cart(self, cart_id: Optional[str] = None) -> Cart:
        """Get existing cart or create new one"""
        if cart_id and cart_id in self.carts:
            return self.carts[cart_id]
        return self.create_cart()

    def add_item(
        self,
        cart_id: str,
        product: Product,
        quantity: int = 1,
    ) -> Optional[Cart]:
        """Add an item to the cart"""
        cart = self.get_cart(cart_id)
        if not cart:
            return None

        # Check if product already in cart
        existing_item = next(
            (item for item in cart.items if item.product_id == product.id),
            None,
        )

        if existing_item:
            # Update quantity
            existing_item.quantity += quantity
            existing_item.total_price = existing_item.unit_price * existing_item.quantity
        else:
            # Add new item
            cart_item = CartItem(
                product_id=product.id,
                product_name=product.name,
                quantity=quantity,
                unit_price=product.price,
                total_price=product.price * quantity,
            )
            cart.items.append(cart_item)

        self._recalculate_totals(cart)
        return cart

    def update_item_quantity(
        self,
        cart_id: str,
        product_id: str,
        quantity: int,
    ) -> Optional[Cart]:
        """Update item quantity in cart"""
        cart = self.get_cart(cart_id)
        if not cart:
            return None

        item = next(
            (item for item in cart.items if item.product_id == product_id),
            None,
        )

        if not item:
            return None

        if quantity <= 0:
            # Remove item
            cart.items = [i for i in cart.items if i.product_id != product_id]
        else:
            item.quantity = quantity
            item.total_price = item.unit_price * quantity

        self._recalculate_totals(cart)
        return cart

    def remove_item(self, cart_id: str, product_id: str) -> Optional[Cart]:
        """Remove an item from the cart"""
        return self.update_item_quantity(cart_id, product_id, 0)

    def clear_cart(self, cart_id: str) -> Optional[Cart]:
        """Clear all items from cart"""
        cart = self.get_cart(cart_id)
        if not cart:
            return None

        cart.items = []
        self._recalculate_totals(cart)
        return cart

    def delete_cart(self, cart_id: str) -> bool:
        """Delete a cart"""
        if cart_id in self.carts:
            del self.carts[cart_id]
            return True
        return False

    def _recalculate_totals(self, cart: Cart) -> None:
        """Recalculate cart totals"""
        cart.subtotal = sum(item.total_price for item in cart.items)
        cart.tax = round(cart.subtotal * self.TAX_RATE, 2)
        cart.total = round(cart.subtotal + cart.tax, 2)
        cart.updated_at = datetime.utcnow()


# Singleton instance
cart_db = CartDatabase()
