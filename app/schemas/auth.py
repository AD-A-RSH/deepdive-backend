"""
app/schemas/auth.py
───────────────────
Pydantic request/response schemas for authentication endpoints.

Principle: Interface Segregation — separate schemas for login, token
           response, and the "me" payload keep each contract minimal.
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Credentials submitted by the creator on the login form."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token envelope returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """
    Creator profile returned by GET /auth/me.

    Only non-sensitive fields are included — hashed_password is never exposed.
    """

    id: int
    email: str
    name: str
    channel: str | None
    plan: str
    avatar_initials: str
    stats: dict  # Computed dynamically by the auth service

    model_config = {"from_attributes": True}
