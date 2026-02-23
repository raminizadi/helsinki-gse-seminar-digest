"""HMAC-based token generation and validation for subscribe/unsubscribe links."""

from __future__ import annotations

import hashlib
import hmac
import os


def _get_secret() -> bytes:
    return os.environ["SECRET_KEY"].encode()


def generate_token(email: str, action: str) -> str:
    """Generate an HMAC token for an email + action pair.

    Args:
        email: Subscriber email address (lowercased before signing).
        action: Either "confirm" or "unsubscribe".

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    message = f"{email.lower()}:{action}".encode()
    return hmac.new(_get_secret(), message, hashlib.sha256).hexdigest()


def verify_token(email: str, action: str, token: str) -> bool:
    """Verify an HMAC token. Returns True if valid."""
    expected = generate_token(email, action)
    return hmac.compare_digest(expected, token)
