"""Chat API routes for agent service"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends

from ..core.session import session_manager, UserSession
from ..services.shopping_agent import ShoppingAgent, AgentResponse
from ..services.merchant_client import MerchantClient
from ..core.config import settings

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Initialize services (would be dependency injected in production)
merchant_client: Optional[MerchantClient] = None
shopping_agent: Optional[ShoppingAgent] = None


def get_merchant_client() -> MerchantClient:
    """Get or create merchant client"""
    global merchant_client
    if merchant_client is None:
        merchant_client = MerchantClient(
            merchant_base_url=settings.merchant_base_url,
            tap_private_key=settings.get_tap_private_key(),
            tap_keyid=settings.tap_agent_keyid,
        )
    return merchant_client


def get_shopping_agent() -> ShoppingAgent:
    """Get or create shopping agent"""
    global shopping_agent
    if shopping_agent is None:
        shopping_agent = ShoppingAgent(
            merchant_client=get_merchant_client(),
            visa_client=None,  # Add Visa MCP client if configured
        )
    return shopping_agent


class ChatRequest(BaseModel):
    """Request to send a chat message"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    session_id: str
    message: str
    action_type: Optional[str] = None
    data: Optional[dict] = None
    requires_user_action: bool = False
    action_url: Optional[str] = None


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    agent: ShoppingAgent = Depends(get_shopping_agent),
):
    """
    Send a message to the shopping agent.

    Creates a new session if session_id is not provided.
    """
    # Get or create session
    session = session_manager.get_or_create_session(request.session_id)

    # Process message
    response = await agent.process_message(session, request.message)

    return ChatResponse(
        session_id=session.session_id,
        message=response.message,
        action_type=response.action_type,
        data=response.data,
        requires_user_action=response.requires_user_action,
        action_url=response.action_url,
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "cart": {
            "cart_id": session.cart.cart_id,
            "items_count": len(session.cart.items),
            "total": session.cart.total,
        },
        "payment": {
            "card_enrolled": session.payment.card_enrolled,
            "authenticated": session.payment.authenticated,
        },
        "message_count": len(session.conversation_history),
    }


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 20):
    """Get conversation history for a session"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "messages": session.get_recent_messages(limit),
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_manager.delete_session(session_id):
        return {"message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")
