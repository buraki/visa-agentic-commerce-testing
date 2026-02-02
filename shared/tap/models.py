"""TAP Data Models"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class InteractionType(str, Enum):
    """Type of agent-merchant interaction"""
    BROWSING = "browsing"
    CHECKOUT = "checkout"


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms"""
    ED25519 = "ed25519"
    RSA_PSS_SHA256 = "rsa-pss-sha256"


@dataclass
class SignatureComponents:
    """Components of a TAP signature"""
    signature: str
    signature_input: str
    keyid: str
    created: int
    expires: int
    nonce: str
    algorithm: SignatureAlgorithm

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP headers"""
        return {
            "Signature": self.signature,
            "Signature-Input": self.signature_input,
        }


@dataclass
class VerificationResult:
    """Result of TAP signature verification"""
    is_valid: bool
    agent_id: Optional[str] = None
    interaction_type: Optional[InteractionType] = None
    error_message: Optional[str] = None
    keyid: Optional[str] = None
    created: Optional[int] = None
    expires: Optional[int] = None

    @property
    def is_browsing(self) -> bool:
        return self.interaction_type == InteractionType.BROWSING

    @property
    def is_checkout(self) -> bool:
        return self.interaction_type == InteractionType.CHECKOUT
