"""
Shopping Agent

AI-powered shopping assistant that:
1. Understands user intent through conversation
2. Searches merchant catalogs
3. Manages shopping carts
4. Handles Visa card enrollment and payment
"""

import os
import sys
import logging
import json
from typing import Optional, Any
from dataclasses import dataclass

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))

from ..core.config import settings
from ..core.session import UserSession, SessionState
from .merchant_client import MerchantClient

# Import MCP client if available
try:
    from mcp.client import VisaMCPClient
    from mcp.models import (
        CardEnrollmentRequest,
        PurchaseInstruction,
        PurchaseItem,
        CommerceSignal,
        TransactionStatus,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the shopping agent"""
    message: str
    action_type: Optional[str] = None  # e.g., "search", "add_to_cart", "checkout"
    data: Optional[dict] = None  # Additional data (products, cart, etc.)
    requires_user_action: bool = False  # If user needs to do something
    action_url: Optional[str] = None  # URL for user action (e.g., Passkey auth)


class ShoppingAgent:
    """
    AI Shopping Assistant

    Processes user messages and orchestrates shopping workflows.
    """

    def __init__(
        self,
        merchant_client: MerchantClient,
        visa_client: Optional[Any] = None,  # VisaMCPClient if available
    ):
        self.merchant = merchant_client
        self.visa = visa_client
        self._tools = self._define_tools()

    def _define_tools(self) -> list[dict]:
        """Define available tools for the agent"""
        return [
            {
                "name": "search_products",
                "description": "Search for products in the merchant catalog",
                "parameters": {
                    "query": "Search query string",
                    "category": "Product category filter (optional)",
                    "max_price": "Maximum price filter (optional)",
                },
            },
            {
                "name": "get_product_details",
                "description": "Get detailed information about a specific product",
                "parameters": {
                    "product_id": "The product ID to look up",
                },
            },
            {
                "name": "add_to_cart",
                "description": "Add a product to the shopping cart",
                "parameters": {
                    "product_id": "The product ID to add",
                    "quantity": "Number of items to add (default 1)",
                },
            },
            {
                "name": "view_cart",
                "description": "View current shopping cart contents",
                "parameters": {},
            },
            {
                "name": "remove_from_cart",
                "description": "Remove a product from the cart",
                "parameters": {
                    "product_id": "The product ID to remove",
                },
            },
            {
                "name": "enroll_card",
                "description": "Start Visa card enrollment for payment",
                "parameters": {
                    "card_hint": "Last 4 digits of the card for display",
                },
            },
            {
                "name": "initiate_purchase",
                "description": "Start the purchase process for items in cart",
                "parameters": {},
            },
            {
                "name": "complete_checkout",
                "description": "Complete the checkout with payment",
                "parameters": {
                    "shipping_address": "Shipping address details",
                },
            },
        ]

    async def process_message(
        self,
        session: UserSession,
        user_message: str,
    ) -> AgentResponse:
        """
        Process a user message and return appropriate response.

        This is a simplified version - in production you'd use an LLM
        to understand intent and select appropriate actions.
        """
        # Add message to history
        session.add_message("user", user_message)

        message_lower = user_message.lower()

        try:
            # Simple intent matching (replace with LLM in production)
            if any(word in message_lower for word in ["search", "find", "looking for", "show me"]):
                response = await self._handle_search(session, user_message)

            elif any(word in message_lower for word in ["add to cart", "buy", "purchase", "get"]):
                response = await self._handle_add_to_cart(session, user_message)

            elif any(word in message_lower for word in ["cart", "basket", "what's in"]):
                response = await self._handle_view_cart(session)

            elif any(word in message_lower for word in ["remove", "delete"]):
                response = await self._handle_remove_from_cart(session, user_message)

            elif any(word in message_lower for word in ["checkout", "pay", "complete order"]):
                response = await self._handle_checkout(session, user_message)

            elif any(word in message_lower for word in ["enroll", "add card", "register card"]):
                response = await self._handle_card_enrollment(session, user_message)

            elif any(word in message_lower for word in ["help", "what can you do"]):
                response = self._handle_help()

            else:
                response = AgentResponse(
                    message="I can help you shop! Try:\n"
                    "- 'Search for headphones'\n"
                    "- 'Add [product] to cart'\n"
                    "- 'Show my cart'\n"
                    "- 'Checkout'\n"
                    "- 'Help' for more options",
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            response = AgentResponse(
                message=f"I encountered an error: {str(e)}. Please try again.",
            )

        # Add response to history
        session.add_message("assistant", response.message)

        return response

    async def _handle_search(
        self,
        session: UserSession,
        message: str,
    ) -> AgentResponse:
        """Handle product search requests"""
        session.update_state(SessionState.BROWSING)

        # Extract search query (simplified - use NLP in production)
        query = message.lower()
        for prefix in ["search for", "find", "looking for", "show me", "search"]:
            if prefix in query:
                query = query.split(prefix, 1)[1].strip()
                break

        # Search products
        results = await self.merchant.search_products(query=query, limit=5)
        products = results.get("products", [])

        if not products:
            return AgentResponse(
                message=f"I couldn't find any products matching '{query}'. Try a different search term.",
                action_type="search",
                data={"query": query, "products": []},
            )

        # Format product list
        product_list = "\n".join([
            f"• **{p['name']}** - ${p['price']:.2f} "
            f"({'In Stock' if p['in_stock'] else 'Out of Stock'})"
            for p in products
        ])

        return AgentResponse(
            message=f"I found {len(products)} products:\n\n{product_list}\n\n"
            "Would you like to add any of these to your cart?",
            action_type="search",
            data={"query": query, "products": products},
        )

    async def _handle_add_to_cart(
        self,
        session: UserSession,
        message: str,
    ) -> AgentResponse:
        """Handle add to cart requests"""
        session.update_state(SessionState.CART_MANAGEMENT)

        # Create cart if needed
        if not session.cart.cart_id:
            cart_response = await self.merchant.create_cart()
            session.cart.cart_id = cart_response["cart"]["cart_id"]

        # Try to find product (simplified - would use NLP/context in production)
        # For now, search for mentioned product
        search_results = await self.merchant.search_products(
            query=message.replace("add to cart", "").replace("buy", "").strip(),
            limit=1,
        )

        products = search_results.get("products", [])
        if not products:
            return AgentResponse(
                message="I couldn't find that product. Could you search for it first?",
            )

        product = products[0]

        # Add to cart
        cart_response = await self.merchant.add_to_cart(
            cart_id=session.cart.cart_id,
            product_id=product["id"],
            quantity=1,
        )

        cart = cart_response["cart"]
        session.cart.items = cart["items"]
        session.cart.total = cart["total"]

        return AgentResponse(
            message=f"Added **{product['name']}** to your cart!\n\n"
            f"Cart total: ${cart['total']:.2f}\n\n"
            "Say 'checkout' when you're ready to purchase.",
            action_type="add_to_cart",
            data={"product": product, "cart": cart},
        )

    async def _handle_view_cart(self, session: UserSession) -> AgentResponse:
        """Handle view cart requests"""
        if not session.cart.cart_id:
            return AgentResponse(
                message="Your cart is empty. Search for products to add!",
                action_type="view_cart",
                data={"cart": None},
            )

        cart_response = await self.merchant.get_cart(session.cart.cart_id)
        cart = cart_response["cart"]

        if not cart["items"]:
            return AgentResponse(
                message="Your cart is empty. Search for products to add!",
                action_type="view_cart",
                data={"cart": cart},
            )

        items_list = "\n".join([
            f"• {item['product_name']} x{item['quantity']} - ${item['total_price']:.2f}"
            for item in cart["items"]
        ])

        return AgentResponse(
            message=f"**Your Cart:**\n\n{items_list}\n\n"
            f"Subtotal: ${cart['subtotal']:.2f}\n"
            f"Tax: ${cart['tax']:.2f}\n"
            f"**Total: ${cart['total']:.2f}**\n\n"
            "Say 'checkout' to complete your purchase!",
            action_type="view_cart",
            data={"cart": cart},
        )

    async def _handle_remove_from_cart(
        self,
        session: UserSession,
        message: str,
    ) -> AgentResponse:
        """Handle remove from cart requests"""
        if not session.cart.cart_id or not session.cart.items:
            return AgentResponse(
                message="Your cart is already empty!",
            )

        # For simplicity, remove the first matching item
        # In production, use NLP to identify which item
        await self.merchant.remove_from_cart(
            cart_id=session.cart.cart_id,
            product_id=session.cart.items[0]["product_id"],
        )

        return await self._handle_view_cart(session)

    async def _handle_card_enrollment(
        self,
        session: UserSession,
        message: str,
    ) -> AgentResponse:
        """Handle Visa card enrollment"""
        if not self.visa:
            return AgentResponse(
                message="Visa integration is not configured. "
                "Please set up Visa API credentials.",
            )

        session.update_state(SessionState.ENROLLING_CARD)

        # Extract card hint (last 4 digits) from message
        # In production, use secure input form
        card_hint = "****"

        try:
            enrollment = await self.visa.enroll_card(
                CardEnrollmentRequest(
                    card_hint=card_hint,
                    return_url=settings.auth_callback_url,
                    agent_id=settings.tap_agent_id,
                )
            )

            session.payment.enrollment_id = enrollment.enrollment_id
            session.update_state(SessionState.AWAITING_AUTH)

            return AgentResponse(
                message="To securely add your card, please complete the verification:\n\n"
                "This will set up a Passkey for secure, password-free authentication.",
                action_type="enroll_card",
                requires_user_action=True,
                action_url=enrollment.auth_url,
                data={"enrollment_id": enrollment.enrollment_id},
            )

        except Exception as e:
            logger.error(f"Card enrollment failed: {e}")
            return AgentResponse(
                message=f"Card enrollment failed: {str(e)}. Please try again.",
            )

    async def _handle_checkout(
        self,
        session: UserSession,
        message: str,
    ) -> AgentResponse:
        """Handle checkout process"""
        if not session.cart.cart_id or not session.cart.items:
            return AgentResponse(
                message="Your cart is empty! Add some products first.",
            )

        session.update_state(SessionState.CHECKOUT)

        # Check if Visa is configured for tokenized payment
        if self.visa and session.payment.card_enrolled:
            return await self._handle_visa_checkout(session)

        # Fall back to simple checkout (mock payment)
        return await self._handle_simple_checkout(session)

    async def _handle_simple_checkout(
        self,
        session: UserSession,
    ) -> AgentResponse:
        """Handle checkout without Visa integration"""
        # Use mock address and payment
        shipping_address = {
            "name": "Test User",
            "street": "123 Test Street",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "US",
        }

        payment = {
            "method": "credit_card",
            "token": "mock_token_4242",
        }

        try:
            result = await self.merchant.checkout(
                cart_id=session.cart.cart_id,
                shipping_address=shipping_address,
                payment=payment,
            )

            if result.get("success"):
                order = result["order"]
                session.cart = type(session.cart)()  # Reset cart
                session.update_state(SessionState.COMPLETED)

                return AgentResponse(
                    message=f"Order placed successfully!\n\n"
                    f"**Order ID:** {order['order_id']}\n"
                    f"**Total:** ${order['total']:.2f}\n\n"
                    "Thank you for your purchase!",
                    action_type="checkout_complete",
                    data={"order": order},
                )
            else:
                return AgentResponse(
                    message=f"Checkout failed: {result.get('error_message', 'Unknown error')}",
                )

        except Exception as e:
            logger.error(f"Checkout failed: {e}")
            return AgentResponse(
                message=f"Checkout failed: {str(e)}",
            )

    async def _handle_visa_checkout(
        self,
        session: UserSession,
    ) -> AgentResponse:
        """Handle checkout with Visa tokenized credentials"""
        if not MCP_AVAILABLE or not self.visa:
            return await self._handle_simple_checkout(session)

        try:
            # Get cart for purchase details
            cart_response = await self.merchant.get_cart(session.cart.cart_id)
            cart = cart_response["cart"]

            # Create purchase instruction
            items = [
                PurchaseItem(
                    name=item["product_name"],
                    sku=item["product_id"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total_price=item["total_price"],
                )
                for item in cart["items"]
            ]

            instruction = await self.visa.initiate_purchase(
                PurchaseInstruction(
                    merchant_url=settings.merchant_base_url,
                    merchant_name=settings.merchant_name,
                    amount=cart["total"],
                    items=items,
                )
            )

            session.payment.instruction_id = instruction.instruction_id
            session.update_state(SessionState.AWAITING_AUTH)

            return AgentResponse(
                message=f"Please authenticate this purchase of ${cart['total']:.2f}:\n\n"
                "Use your Passkey to securely confirm this transaction.",
                action_type="authenticate_purchase",
                requires_user_action=True,
                action_url=instruction.auth_url,
                data={
                    "instruction_id": instruction.instruction_id,
                    "amount": cart["total"],
                },
            )

        except Exception as e:
            logger.error(f"Visa checkout failed: {e}")
            return AgentResponse(
                message=f"Visa checkout failed: {str(e)}. "
                "Would you like to try a different payment method?",
            )

    def _handle_help(self) -> AgentResponse:
        """Handle help requests"""
        return AgentResponse(
            message="**I'm your AI Shopping Assistant!**\n\n"
            "Here's what I can do:\n\n"
            "**Shopping:**\n"
            "• 'Search for [product]' - Find products\n"
            "• 'Add [product] to cart' - Add items\n"
            "• 'Show my cart' - View cart\n"
            "• 'Remove [product]' - Remove items\n\n"
            "**Payment:**\n"
            "• 'Add my Visa card' - Enroll for secure payment\n"
            "• 'Checkout' - Complete your purchase\n\n"
            "What would you like to do?",
        )
