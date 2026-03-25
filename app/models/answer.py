"""
app/models/answer.py
────────────────────
SQLAlchemy ORM model for the ``answers`` table.

Each Answer is one fan's response to a single Question within a Vote.
For choice questions the value is the selected option text (or
comma-joined texts for multi-select).  For text questions it is the
raw free-form string.
"""

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Answer(Base):
    """
    A fan's response to one Question within a Vote.

    Attributes:
        id:          Auto-increment primary key.
        vote_id:     FK to ``votes.id``.
        question_id: FK to ``questions.id``.
        value:       The submitted answer value (string or JSON array).
        vote:        Back-reference to the parent Vote.
        question:    Back-reference to the answered Question.
    """

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vote_id: Mapped[int] = mapped_column(
        ForeignKey("votes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Relationships ─────────────────────────────────
    vote: Mapped["Vote"] = relationship("Vote", back_populates="answers")  # type: ignore[name-defined]
    question: Mapped["Question"] = relationship("Question", back_populates="answers")  # type: ignore[name-defined]
