"""
app/models/poll.py
──────────────────
SQLAlchemy ORM model for the ``polls`` table.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Poll(Base):
    """
    A creator's poll (survey instrument).

    Attributes:
        id:             Auto-increment primary key.
        owner_id:       FK to ``users.id`` — the creator who owns this poll.
        title:          Human-readable poll title shown to fans.
        description:    Optional longer description shown on the fan-vote page.
        status:         Lifecycle state: "draft" | "active" | "closed".
        share_url:      Public URL fans use to cast their vote.
        audience_size:  Creator's estimated total audience (used to compute
                        response_rate = total_votes / audience_size).
        created_at:     UTC creation timestamp.
        closes_at:      Optional UTC close timestamp; NULL means no expiry.
        owner:          Back-reference to the owning User.
        questions:      Ordered list of Question objects in this poll.
        votes:          All Vote records cast for this poll.
    """

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    share_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audience_size: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────
    owner: Mapped["User"] = relationship("User", back_populates="polls")  # type: ignore[name-defined]
    questions: Mapped[list["Question"]] = relationship(  # type: ignore[name-defined]
        "Question", back_populates="poll", cascade="all, delete-orphan",
        order_by="Question.order",
    )
    votes: Mapped[list["Vote"]] = relationship(  # type: ignore[name-defined]
        "Vote", back_populates="poll", cascade="all, delete-orphan"
    )
