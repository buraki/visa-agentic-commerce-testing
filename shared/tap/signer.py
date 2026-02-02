"""
TAP Signature Generator

Implements RFC 9421 HTTP Message Signatures for the Trusted Agent Protocol.
Supports Ed25519 and RSA-PSS-SHA256 algorithms.
"""

import base64
import hashlib
import time
import uuid
from typing import Optional
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.backends import default_backend

from .models import SignatureComponents, SignatureAlgorithm, InteractionType


class TAPSigner:
    """
    Generates TAP-compliant HTTP Message Signatures per RFC 9421.

    Usage:
        signer = TAPSigner(
            private_key_pem="...",
            keyid="https://registry.visa.com/agents/my-agent",
            algorithm=SignatureAlgorithm.ED25519
        )

        sig = signer.sign(
            method="GET",
            url="https://merchant.com/api/products",
            interaction_type=InteractionType.BROWSING
        )

        headers = sig.to_headers()
    """

    def __init__(
        self,
        private_key_pem: str,
        keyid: str,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.ED25519,
        signature_validity_seconds: int = 300,
    ):
        """
        Initialize the TAP signer.

        Args:
            private_key_pem: PEM-encoded private key
            keyid: Agent's key identifier (typically a URL to the agent registry)
            algorithm: Signature algorithm to use
            signature_validity_seconds: How long signatures remain valid
        """
        self.keyid = keyid
        self.algorithm = algorithm
        self.validity_seconds = signature_validity_seconds
        self._private_key = self._load_private_key(private_key_pem)

    def _load_private_key(self, pem: str) -> Ed25519PrivateKey | RSAPrivateKey:
        """Load private key from PEM string"""
        pem_bytes = pem.encode() if isinstance(pem, str) else pem

        try:
            # Try loading as Ed25519
            return serialization.load_pem_private_key(
                pem_bytes, password=None, backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")

    def sign(
        self,
        method: str,
        url: str,
        body: Optional[str] = None,
        interaction_type: InteractionType = InteractionType.BROWSING,
        additional_headers: Optional[dict[str, str]] = None,
    ) -> SignatureComponents:
        """
        Generate a TAP signature for an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL being requested
            body: Request body (for POST/PUT requests)
            interaction_type: Type of interaction (browsing/checkout)
            additional_headers: Extra headers to include in signature base

        Returns:
            SignatureComponents with signature and signature-input headers
        """
        # Parse URL components
        parsed = urlparse(url)
        authority = parsed.netloc
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # Generate signature parameters
        created = int(time.time())
        expires = created + self.validity_seconds
        nonce = str(uuid.uuid4())

        # Build the signature base string per RFC 9421
        signature_base = self._build_signature_base(
            method=method.upper(),
            authority=authority,
            path=path,
            body=body,
            created=created,
            expires=expires,
            nonce=nonce,
            interaction_type=interaction_type,
            additional_headers=additional_headers,
        )

        # Sign the base string
        signature_bytes = self._create_signature(signature_base)
        signature_b64 = base64.b64encode(signature_bytes).decode()

        # Build signature-input header
        signature_input = self._build_signature_input(
            method=method.upper(),
            has_body=body is not None,
            created=created,
            expires=expires,
            nonce=nonce,
            interaction_type=interaction_type,
            additional_headers=additional_headers,
        )

        return SignatureComponents(
            signature=f"sig1=:{signature_b64}:",
            signature_input=signature_input,
            keyid=self.keyid,
            created=created,
            expires=expires,
            nonce=nonce,
            algorithm=self.algorithm,
        )

    def _build_signature_base(
        self,
        method: str,
        authority: str,
        path: str,
        body: Optional[str],
        created: int,
        expires: int,
        nonce: str,
        interaction_type: InteractionType,
        additional_headers: Optional[dict[str, str]],
    ) -> str:
        """Build the signature base string per RFC 9421"""
        lines = []

        # Derived components
        lines.append(f'"@method": {method}')
        lines.append(f'"@authority": {authority}')
        lines.append(f'"@path": {path}')

        # Content-digest if body present
        if body:
            digest = self._compute_content_digest(body)
            lines.append(f'"content-digest": sha-256=:{digest}:')

        # Additional headers
        if additional_headers:
            for header_name, header_value in sorted(additional_headers.items()):
                lines.append(f'"{header_name.lower()}": {header_value}')

        # Signature parameters line
        params_line = self._build_signature_params_line(
            method=method,
            has_body=body is not None,
            created=created,
            expires=expires,
            nonce=nonce,
            interaction_type=interaction_type,
            additional_headers=additional_headers,
        )
        lines.append(f'"@signature-params": {params_line}')

        return "\n".join(lines)

    def _build_signature_params_line(
        self,
        method: str,
        has_body: bool,
        created: int,
        expires: int,
        nonce: str,
        interaction_type: InteractionType,
        additional_headers: Optional[dict[str, str]],
    ) -> str:
        """Build the signature parameters for signature-input header"""
        # Covered components
        components = ['"@method"', '"@authority"', '"@path"']

        if has_body:
            components.append('"content-digest"')

        if additional_headers:
            for header_name in sorted(additional_headers.keys()):
                components.append(f'"{header_name.lower()}"')

        components_str = " ".join(components)

        # Parameters
        alg = "ed25519" if self.algorithm == SignatureAlgorithm.ED25519 else "rsa-pss-sha256"

        params = f'({components_str});created={created};expires={expires};keyid="{self.keyid}";alg="{alg}";nonce="{nonce}";tag="{interaction_type.value}"'

        return params

    def _build_signature_input(
        self,
        method: str,
        has_body: bool,
        created: int,
        expires: int,
        nonce: str,
        interaction_type: InteractionType,
        additional_headers: Optional[dict[str, str]],
    ) -> str:
        """Build the Signature-Input header value"""
        params_line = self._build_signature_params_line(
            method=method,
            has_body=has_body,
            created=created,
            expires=expires,
            nonce=nonce,
            interaction_type=interaction_type,
            additional_headers=additional_headers,
        )
        return f"sig1={params_line}"

    def _compute_content_digest(self, body: str) -> str:
        """Compute SHA-256 content digest"""
        body_bytes = body.encode() if isinstance(body, str) else body
        digest = hashlib.sha256(body_bytes).digest()
        return base64.b64encode(digest).decode()

    def _create_signature(self, signature_base: str) -> bytes:
        """Create the cryptographic signature"""
        base_bytes = signature_base.encode()

        if isinstance(self._private_key, ed25519.Ed25519PrivateKey):
            return self._private_key.sign(base_bytes)
        else:
            # RSA-PSS-SHA256
            return self._private_key.sign(
                base_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
