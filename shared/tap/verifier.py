"""
TAP Signature Verifier

Verifies RFC 9421 HTTP Message Signatures for the Trusted Agent Protocol.
Used by merchants to validate agent requests.
"""

import base64
import hashlib
import re
import time
from typing import Optional
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from .models import VerificationResult, SignatureAlgorithm, InteractionType


class TAPVerifier:
    """
    Verifies TAP-compliant HTTP Message Signatures.

    Usage:
        verifier = TAPVerifier()
        verifier.register_agent(
            keyid="https://registry.visa.com/agents/my-agent",
            public_key_pem="..."
        )

        result = verifier.verify(
            method="GET",
            url="https://merchant.com/api/products",
            headers=request.headers
        )

        if result.is_valid:
            print(f"Valid request from agent: {result.agent_id}")
    """

    def __init__(
        self,
        max_clock_skew_seconds: int = 60,
        max_signature_age_seconds: int = 300,
    ):
        """
        Initialize the TAP verifier.

        Args:
            max_clock_skew_seconds: Maximum allowed clock skew
            max_signature_age_seconds: Maximum age of signatures to accept
        """
        self.max_clock_skew = max_clock_skew_seconds
        self.max_signature_age = max_signature_age_seconds
        self._trusted_agents: dict[str, dict] = {}
        self._used_nonces: set[str] = set()

    def register_agent(
        self,
        keyid: str,
        public_key_pem: str,
        name: Optional[str] = None,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519,
    ) -> None:
        """
        Register a trusted agent with their public key.

        Args:
            keyid: Agent's key identifier
            public_key_pem: PEM-encoded public key
            name: Optional human-readable name
            algorithm: Expected signature algorithm
        """
        public_key = self._load_public_key(public_key_pem)
        self._trusted_agents[keyid] = {
            "public_key": public_key,
            "name": name or keyid,
            "algorithm": algorithm,
        }

    def _load_public_key(self, pem: str) -> Ed25519PublicKey | RSAPublicKey:
        """Load public key from PEM string"""
        pem_bytes = pem.encode() if isinstance(pem, str) else pem

        try:
            return serialization.load_pem_public_key(
                pem_bytes, backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load public key: {e}")

    def verify(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify a TAP signature on an incoming request.

        Args:
            method: HTTP method
            url: Full request URL
            headers: Request headers (must include Signature and Signature-Input)
            body: Request body if present

        Returns:
            VerificationResult indicating success/failure
        """
        # Extract signature headers (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}

        signature_header = headers_lower.get("signature")
        signature_input = headers_lower.get("signature-input")

        if not signature_header or not signature_input:
            return VerificationResult(
                is_valid=False,
                error_message="Missing Signature or Signature-Input headers",
            )

        # Parse signature input to extract parameters
        try:
            params = self._parse_signature_input(signature_input)
        except ValueError as e:
            return VerificationResult(
                is_valid=False,
                error_message=f"Failed to parse Signature-Input: {e}",
            )

        # Validate agent is registered
        keyid = params.get("keyid")
        if keyid not in self._trusted_agents:
            return VerificationResult(
                is_valid=False,
                error_message=f"Unknown agent keyid: {keyid}",
                keyid=keyid,
            )

        # Validate timestamp
        created = params.get("created")
        expires = params.get("expires")
        now = int(time.time())

        if created > now + self.max_clock_skew:
            return VerificationResult(
                is_valid=False,
                error_message="Signature created in the future",
                keyid=keyid,
                created=created,
            )

        if expires < now:
            return VerificationResult(
                is_valid=False,
                error_message="Signature has expired",
                keyid=keyid,
                created=created,
                expires=expires,
            )

        if now - created > self.max_signature_age:
            return VerificationResult(
                is_valid=False,
                error_message="Signature too old",
                keyid=keyid,
                created=created,
            )

        # Check nonce for replay protection
        nonce = params.get("nonce")
        if nonce in self._used_nonces:
            return VerificationResult(
                is_valid=False,
                error_message="Nonce already used (replay attack)",
                keyid=keyid,
            )

        # Reconstruct signature base
        try:
            signature_base = self._reconstruct_signature_base(
                method=method,
                url=url,
                body=body,
                headers=headers_lower,
                params=params,
            )
        except ValueError as e:
            return VerificationResult(
                is_valid=False,
                error_message=f"Failed to reconstruct signature base: {e}",
                keyid=keyid,
            )

        # Extract and verify signature
        try:
            signature_bytes = self._extract_signature(signature_header)
        except ValueError as e:
            return VerificationResult(
                is_valid=False,
                error_message=f"Failed to extract signature: {e}",
                keyid=keyid,
            )

        agent = self._trusted_agents[keyid]
        try:
            self._verify_signature(
                public_key=agent["public_key"],
                signature=signature_bytes,
                message=signature_base.encode(),
            )
        except InvalidSignature:
            return VerificationResult(
                is_valid=False,
                error_message="Invalid signature",
                keyid=keyid,
                created=created,
                expires=expires,
            )

        # Mark nonce as used
        self._used_nonces.add(nonce)
        # Cleanup old nonces (simple approach - in production use TTL cache)
        if len(self._used_nonces) > 10000:
            self._used_nonces.clear()

        # Extract interaction type (tag)
        tag = params.get("tag", "browsing")
        interaction_type = (
            InteractionType.CHECKOUT
            if tag == "checkout"
            else InteractionType.BROWSING
        )

        return VerificationResult(
            is_valid=True,
            agent_id=agent["name"],
            interaction_type=interaction_type,
            keyid=keyid,
            created=created,
            expires=expires,
        )

    def _parse_signature_input(self, signature_input: str) -> dict:
        """Parse the Signature-Input header to extract parameters"""
        # Format: sig1=("@method" "@authority" "@path");created=123;expires=456;keyid="...";alg="...";nonce="...";tag="..."

        # Extract the sig1= part
        if not signature_input.startswith("sig1="):
            raise ValueError("Expected sig1= prefix")

        params_str = signature_input[5:]  # Remove "sig1="

        params = {}

        # Extract keyid
        keyid_match = re.search(r'keyid="([^"]+)"', params_str)
        if keyid_match:
            params["keyid"] = keyid_match.group(1)

        # Extract created
        created_match = re.search(r"created=(\d+)", params_str)
        if created_match:
            params["created"] = int(created_match.group(1))

        # Extract expires
        expires_match = re.search(r"expires=(\d+)", params_str)
        if expires_match:
            params["expires"] = int(expires_match.group(1))

        # Extract nonce
        nonce_match = re.search(r'nonce="([^"]+)"', params_str)
        if nonce_match:
            params["nonce"] = nonce_match.group(1)

        # Extract algorithm
        alg_match = re.search(r'alg="([^"]+)"', params_str)
        if alg_match:
            params["alg"] = alg_match.group(1)

        # Extract tag (interaction type)
        tag_match = re.search(r'tag="([^"]+)"', params_str)
        if tag_match:
            params["tag"] = tag_match.group(1)

        # Extract covered components
        components_match = re.search(r"\(([^)]+)\)", params_str)
        if components_match:
            components_str = components_match.group(1)
            params["components"] = [
                c.strip().strip('"') for c in components_str.split()
            ]

        return params

    def _reconstruct_signature_base(
        self,
        method: str,
        url: str,
        body: Optional[str],
        headers: dict[str, str],
        params: dict,
    ) -> str:
        """Reconstruct the signature base string for verification"""
        parsed = urlparse(url)
        authority = parsed.netloc
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        lines = []

        # Add covered components in order
        components = params.get("components", [])

        for component in components:
            if component == "@method":
                lines.append(f'"@method": {method.upper()}')
            elif component == "@authority":
                lines.append(f'"@authority": {authority}')
            elif component == "@path":
                lines.append(f'"@path": {path}')
            elif component == "content-digest":
                if body:
                    digest = self._compute_content_digest(body)
                    lines.append(f'"content-digest": sha-256=:{digest}:')
            else:
                # Regular header
                header_value = headers.get(component.lower(), "")
                lines.append(f'"{component}": {header_value}')

        # Reconstruct signature-params line
        signature_input = headers.get("signature-input", "")
        # Remove the "sig1=" prefix to get just the params
        if signature_input.startswith("sig1="):
            params_line = signature_input[5:]
        else:
            params_line = signature_input

        lines.append(f'"@signature-params": {params_line}')

        return "\n".join(lines)

    def _compute_content_digest(self, body: str) -> str:
        """Compute SHA-256 content digest"""
        body_bytes = body.encode() if isinstance(body, str) else body
        digest = hashlib.sha256(body_bytes).digest()
        return base64.b64encode(digest).decode()

    def _extract_signature(self, signature_header: str) -> bytes:
        """Extract signature bytes from Signature header"""
        # Format: sig1=:base64signature:
        match = re.search(r"sig1=:([^:]+):", signature_header)
        if not match:
            raise ValueError("Invalid Signature header format")

        return base64.b64decode(match.group(1))

    def _verify_signature(
        self,
        public_key: Ed25519PublicKey | RSAPublicKey,
        signature: bytes,
        message: bytes,
    ) -> None:
        """Verify the cryptographic signature"""
        if isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(signature, message)
        else:
            # RSA-PSS-SHA256
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
