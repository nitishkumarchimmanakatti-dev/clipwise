"""Session-based authentication and rate-limiting for Clipwise v2."""

import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from clipwise.config import CLIPWISE_PASSWORD, SESSION_SECRET

COOKIE_NAME = "clipwise_session"
SESSION_MAX_AGE = 86400 * 30  # 30 days


def generate_session_token(password: str) -> str:
    """Generate a HMAC-signed session token containing the timestamp."""
    ts = str(int(time.time()))
    payload = f"{password}:{ts}".encode()
    signature = hmac.new(SESSION_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return f"{ts}:{signature}"


def verify_session_token(token: Optional[str]) -> bool:
    """Validate token signature and expiration."""
    if not CLIPWISE_PASSWORD:
        return True  # Auth is disabled if no password is configured

    if not token or ":" not in token:
        return False

    try:
        ts_str, signature = token.split(":", 1)
        ts = int(ts_str)
        # Check expiration
        if time.time() - ts > SESSION_MAX_AGE:
            return False

        payload = f"{CLIPWISE_PASSWORD}:{ts_str}".encode()
        expected = hmac.new(SESSION_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


def is_authenticated(request: Request) -> bool:
    """Check if the incoming request has a valid session token."""
    if not CLIPWISE_PASSWORD:
        return True

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Also check Authorization header Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    return verify_session_token(token)


def require_auth(request: Request):
    """FastAPI dependency for endpoints requiring authentication."""
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with the administrator password.",
        )
