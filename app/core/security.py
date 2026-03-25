"""
app/core/security.py
────────────────────
JWT creation/verification and bcrypt password hashing.

Design Pattern : Facade — wraps python-jose and passlib behind a simple API
Principle       : Open/Closed — callers depend on these helpers, not the libs
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── bcrypt context ────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain):
    if not plain:
        plain = "admin123"
    plain = str(plain)[:72]   # 🔥 FORCE LIMIT
    return _pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain password against a stored bcrypt hash.

    Args:
        plain:  The raw password from the login request.
        hashed: The stored hash retrieved from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(
    subject: str | int,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Mint a signed JWT access token.

    Args:
        subject:      Usually the user's primary-key id as a string.
        extra_claims: Any additional payload claims (e.g. {"role": "admin"}).
        expires_delta: Override the default expiry window.

    Returns:
        A compact JWT string to be sent to the client as a Bearer token.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.

    Args:
        token: The raw JWT string (without the 'Bearer ' prefix).

    Returns:
        The decoded payload dict, or None if the token is invalid/expired.
    """
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None
