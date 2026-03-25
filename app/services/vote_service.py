"""
app/services/vote_service.py
────────────────────────────
Business logic for fan vote submission (public, no auth required).

Fixes applied:
  - get_public_poll now accepts both 'draft' and 'active' so "Preview Fan View"
    works on newly-created polls without requiring a publish step first.
  - submit_vote still enforces 'active'-only to prevent votes on draft polls.
  - question_id values from the frontend arrive as strings (from Object.entries);
    they are coerced to int before the q_map lookup so answers are never silently
    dropped.
"""

import json
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.poll import Poll
from app.models.question import Question
from app.models.vote import Vote
from app.schemas.analytics import VoteSubmit, VoteOut


class VoteService:
    """
    Handles public fan-vote display and submission.

    No authentication is required — these endpoints are called from
    the fan-facing FanVote.jsx page.
    """

    def get_public_poll(self, db: Session, poll_id: int) -> Poll:
        """
        Fetch a poll for the public fan-vote / preview page.

        Accepts polls in 'draft' OR 'active' status so that creators can
        preview the fan experience immediately after creating a poll — before
        they hit the Publish button.  Closed polls are still rejected.

        Args:
            db:      Active database session.
            poll_id: Numeric primary key of the poll.

        Returns:
            The Poll ORM object with questions and options eagerly loaded.

        Raises:
            LookupError: Poll does not exist or has been closed.
        """
        poll = db.query(Poll).filter(Poll.id == poll_id).first()
        if not poll:
            raise LookupError("Poll not found")
        if poll.status == "closed":
            raise LookupError("This poll has been closed and is no longer accepting responses.")
        return poll  # draft and paused are viewable; submit_vote blocks paused

    def submit_vote(self, db: Session, poll_id: int, payload: VoteSubmit) -> VoteOut:
        """
        Persist a fan's complete vote submission.

        Enforces that only 'active' polls accept votes — draft polls can be
        previewed but not voted on.

        question_id values from the frontend are coerced to int because
        JavaScript's Object.entries() always produces string keys, which would
        silently fail the dict lookup if left as strings.

        Args:
            db:       Active database session.
            poll_id:  Numeric PK from the URL path.
            payload:  Validated VoteSubmit schema from the request body.

        Returns:
            VoteOut with the new vote's id and submitted_at timestamp.

        Raises:
            LookupError: Poll not found or not active.
            ValueError:  Required questions have no answers in the payload.
        """
        # Load poll — must be active to accept votes
        poll = db.query(Poll).filter(Poll.id == poll_id).first()
        if not poll:
            raise LookupError("Poll not found")
        if poll.status not in ("active",):
            raise LookupError(
                "This poll is not currently accepting votes. "
                "It may be paused or not yet published."
            )

        # Build question lookup — coerce IDs to int defensively
        q_map: dict[int, Question] = {q.id: q for q in poll.questions}

        # Coerce question_id strings → int (JS Object.entries gives strings)
        answered_ids = set()
        for a in payload.answers:
            try:
                answered_ids.add(int(a.question_id))
            except (ValueError, TypeError):
                pass

        # Validate all required questions are answered
        missing = [
            q.text for q in poll.questions
            if q.required and q.id not in answered_ids
        ]
        if missing:
            raise ValueError(f"Required questions unanswered: {missing}")

        # Persist vote envelope
        vote = Vote(poll_id=poll_id, platform=payload.platform)
        db.add(vote)
        db.flush()  # Populate vote.id before inserting answers

        # Persist individual answers
        for answer_in in payload.answers:
            try:
                q_id = int(answer_in.question_id)
            except (ValueError, TypeError):
                continue
            if q_id not in q_map:
                continue  # Ignore unknown question IDs gracefully
            value = (
                json.dumps(answer_in.value)
                if isinstance(answer_in.value, list)
                else str(answer_in.value)
            )
            db.add(Answer(
                vote_id=vote.id,
                question_id=q_id,
                value=value,
            ))

        db.commit()
        db.refresh(vote)
        return VoteOut(id=vote.id, submitted_at=vote.submitted_at)


# ── Module-level singleton ─────────────────────────────────────
vote_service = VoteService()
