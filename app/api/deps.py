"""
app/api/deps.py
───────────────
FastAPI dependency functions shared across endpoint routers.

Design Pattern : Dependency Injection — FastAPI resolves these automatically
                 when annotated with Depends(), keeping endpoint handlers clean.
Principle       : DRY — auth logic defined once, reused everywhere.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# Bearer token scheme — FastAPI will look for "Authorization: Bearer <token>"
_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the Bearer JWT and return the authenticated User ORM object.

    This dependency is injected into every protected endpoint via::

        @router.get("/protected")
        def endpoint(current_user: User = Depends(get_current_user)):
            ...

    Args:
        credentials: Bearer token extracted by HTTPBearer from the
                     Authorization header.
        db:          Active database session from get_db.

    Returns:
        The authenticated User ORM object.

    Raises:
        HTTPException 401: If the token is missing, invalid, or expired.
        HTTPException 401: If the user referenced by the token no longer exists.
        HTTPException 403: If the account has been deactivated.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user
