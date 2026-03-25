"""
app/models/vote.py
──────────────────
SQLAlchemy ORM model for the ``votes`` table.

A Vote represents one fan's complete submission for a Poll (the envelope).
Individual per-question responses are stored in the ``answers`` table.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Vote(Base):
    """
    One fan's complete submission for a Poll.

    Attributes:
        id:           Auto-increment primary key.
        poll_id:      FK to ``polls.id``.
        platform:     Origin platform tag: "patreon" | "youtube" |
                      "discord" | "direct".
        submitted_at: UTC timestamp when the vote was cast.
        poll:         Back-reference to the Poll.
        answers:      List of per-question Answer objects in this vote.
    """

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    poll_id: Mapped[int] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), default="direct", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────
    poll: Mapped["Poll"] = relationship("Poll", back_populates="votes")  # type: ignore[name-defined]
    answers: Mapped[list["Answer"]] = relationship(  # type: ignore[name-defined]
        "Answer", back_populates="vote", cascade="all, delete-orphan"
    )
