"""
Security utilities — password hashing, JWT token helpers, cryptographic codes, CSRF.
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt

from app.core.exceptions import AuthenticationError


# ── Password hashing (using direct bcrypt) ───────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    # Bcrypt operates on bytes up to 72 bytes
    pwd_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        hash_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


# ── JWT helpers ──────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    from jose import jwt as jose_jwt

    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=60))
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": secrets.token_hex(16),
    })
    return jose_jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_refresh_token(
    data: dict,
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token with unique jti."""
    from jose import jwt as jose_jwt

    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=7))
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    })
    return jose_jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    """Decode and verify a JWT access or refresh token. Raises on invalid/expired."""
    from jose import JWTError, jwt as jose_jwt

    try:
        payload = jose_jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError as e:
        raise AuthenticationError(message=f"Invalid or expired token: {e}")


def decode_access_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    """Decode and verify a JWT access token. Validates type == 'access'."""
    payload = decode_token(token, secret_key, algorithm)
    if payload.get("type") != "access":
        raise AuthenticationError(message="Invalid token type, expected access token")
    return payload


# ── Cryptographic codes & nonces ─────────────────────────────────────────────

def generate_pairing_code(length: int = 6) -> str:
    """
    Generate a high-entropy, human-friendly alphanumeric pairing code.
    Excludes ambiguous characters (0, O, I, 1, L).
    """
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_nine_digit_project_code() -> str:
    """
    Generate a 9-digit project join code formatted as 'XXX-XXX-XXX'.
    Guarantees uniform randomness using secrets.randbelow.
    """
    digits = "".join(str(secrets.randbelow(10)) for _ in range(9))
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a URL-safe random string for session tokens or lease tokens."""
    return secrets.token_urlsafe(nbytes)


def generate_nonce(nbytes: int = 16) -> str:
    """Generate a random hex string for challenge nonces."""
    return secrets.token_hex(nbytes)


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a token for safe database persistence."""
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

