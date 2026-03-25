"""
app/services/auth_service.py
────────────────────────────
Business logic for creator authentication.

Design Pattern : Service Layer — isolates auth logic from the HTTP layer
                 so it can be tested without FastAPI or HTTP concerns.
Principle       : Single Responsibility — this module only handles auth.
"""

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.poll import Poll
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut


class AuthService:
    """
    Handles creator login and profile retrieval.

    All methods accept a SQLAlchemy Session injected from the FastAPI
    dependency, keeping the service transport-agnostic.
    """

    def authenticate(self, db: Session, payload: LoginRequest) -> TokenResponse:
        """
        Validate credentials and return a JWT access token.

        Args:
            db:      Active database session.
            payload: Email + password from the login form.

        Returns:
            A TokenResponse containing the signed JWT.

        Raises:
            ValueError: If the email is unknown or the password is wrong.
        """
        user = db.query(User).filter(User.email == payload.email).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise ValueError("Invalid email or password")
        if not user.is_active:
            raise ValueError("Account is disabled")

        token = create_access_token(subject=user.id)
        return TokenResponse(access_token=token)

    def get_me(self, db: Session, user_id: int) -> UserOut:
        """
        Return the authenticated creator's profile with computed stats.

        Args:
            db:      Active database session.
            user_id: PK of the authenticated user from the JWT sub claim.

        Returns:
            UserOut with aggregated poll statistics.

        Raises:
            LookupError: If the user no longer exists.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise LookupError("User not found")

        polls = db.query(Poll).filter(Poll.owner_id == user_id).all()
        poll_ids = [p.id for p in polls]

        # Use a single COUNT query instead of N queries (one per poll).
        # The old code re-fetched each poll and loaded all Vote objects
        # just to call __len__() — an N+1 query bug.
        from sqlalchemy import func
        from app.models.vote import Vote
        total_votes = 0
        if poll_ids:
            total_votes = db.query(func.count(Vote.id)).filter(
                Vote.poll_id.in_(poll_ids)
            ).scalar() or 0

        active_polls = sum(1 for p in polls if p.status == "active")

        return UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            channel=user.channel,
            plan=user.plan,
            avatar_initials=user.avatar_initials,
            stats={
                "total_polls": len(polls),
                "total_responses": total_votes,
                "active_polls": active_polls,
                "validated_topics": len([p for p in polls if p.status == "closed"]),
            },
        )

    def register(self, db: Session, name: str, email: str, password: str) -> User:
        """
        Create a new creator account.

        Args:
            db:       Active database session.
            name:     Creator display name.
            email:    Unique email address.
            password: Plain-text password (will be hashed before storage).

        Returns:
            The newly created and committed User ORM object.

        Raises:
            ValueError: If the email is already registered.
        """
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("Email already registered")

        initials = "".join(w[0].upper() for w in name.split()[:2]) or "??"
        user = User(
            email=email,
            hashed_password=hash_password(password),
            name=name,
            avatar_initials=initials,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


# ── Module-level singleton ─────────────────────────────────────
auth_service = AuthService()
