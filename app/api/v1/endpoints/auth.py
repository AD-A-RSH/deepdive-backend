"""
app/api/v1/endpoints/auth.py
────────────────────────────
HTTP handlers for authentication: register, login, me, refresh.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Register schema (local — keep auth schemas minimal) ───────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new creator account.

    Immediately returns a JWT so the frontend can log in without
    a separate login call after registration.
    """
    try:
        user = auth_service.register(db, payload.name, payload.email, payload.password)
        # Issue token immediately so caller can proceed without a second request
        from app.core.security import create_access_token
        token = create_access_token(subject=user.id)
        return TokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a creator and return a JWT access token.

    Returns a Bearer token stored client-side under 'dd_token'
    as expected by client.js.
    """
    try:
        return auth_service.authenticate(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Return the authenticated creator's profile and computed stats.

    Matches the shape previously provided by MOCK_CREATOR in Dashboard.jsx.
    """
    try:
        return auth_service.get_me(db, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh(current_user: User = Depends(get_current_user)):
    """Issue a fresh JWT for an already-authenticated creator."""
    from app.core.security import create_access_token
    token = create_access_token(subject=current_user.id)
    return TokenResponse(access_token=token)
