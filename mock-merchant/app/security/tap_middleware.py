"""
TAP Signature Verification Middleware

Verifies TAP (Trusted Agent Protocol) signatures on incoming requests.
Allows requests without signatures (regular users) but validates if present.
"""

import os
import logging
from typing import Optional, Callable

from fastapi import Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))

from tap.verifier import TAPVerifier
from tap.models import VerificationResult, InteractionType

logger = logging.getLogger(__name__)


class TAPVerificationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that verifies TAP signatures on requests.

    If a request has Signature headers, it validates them.
    If validation fails, the request is rejected.
    If no signature headers, the request proceeds normally (regular user).
    """

    def __init__(self, app, verifier: TAPVerifier):
        super().__init__(app)
        self.verifier = verifier

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if request has TAP signature headers
        signature = request.headers.get("Signature")
        signature_input = request.headers.get("Signature-Input")

        if signature and signature_input:
            # This is an agent request - verify signature
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                body = body.decode() if body else None

            # Reconstruct full URL
            url = str(request.url)

            result = self.verifier.verify(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                body=body,
            )

            if not result.is_valid:
                logger.warning(f"TAP verification failed: {result.error_message}")
                raise HTTPException(
                    status_code=401,
                    detail=f"TAP signature verification failed: {result.error_message}",
                )

            # Store verification result in request state for downstream use
            request.state.tap_verified = True
            request.state.tap_agent_id = result.agent_id
            request.state.tap_interaction_type = result.interaction_type
            request.state.tap_keyid = result.keyid

            logger.info(
                f"TAP verified: agent={result.agent_id}, "
                f"type={result.interaction_type.value if result.interaction_type else 'unknown'}"
            )
        else:
            # Regular user request (no TAP headers)
            request.state.tap_verified = False
            request.state.tap_agent_id = None
            request.state.tap_interaction_type = None

        response = await call_next(request)
        return response


class TAPDependency:
    """
    FastAPI dependency for TAP verification.

    Use this when you want route-level control over TAP verification
    instead of middleware.
    """

    def __init__(self, require_tap: bool = False, require_checkout: bool = False):
        """
        Args:
            require_tap: If True, reject requests without valid TAP signature
            require_checkout: If True, require interaction type to be 'checkout'
        """
        self.require_tap = require_tap
        self.require_checkout = require_checkout

    async def __call__(self, request: Request) -> VerificationResult:
        """Check TAP status from request state"""
        is_verified = getattr(request.state, "tap_verified", False)
        agent_id = getattr(request.state, "tap_agent_id", None)
        interaction_type = getattr(request.state, "tap_interaction_type", None)

        if self.require_tap and not is_verified:
            raise HTTPException(
                status_code=401,
                detail="This endpoint requires TAP signature authentication",
            )

        if self.require_checkout and interaction_type != InteractionType.CHECKOUT:
            raise HTTPException(
                status_code=403,
                detail="This endpoint requires checkout interaction type",
            )

        return VerificationResult(
            is_valid=is_verified,
            agent_id=agent_id,
            interaction_type=interaction_type,
            keyid=getattr(request.state, "tap_keyid", None),
        )


def get_tap_verifier() -> TAPVerifier:
    """
    Create and configure TAP verifier with registered agents.

    In production, agent public keys would be fetched from
    the Visa agent registry.
    """
    verifier = TAPVerifier()

    # Load agent public key from environment or file
    agent_public_key = os.getenv("TAP_AGENT_PUBLIC_KEY")
    agent_keyid = os.getenv("TAP_AGENT_KEYID", "https://registry.visa.com/agents/test-agent")

    if agent_public_key:
        verifier.register_agent(
            keyid=agent_keyid,
            public_key_pem=agent_public_key,
            name="Test Shopping Agent",
        )
        logger.info(f"Registered TAP agent: {agent_keyid}")
    else:
        logger.warning("No TAP agent public key configured - TAP verification disabled")

    return verifier


# Dependency instances
require_tap = TAPDependency(require_tap=True)
require_checkout = TAPDependency(require_tap=True, require_checkout=True)
optional_tap = TAPDependency(require_tap=False)
