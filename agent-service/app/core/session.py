"""Session management for agent conversations"""

import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class SessionState(str, Enum):
    """Current state of the shopping session"""
    IDLE = "idle"
    BROWSING = "browsing"
    CART_MANAGEMENT = "cart_management"
    ENROLLING_CARD = "enrolling_card"
    AWAITING_AUTH = "awaiting_auth"
    CHECKOUT = "checkout"
    COMPLETED = "completed"


@dataclass
class CartState:
    """Current cart state"""
    cart_id: Optional[str] = None
    items: list = field(default_factory=list)
    total: float = 0.0


@dataclass
class PaymentState:
    """Payment flow state"""
    card_enrolled: bool = False
    enrollment_id: Optional[str] = None
    instruction_id: Optional[str] = None
    authenticated: bool = False


@dataclass
class UserSession:
    """User shopping session"""
    session_id: str
    created_at: datetime
    updated_at: datetime
    state: SessionState = SessionState.IDLE
    cart: CartState = field(default_factory=CartState)
    payment: PaymentState = field(default_factory=PaymentState)
    conversation_history: list = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.updated_at = datetime.utcnow()

    def get_recent_messages(self, limit: int = 10) -> list:
        """Get recent messages for LLM context"""
        return self.conversation_history[-limit:]

    def update_state(self, new_state: SessionState) -> None:
        """Update session state"""
        self.state = new_state
        self.updated_at = datetime.utcnow()


class SessionManager:
    """Manages user sessions"""

    def __init__(self):
        self.sessions: dict[str, UserSession] = {}

    def create_session(self) -> UserSession:
        """Create a new session"""
        now = datetime.utcnow()
        session = UserSession(
            session_id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def get_or_create_session(self, session_id: Optional[str] = None) -> UserSession:
        """Get existing session or create new one"""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        return self.create_session()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Remove sessions older than max_age_hours"""
        now = datetime.utcnow()
        old_sessions = [
            sid for sid, session in self.sessions.items()
            if (now - session.updated_at).total_seconds() > max_age_hours * 3600
        ]
        for sid in old_sessions:
            del self.sessions[sid]
        return len(old_sessions)


# Singleton instance
session_manager = SessionManager()
