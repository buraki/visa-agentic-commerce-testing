"""Authentication callback routes for Visa Passkey flows"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..core.session import session_manager, SessionState

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.get("/callback")
async def auth_callback(
    request: Request,
    session_id: Optional[str] = Query(None),
    enrollment_id: Optional[str] = Query(None),
    instruction_id: Optional[str] = Query(None),
    status: str = Query("success"),
    error: Optional[str] = Query(None),
):
    """
    Callback endpoint for Visa Passkey authentication flows.

    This is called after user completes:
    - Card enrollment verification
    - Purchase authentication

    In production, this would verify the callback signature
    and update the session accordingly.
    """
    if status == "error" or error:
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Authentication Failed</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-100 min-h-screen flex items-center justify-center">
                <div class="bg-white p-8 rounded-lg shadow-md max-w-md text-center">
                    <div class="text-red-500 text-6xl mb-4">✗</div>
                    <h1 class="text-2xl font-bold text-gray-900 mb-2">Authentication Failed</h1>
                    <p class="text-gray-600 mb-4">{error or 'An error occurred during authentication.'}</p>
                    <p class="text-sm text-gray-500">You can close this window and try again.</p>
                </div>
                <script>
                    // Notify parent window of failure
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'auth_callback',
                            status: 'error',
                            error: '{error or "Authentication failed"}'
                        }}, '*');
                    }}
                </script>
            </body>
            </html>
            """,
            status_code=200,
        )

    # Success case
    # Update session if provided
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            if enrollment_id:
                session.payment.card_enrolled = True
                session.payment.enrollment_id = enrollment_id
                session.update_state(SessionState.CART_MANAGEMENT)

            if instruction_id:
                session.payment.authenticated = True
                session.payment.instruction_id = instruction_id
                session.update_state(SessionState.CHECKOUT)

    return HTMLResponse(
        content=f"""
        <html>
        <head>
            <title>Authentication Successful</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md max-w-md text-center">
                <div class="text-green-500 text-6xl mb-4">✓</div>
                <h1 class="text-2xl font-bold text-gray-900 mb-2">Authentication Successful</h1>
                <p class="text-gray-600 mb-4">Your identity has been verified.</p>
                <p class="text-sm text-gray-500">You can close this window and continue shopping.</p>
            </div>
            <script>
                // Notify parent window of success
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'auth_callback',
                        status: 'success',
                        session_id: '{session_id or ""}',
                        enrollment_id: '{enrollment_id or ""}',
                        instruction_id: '{instruction_id or ""}'
                    }}, '*');
                    setTimeout(() => window.close(), 2000);
                }}
            </script>
        </body>
        </html>
        """,
        status_code=200,
    )


@router.get("/status/{session_id}")
async def get_auth_status(session_id: str):
    """Check authentication status for a session"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "state": session.state.value,
        "card_enrolled": session.payment.card_enrolled,
        "authenticated": session.payment.authenticated,
        "enrollment_id": session.payment.enrollment_id,
        "instruction_id": session.payment.instruction_id,
    }
