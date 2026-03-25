"""
app/models/option.py
────────────────────
SQLAlchemy ORM model for the ``options`` table.

Each row is one selectable answer choice for a choice-type Question.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Option(Base):
    """
    A selectable answer option belonging to a choice-type Question.

    Attributes:
        id:          Auto-increment primary key.
        question_id: FK to ``questions.id``.
        order:       1-based display order within the question.
        text:        The option label shown to the fan.
        question:    Back-reference to the owning Question.
    """

    __tablename__ = "options"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    text: Mapped[str] = mapped_column(String(512), nullable=False)

    # ── Relationships ─────────────────────────────────
    question: Mapped["Question"] = relationship("Question", back_populates="options")  # type: ignore[name-defined]
