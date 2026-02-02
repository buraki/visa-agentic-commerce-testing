"""
Merchant API Client

HTTP client for interacting with merchant APIs.
Includes TAP signature generation for authenticated requests.
"""

import os
import sys
import logging
from typing import Optional, Any

import httpx

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))

from tap.signer import TAPSigner
from tap.models import InteractionType, SignatureAlgorithm

logger = logging.getLogger(__name__)


class MerchantClient:
    """
    Client for interacting with merchant APIs.

    Generates TAP signatures for all requests to identify the agent.
    """

    def __init__(
        self,
        merchant_base_url: str,
        tap_private_key: Optional[str] = None,
        tap_keyid: str = "https://registry.visa.com/agents/shopping-agent",
        tap_algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519,
    ):
        """
        Initialize merchant client.

        Args:
            merchant_base_url: Base URL of merchant API
            tap_private_key: PEM-encoded private key for TAP signing
            tap_keyid: Agent's key identifier
            tap_algorithm: Signature algorithm to use
        """
        self.base_url = merchant_base_url.rstrip("/")
        self._http_client = httpx.AsyncClient(timeout=30.0)

        if tap_private_key:
            self._tap_signer = TAPSigner(
                private_key_pem=tap_private_key,
                keyid=tap_keyid,
                algorithm=tap_algorithm,
            )
            logger.info(f"TAP signer initialized with keyid: {tap_keyid}")
        else:
            self._tap_signer = None
            logger.warning("No TAP private key provided - requests will not be signed")

    async def close(self) -> None:
        """Close HTTP client"""
        await self._http_client.aclose()

    def _generate_headers(
        self,
        method: str,
        url: str,
        body: Optional[str] = None,
        interaction_type: InteractionType = InteractionType.BROWSING,
    ) -> dict[str, str]:
        """Generate headers including TAP signature if available"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self._tap_signer:
            signature = self._tap_signer.sign(
                method=method,
                url=url,
                body=body,
                interaction_type=interaction_type,
            )
            headers.update(signature.to_headers())
            logger.debug(f"Generated TAP signature for {method} {url}")

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        interaction_type: InteractionType = InteractionType.BROWSING,
    ) -> dict[str, Any]:
        """Make an HTTP request with TAP signature"""
        url = f"{self.base_url}{path}"
        body_str = None

        if body:
            import json
            body_str = json.dumps(body)

        headers = self._generate_headers(
            method=method,
            url=url,
            body=body_str,
            interaction_type=interaction_type,
        )

        response = await self._http_client.request(
            method=method,
            url=url,
            headers=headers,
            content=body_str,
        )

        if response.status_code >= 400:
            logger.error(f"Request failed: {response.status_code} - {response.text}")
            response.raise_for_status()

        return response.json()

    # ==================== Product APIs ====================

    async def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 20,
    ) -> dict:
        """Search products in merchant catalog"""
        params = []
        if query:
            params.append(f"query={query}")
        if category:
            params.append(f"category={category}")
        if min_price is not None:
            params.append(f"min_price={min_price}")
        if max_price is not None:
            params.append(f"max_price={max_price}")
        params.append(f"limit={limit}")

        path = f"/api/products?{'&'.join(params)}"
        return await self._request("GET", path)

    async def get_product(self, product_id: str) -> dict:
        """Get product details"""
        return await self._request("GET", f"/api/products/{product_id}")

    async def get_categories(self) -> list[str]:
        """Get available product categories"""
        return await self._request("GET", "/api/products/categories")

    # ==================== Cart APIs ====================

    async def create_cart(self) -> dict:
        """Create a new shopping cart"""
        return await self._request("POST", "/api/cart")

    async def get_cart(self, cart_id: str) -> dict:
        """Get cart by ID"""
        return await self._request("GET", f"/api/cart/{cart_id}")

    async def add_to_cart(
        self,
        cart_id: str,
        product_id: str,
        quantity: int = 1,
    ) -> dict:
        """Add item to cart"""
        return await self._request(
            "POST",
            f"/api/cart/{cart_id}/items",
            body={"product_id": product_id, "quantity": quantity},
        )

    async def update_cart_item(
        self,
        cart_id: str,
        product_id: str,
        quantity: int,
    ) -> dict:
        """Update item quantity in cart"""
        return await self._request(
            "PUT",
            f"/api/cart/{cart_id}/items/{product_id}",
            body={"quantity": quantity},
        )

    async def remove_from_cart(self, cart_id: str, product_id: str) -> dict:
        """Remove item from cart"""
        return await self._request(
            "DELETE",
            f"/api/cart/{cart_id}/items/{product_id}",
        )

    # ==================== Checkout APIs ====================

    async def checkout(
        self,
        cart_id: str,
        shipping_address: dict,
        payment: dict,
        instruction_id: Optional[str] = None,
    ) -> dict:
        """
        Process checkout.

        For Visa token payments, this requires a TAP checkout signature.
        """
        body = {
            "cart_id": cart_id,
            "shipping_address": shipping_address,
            "payment": payment,
        }

        if instruction_id:
            body["instruction_id"] = instruction_id

        # Use checkout interaction type for payment
        return await self._request(
            "POST",
            "/api/checkout",
            body=body,
            interaction_type=InteractionType.CHECKOUT,
        )

    async def get_order(self, order_id: str) -> dict:
        """Get order details"""
        return await self._request("GET", f"/api/checkout/orders/{order_id}")
