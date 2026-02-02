"""
Visa MCP Client

A Python wrapper for the Visa MCP (Model Context Protocol) server.
Handles authentication, token management, and API calls.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from .models import (
    CardEnrollmentRequest,
    CardEnrollmentResponse,
    PurchaseInstruction,
    PurchaseInstructionResponse,
    PaymentCredentials,
    CommerceSignal,
    CommerceSignalResponse,
    TransactionStatus,
)

logger = logging.getLogger(__name__)


class VisaMCPClientError(Exception):
    """Base exception for Visa MCP client errors"""
    pass


class AuthenticationError(VisaMCPClientError):
    """Authentication-related errors"""
    pass


class VisaMCPClient:
    """
    Client for Visa's MCP (Model Context Protocol) server.

    Provides access to Visa Intelligent Commerce APIs:
    - enroll-card: Register user's card with Passkey
    - initiate-purchase-instruction: Create purchase intent
    - authenticate-purchase-instruction: User authentication
    - retrieve-payment-credentials: Get tokenized credentials
    - share-commerce-signals: Report transaction outcomes

    Usage:
        client = VisaMCPClient.from_env()
        await client.connect()

        enrollment = await client.enroll_card(CardEnrollmentRequest(...))
        instruction = await client.initiate_purchase(PurchaseInstruction(...))
        credentials = await client.retrieve_credentials(instruction.instruction_id)
    """

    def __init__(
        self,
        mcp_base_url: str,
        vic_api_key: str,
        vic_api_key_ss: str,
        vts_api_key: str,
        vts_api_key_ss: str,
        mle_server_cert: str,
        mle_private_key: str,
        key_id: str,
        external_client_id: str,
        external_app_id: str,
        user_signing_private_key: str,
    ):
        """
        Initialize the Visa MCP client.

        All credentials should come from Visa Developer Portal.
        """
        self.base_url = mcp_base_url.rstrip("/")
        self._credentials = {
            "vic_api_key": vic_api_key,
            "vic_api_key_ss": vic_api_key_ss,
            "vts_api_key": vts_api_key,
            "vts_api_key_ss": vts_api_key_ss,
            "mle_server_cert": mle_server_cert,
            "mle_private_key": mle_private_key,
            "key_id": key_id,
            "external_client_id": external_client_id,
            "external_app_id": external_app_id,
        }
        self._signing_key = self._load_private_key(user_signing_private_key)
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def from_env(cls) -> "VisaMCPClient":
        """Create client from environment variables"""
        required_vars = [
            "MCP_BASE_URL",
            "VIC_API_KEY",
            "VIC_API_KEY_SS",
            "VTS_API_KEY",
            "VTS_API_KEY_SS",
            "MLE_SERVER_CERT",
            "MLE_PRIVATE_KEY",
            "KEY_ID",
            "EXTERNAL_CLIENT_ID",
            "EXTERNAL_APP_ID",
            "USER_SIGNING_PRIVATE_KEY",
        ]

        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

        return cls(
            mcp_base_url=os.environ["MCP_BASE_URL"],
            vic_api_key=os.environ["VIC_API_KEY"],
            vic_api_key_ss=os.environ["VIC_API_KEY_SS"],
            vts_api_key=os.environ["VTS_API_KEY"],
            vts_api_key_ss=os.environ["VTS_API_KEY_SS"],
            mle_server_cert=os.environ["MLE_SERVER_CERT"],
            mle_private_key=os.environ["MLE_PRIVATE_KEY"],
            key_id=os.environ["KEY_ID"],
            external_client_id=os.environ["EXTERNAL_CLIENT_ID"],
            external_app_id=os.environ["EXTERNAL_APP_ID"],
            user_signing_private_key=os.environ["USER_SIGNING_PRIVATE_KEY"],
        )

    def _load_private_key(self, key_pem: str):
        """Load RSA private key for JWT signing"""
        key_bytes = key_pem.encode() if isinstance(key_pem, str) else key_pem
        return serialization.load_pem_private_key(
            key_bytes, password=None, backend=default_backend()
        )

    async def connect(self) -> None:
        """Establish connection to MCP server"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        await self._refresh_token()
        logger.info("Connected to Visa MCP server")

    async def disconnect(self) -> None:
        """Close connection"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._access_token = None
        logger.info("Disconnected from Visa MCP server")

    async def _refresh_token(self) -> None:
        """Generate or refresh the JWE access token"""
        now = datetime.utcnow()

        # Check if current token is still valid
        if self._access_token and self._token_expires_at:
            if now < self._token_expires_at - timedelta(minutes=5):
                return  # Token still valid

        # Generate new token
        self._access_token = await self._generate_jwe_token()
        self._token_expires_at = now + timedelta(hours=1)
        logger.info("Refreshed MCP access token")

    async def _generate_jwe_token(self) -> str:
        """
        Generate JWE token for MCP authentication.

        This creates a JWT with credentials, signs it, then encrypts to JWE.
        In production, this would fetch Visa's public key from JWKS endpoint.
        """
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)

        # JWT payload with all credentials
        payload = {
            "vdp_vic_apikey": self._credentials["vic_api_key"],
            "vdp_vic_apikey_ss": self._credentials["vic_api_key_ss"],
            "vdp_vts_apikey": self._credentials["vts_api_key"],
            "vdp_vts_apikey_ss": self._credentials["vts_api_key_ss"],
            "mle_server_cert_value": self._credentials["mle_server_cert"],
            "mle_private_key_value": self._credentials["mle_private_key"],
            "mle_key_id": self._credentials["key_id"],
            "external_client_id": self._credentials["external_client_id"],
            "external_app_id": self._credentials["external_app_id"],
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "iss": self.base_url,
            "aud": self.base_url,
        }

        # Sign the JWT
        signed_jwt = jwt.encode(payload, self._signing_key, algorithm="RS256")

        # In production, encrypt to JWE using Visa's public key
        # For now, return the signed JWT (sandbox may accept this)
        return signed_jwt

    async def _ensure_connected(self) -> None:
        """Ensure we have a valid connection"""
        if self._http_client is None:
            await self.connect()
        await self._refresh_token()

    async def _call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Call an MCP tool on the Visa server.

        Args:
            tool_name: Name of the MCP tool to invoke
            args: Arguments for the tool

        Returns:
            Tool response as dictionary
        """
        await self._ensure_connected()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        # MCP tool invocation format
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            },
            "id": 1,
        }

        response = await self._http_client.post(
            f"{self.base_url}/mcp",
            headers=headers,
            json=request_body,
        )

        if response.status_code == 401:
            # Token expired, refresh and retry
            self._access_token = None
            await self._refresh_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = await self._http_client.post(
                f"{self.base_url}/mcp",
                headers=headers,
                json=request_body,
            )

        if response.status_code != 200:
            raise VisaMCPClientError(
                f"MCP call failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        if "error" in result:
            raise VisaMCPClientError(f"MCP error: {result['error']}")

        return result.get("result", {})

    # ==================== VIC API Methods ====================

    async def enroll_card(
        self, request: CardEnrollmentRequest
    ) -> CardEnrollmentResponse:
        """
        Enroll a card with Visa Intelligent Commerce.

        This initiates the card enrollment process which requires
        user verification via Passkey.

        Args:
            request: Card enrollment details

        Returns:
            Enrollment response with auth URL for Passkey setup
        """
        result = await self._call_tool(
            "enroll-card",
            {
                "cardHint": request.card_hint,
                "returnUrl": request.return_url,
                "agentId": request.agent_id,
            },
        )

        return CardEnrollmentResponse(
            enrollment_id=result["enrollmentId"],
            auth_url=result["authUrl"],
            status=result["status"],
            expires_at=datetime.fromisoformat(result["expiresAt"]),
        )

    async def initiate_purchase(
        self, instruction: PurchaseInstruction
    ) -> PurchaseInstructionResponse:
        """
        Initiate a purchase instruction.

        Creates a formal purchase intent that can be authenticated
        by the user via Passkey.

        Args:
            instruction: Purchase details

        Returns:
            Instruction response with auth URL
        """
        items = [
            {
                "name": item.name,
                "sku": item.sku,
                "quantity": item.quantity,
                "unitPrice": item.unit_price,
                "totalPrice": item.total_price,
            }
            for item in instruction.items
        ]

        result = await self._call_tool(
            "initiate-purchase-instruction",
            {
                "merchantUrl": instruction.merchant_url,
                "merchantName": instruction.merchant_name,
                "amount": instruction.amount,
                "currency": instruction.currency,
                "items": items,
                "description": instruction.description,
            },
        )

        return PurchaseInstructionResponse(
            instruction_id=result["instructionId"],
            auth_url=result["authUrl"],
            status=result["status"],
            expires_at=datetime.fromisoformat(result["expiresAt"]),
            amount=result["amount"],
            currency=result["currency"],
        )

    async def authenticate_purchase(self, instruction_id: str) -> bool:
        """
        Check if a purchase instruction has been authenticated.

        This is called after the user completes Passkey authentication.

        Args:
            instruction_id: ID from initiate_purchase

        Returns:
            True if authenticated, False otherwise
        """
        result = await self._call_tool(
            "authenticate-purchase-instruction",
            {"instructionId": instruction_id},
        )

        return result.get("authenticated", False)

    async def retrieve_credentials(
        self, instruction_id: str
    ) -> PaymentCredentials:
        """
        Retrieve tokenized payment credentials.

        Can only be called after the purchase instruction is authenticated.
        Returns network-controlled credentials with built-in limits.

        Args:
            instruction_id: Authenticated instruction ID

        Returns:
            Tokenized payment credentials
        """
        result = await self._call_tool(
            "retrieve-payment-credentials",
            {"instructionId": instruction_id},
        )

        return PaymentCredentials(
            token=result["token"],
            expiry_month=result["expiryMonth"],
            expiry_year=result["expiryYear"],
            cvv=result["cvv"],
            cardholder_name=result["cardholderName"],
            max_amount=result["maxAmount"],
            valid_merchant_url=result["validMerchantUrl"],
            expires_at=datetime.fromisoformat(result["expiresAt"]),
        )

    async def share_commerce_signal(
        self, signal: CommerceSignal
    ) -> CommerceSignalResponse:
        """
        Report transaction outcome to Visa.

        Should be called after every purchase attempt (success or failure)
        for fraud prevention and dispute resolution.

        Args:
            signal: Transaction outcome details

        Returns:
            Signal acknowledgment
        """
        result = await self._call_tool(
            "share-commerce-signals",
            {
                "instructionId": signal.instruction_id,
                "status": signal.status.value,
                "orderId": signal.order_id,
                "actualAmount": signal.actual_amount,
                "merchantReference": signal.merchant_reference,
                "failureReason": signal.failure_reason,
            },
        )

        return CommerceSignalResponse(
            signal_id=result["signalId"],
            status=result["status"],
            received_at=datetime.fromisoformat(result["receivedAt"]),
        )

    async def list_available_tools(self) -> list[dict]:
        """List all available MCP tools"""
        await self._ensure_connected()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        }

        response = await self._http_client.post(
            f"{self.base_url}/mcp",
            headers=headers,
            json=request_body,
        )

        if response.status_code != 200:
            raise VisaMCPClientError(f"Failed to list tools: {response.text}")

        result = response.json()
        return result.get("result", {}).get("tools", [])
