"""
Portal Token Generator — HMAC-based signed tokens for customer self-service portal.

Tokens encode a phone number + expiry timestamp, signed with HMAC-SHA256.
No database table needed — the token is self-validating.

Usage:
    from portal_token import generate_portal_token, validate_portal_token

    token = generate_portal_token("27769695462", hours=24)
    phone = validate_portal_token(token)  # Returns phone or None if expired/invalid
"""

import hmac
import hashlib
import base64
import os
import time

# Use a dedicated secret; falls back to SUPABASE_KEY if not set
PORTAL_SECRET = os.environ.get("PORTAL_TOKEN_SECRET") or os.environ.get("SUPABASE_KEY", "fallback-dev-secret")


def generate_portal_token(phone_number: str, hours: int = 24) -> str:
    """Generate a signed, time-limited token encoding a phone number."""
    phone = phone_number.lstrip("+")
    expires = int(time.time()) + (hours * 3600)
    payload = f"{phone}:{expires}"
    sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def validate_portal_token(token: str) -> str | None:
    """Validate token and return phone number, or None if invalid/expired."""
    try:
        # Re-pad base64
        padded = token + "=" * (4 - len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        phone, expires_str, sig = raw.rsplit(":", 2)

        # Check expiry
        if int(expires_str) < int(time.time()):
            return None

        # Verify signature
        payload = f"{phone}:{expires_str}"
        expected_sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None

        return phone
    except Exception:
        return None
