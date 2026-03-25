"""
app/models/user.py
──────────────────
SQLAlchemy ORM model for the ``users`` table.

Represents a content creator account.  Passwords are always stored as
bcrypt hashes — the plain-text password is never persisted.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class User(Base):
    """
    Creator account.

    Attributes:
        id:               Auto-increment primary key (MySQL BIGINT).
        email:            Unique email used for login.
        hashed_password:  bcrypt hash of the creator's password.
        name:             Display name shown in the dashboard.
        channel:          YouTube / Patreon channel name.
        plan:             Subscription tier — "free" | "pro" | "enterprise".
        avatar_initials:  Two-letter abbreviation shown in the nav avatar.
        is_active:        Soft-delete flag; False = account disabled.
        created_at:       UTC timestamp set on insert.
        polls:            Lazy-loaded list of polls owned by this user.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    avatar_initials: Mapped[str] = mapped_column(String(4), default="??", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────
    polls: Mapped[list["Poll"]] = relationship(  # type: ignore[name-defined]
        "Poll", back_populates="owner", cascade="all, delete-orphan"
    )
