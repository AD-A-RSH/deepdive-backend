"""
app/models/question.py
──────────────────────
SQLAlchemy ORM model for the ``questions`` table.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Question(Base):
    """
    A single question inside a Poll.

    Attributes:
        id:        Auto-increment primary key.
        poll_id:   FK to ``polls.id``.
        order:     1-based display order within the poll.
        type:      Question type: "single_choice" | "multiple_choice" |
                   "dropdown" | "short_text" | "long_text".
        text:      The question wording shown to fans.
        required:  If True, the fan must answer before submitting.
        poll:      Back-reference to the owning Poll.
        options:   Ordered list of Option objects (empty for text questions).
        answers:   All Answer records submitted for this question.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    poll_id: Mapped[int] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ─────────────────────────────────
    poll: Mapped["Poll"] = relationship("Poll", back_populates="questions")  # type: ignore[name-defined]
    options: Mapped[list["Option"]] = relationship(  # type: ignore[name-defined]
        "Option", back_populates="question", cascade="all, delete-orphan",
        order_by="Option.order",
    )
    answers: Mapped[list["Answer"]] = relationship(  # type: ignore[name-defined]
        "Answer", back_populates="question", cascade="all, delete-orphan"
    )
