"""AES-GCM for social tokens, Supabase-compatible HS256 JWT for admin, HMAC for webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from hotelpilot.core.config import get_settings

OPERATOR_ROLE = "operator"


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(get_settings().aes_key()).encrypt(nonce, plaintext.encode(), b"hotelpilot")
    return base64.b64encode(nonce + ct).decode()


def decrypt(token_enc: str) -> str:
    raw = base64.b64decode(token_enc)
    return AESGCM(get_settings().aes_key()).decrypt(raw[:12], raw[12:], b"hotelpilot").decode()


def issue_operator_jwt(subject: str = "operator", ttl_s: int = 12 * 3600) -> str:
    """Same shape as a Supabase Auth access token with app_metadata.role = operator."""
    now = int(time.time())
    claims = {
        "sub": subject,
        "role": "authenticated",
        "aud": "authenticated",
        "app_metadata": {"role": OPERATOR_ROLE},
        "iat": now,
        "exp": now + ttl_s,
    }
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")


def verify_operator_jwt(token: str) -> dict[str, Any]:
    """Raises PermissionError unless the token is valid and carries the operator role."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise PermissionError(f"invalid token: {e}") from e
    role = (claims.get("app_metadata") or {}).get("role") or claims.get("user_role")
    if role != OPERATOR_ROLE:
        raise PermissionError("operator role required")
    return dict(claims)


def check_password(given: str) -> bool:
    return hmac.compare_digest(given.encode(), get_settings().admin_password.get_secret_value().encode())


def sign_body(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
