"""Visa MCP Data Models"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime


class TransactionStatus(str, Enum):
    """Transaction outcome status"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class CardEnrollmentRequest:
    """Request to enroll a card with Visa"""
    # Card details would typically come from user input
    # In sandbox, can use test card numbers
    card_hint: str  # Last 4 digits for display
    return_url: str  # Where to redirect after Passkey setup
    agent_id: str


@dataclass
class CardEnrollmentResponse:
    """Response from card enrollment"""
    enrollment_id: str
    auth_url: str  # URL to redirect user for Passkey setup
    status: str
    expires_at: datetime


@dataclass
class PurchaseItem:
    """Item in a purchase instruction"""
    name: str
    sku: str
    quantity: int
    unit_price: float
    total_price: float


@dataclass
class PurchaseInstruction:
    """Request to initiate a purchase"""
    merchant_url: str
    merchant_name: str
    amount: float
    currency: str = "USD"
    items: list[PurchaseItem] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class PurchaseInstructionResponse:
    """Response from purchase instruction creation"""
    instruction_id: str
    auth_url: str  # URL for Passkey authentication
    status: str
    expires_at: datetime
    amount: float
    currency: str


@dataclass
class PaymentCredentials:
    """Tokenized payment credentials from Visa"""
    token: str  # Tokenized card number
    expiry_month: str
    expiry_year: str
    cvv: str  # Dynamic CVV
    cardholder_name: str
    # Network-enforced controls
    max_amount: float
    valid_merchant_url: str
    expires_at: datetime


@dataclass
class CommerceSignal:
    """Signal to report transaction outcome to Visa"""
    instruction_id: str
    status: TransactionStatus
    order_id: Optional[str] = None
    actual_amount: Optional[float] = None
    merchant_reference: Optional[str] = None
    failure_reason: Optional[str] = None


@dataclass
class CommerceSignalResponse:
    """Response from commerce signal submission"""
    signal_id: str
    status: str
    received_at: datetime
