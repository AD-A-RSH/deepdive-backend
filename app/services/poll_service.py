"""
app/services/poll_service.py
────────────────────────────
Business logic for poll and question CRUD.

Changes in this version:
  - toggle_active()  : pauses an active poll (active→paused) or
                       resumes a paused poll (paused→active)
  - delete_poll()    : auto-closes before deleting so any in-flight
                       voters get a "closed" message
  - publish_poll()   : now also resumes paused polls (paused→active)
  - close_poll()     : works on active AND paused polls
  - Status flow:  draft → active ⇄ paused → closed → (deleted)
"""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.option import Option
from app.models.poll import Poll
from app.models.question import Question
from app.models.vote import Vote
from app.schemas.poll import PollCreate, PollUpdate, QuestionCreate, QuestionUpdate, ReorderRequest


class PollService:

    # ── Poll CRUD ──────────────────────────────────────────────

    def list_polls(self, db: Session, owner_id: int) -> List[dict]:
        """Return all polls for a creator with computed aggregate fields."""
        polls = (
            db.query(Poll)
            .filter(Poll.owner_id == owner_id)
            .order_by(Poll.created_at.desc())
            .all()
        )
        result = []
        for p in polls:
            vote_count = db.query(func.count(Vote.id)).filter(Vote.poll_id == p.id).scalar() or 0
            result.append({
                "id":             p.id,
                "title":          p.title,
                "description":    p.description,
                "status":         p.status,
                "total_votes":    vote_count,
                "question_count": len(p.questions),
                "created_at":     p.created_at,
                "closes_at":      p.closes_at,
                "share_url":      p.share_url,
                "audience_size":  p.audience_size,
                "platforms":      [],
            })
        return result

    def get_poll(self, db: Session, poll_id: int, owner_id: int) -> Poll:
        """
        Fetch a single poll with its questions and options.

        Raises:
            LookupError:     Poll does not exist.
            PermissionError: Poll belongs to a different creator.
        """
        poll = db.query(Poll).filter(Poll.id == poll_id).first()
        if not poll:
            raise LookupError(f"Poll {poll_id} not found")
        if poll.owner_id != owner_id:
            raise PermissionError("Not authorised to access this poll")
        return poll

    def create_poll(self, db: Session, owner_id: int, payload: PollCreate) -> Poll:
        """
        Create a poll with nested questions and options.

        Poll starts as 'active' so fans can vote immediately.
        share_url uses the numeric poll.id (/vote/<id>).
        """
        poll = Poll(
            owner_id=owner_id,
            title=payload.title,
            description=payload.description,
            status="active",
            share_url=None,
            audience_size=payload.audience_size,
        )
        db.add(poll)
        db.flush()

        frontend_origin = settings.ALLOWED_ORIGINS.split(",")[0].strip()
        poll.share_url = f"{frontend_origin}/vote/{poll.id}"

        for q_data in payload.questions:
            question = Question(
                poll_id=poll.id,
                order=q_data.order,
                type=q_data.type,
                text=q_data.text,
                required=q_data.required,
            )
            db.add(question)
            db.flush()
            for o_data in q_data.options:
                db.add(Option(question_id=question.id, order=o_data.order, text=o_data.text))

        db.commit()
        db.refresh(poll)
        return poll

    def update_poll(self, db: Session, poll_id: int, owner_id: int, payload: PollUpdate) -> Poll:
        """Partially update a poll (PATCH semantics)."""
        poll = self.get_poll(db, poll_id, owner_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(poll, field, value)
        db.commit()
        db.refresh(poll)
        return poll

    def delete_poll(self, db: Session, poll_id: int, owner_id: int) -> None:
        """
        Hard-delete a poll and all its cascading children.

        Auto-closes the poll first so any fans who have the link
        open will see "poll is closed" rather than a 404.
        The close timestamp is recorded before deletion.

        Args:
            db:       Active database session.
            poll_id:  PK of the poll to delete.
            owner_id: Ownership guard.
        """
        poll = self.get_poll(db, poll_id, owner_id)
        # Auto-close before deleting — protects in-flight voters
        if poll.status in ("active", "paused"):
            poll.status    = "closed"
            poll.closes_at = datetime.now(timezone.utc)
            db.flush()
        db.delete(poll)
        db.commit()

    def publish_poll(self, db: Session, poll_id: int, owner_id: int) -> Poll:
        """
        Activate a poll (draft→active or paused→active).

        Raises:
            ValueError: Poll is already closed — closed polls cannot be reopened.
        """
        poll = self.get_poll(db, poll_id, owner_id)
        if poll.status == "closed":
            raise ValueError("Cannot reopen a closed poll. Closed polls are permanent.")
        poll.status = "active"
        db.commit()
        db.refresh(poll)
        return poll

    def close_poll(self, db: Session, poll_id: int, owner_id: int) -> Poll:
        """
        Permanently close a poll (active or paused → closed).

        Closed polls cannot accept new votes and cannot be reopened.
        Use toggle_active() for temporary pausing instead.

        Raises:
            ValueError: Poll is already closed.
        """
        poll = self.get_poll(db, poll_id, owner_id)
        if poll.status == "closed":
            raise ValueError("Poll is already closed")
        poll.status    = "closed"
        poll.closes_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(poll)
        return poll

    def toggle_active(self, db: Session, poll_id: int, owner_id: int) -> Poll:
        """
        Toggle a poll between 'active' and 'paused'.

        Paused polls stop accepting new votes but are not permanently
        closed — the creator can resume them at any time.

        Status transitions:
          active → paused   (fan vote page shows "temporarily paused")
          paused → active   (voting resumes)

        Raises:
            ValueError: Poll is not in active or paused state.
        """
        poll = self.get_poll(db, poll_id, owner_id)
        if poll.status == "active":
            poll.status = "paused"
        elif poll.status == "paused":
            poll.status = "active"
        else:
            raise ValueError(
                f"Cannot toggle a poll with status '{poll.status}'. "
                "Only active and paused polls can be toggled."
            )
        db.commit()
        db.refresh(poll)
        return poll

    # ── Question CRUD ──────────────────────────────────────────

    def list_questions(self, db: Session, poll_id: int, owner_id: int) -> List[Question]:
        """Return all questions for a poll (ownership verified)."""
        poll = self.get_poll(db, poll_id, owner_id)
        return poll.questions

    def create_question(
        self, db: Session, poll_id: int, owner_id: int, payload: QuestionCreate
    ) -> Question:
        """Append a new question (with options) to an existing poll."""
        self.get_poll(db, poll_id, owner_id)
        max_order = (
            db.query(func.max(Question.order))
            .filter(Question.poll_id == poll_id)
            .scalar() or 0
        )
        question = Question(
            poll_id=poll_id,
            order=max_order + 1,
            type=payload.type,
            text=payload.text,
            required=payload.required,
        )
        db.add(question)
        db.flush()
        for o in payload.options:
            db.add(Option(question_id=question.id, order=o.order, text=o.text))
        db.commit()
        db.refresh(question)
        return question

    def update_question(
        self, db: Session, poll_id: int, question_id: int, owner_id: int, payload: QuestionUpdate
    ) -> Question:
        """Partially update a question."""
        self.get_poll(db, poll_id, owner_id)
        question = db.query(Question).filter(
            Question.id == question_id, Question.poll_id == poll_id
        ).first()
        if not question:
            raise LookupError("Question not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(question, field, value)
        db.commit()
        db.refresh(question)
        return question

    def delete_question(
        self, db: Session, poll_id: int, question_id: int, owner_id: int
    ) -> None:
        """Delete a question and its options."""
        self.get_poll(db, poll_id, owner_id)
        question = db.query(Question).filter(
            Question.id == question_id, Question.poll_id == poll_id
        ).first()
        if not question:
            raise LookupError("Question not found")
        db.delete(question)
        db.commit()

    def reorder_questions(
        self, db: Session, poll_id: int, owner_id: int, payload: ReorderRequest
    ) -> List[Question]:
        """Update the display order of questions in bulk."""
        self.get_poll(db, poll_id, owner_id)
        for new_order, q_id in enumerate(payload.order, start=1):
            db.query(Question).filter(
                Question.id == q_id, Question.poll_id == poll_id
            ).update({"order": new_order})
        db.commit()
        return self.list_questions(db, poll_id, owner_id)


poll_service = PollService()
