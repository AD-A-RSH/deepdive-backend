"""
app/api/v1/endpoints/votes.py
──────────────────────────────
Public, unauthenticated HTTP handlers for the fan-vote flow.

URL structure matches client.js votesApi:
  GET  /vote/{poll_id}          → get public poll for FanVote.jsx
  POST /vote/{poll_id}          → submit fan vote
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import VoteOut, VoteSubmit
from app.schemas.poll import PollDetail
from app.services.vote_service import vote_service

router = APIRouter(prefix="/vote", tags=["Fan Vote"])


@router.get("/{poll_id}", response_model=PollDetail, status_code=status.HTTP_200_OK)
def get_public_poll(poll_id: int, db: Session = Depends(get_db)):
    """
    Return a poll's public data for the FanVote.jsx page.

    No authentication required.  Returns 404 if the poll is not active.

    The response shape matches MOCK_POLL_DETAIL consumed by FanVote.jsx.
    """
    try:
        poll = vote_service.get_public_poll(db, poll_id)
        from sqlalchemy import func
        from app.models.vote import Vote

        total_votes = (
            db.query(func.count(Vote.id)).filter(Vote.poll_id == poll.id).scalar() or 0
        )
        return {
            "id": poll.id,
            "title": poll.title,
            "description": poll.description,
            "status": poll.status,
            "total_votes": total_votes,
            "created_at": poll.created_at,
            "share_url": poll.share_url,
            "audience_size": poll.audience_size,
            "questions": poll.questions,
        }
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{poll_id}", response_model=VoteOut, status_code=status.HTTP_201_CREATED)
def submit_vote(
    poll_id: int,
    payload: VoteSubmit,
    db: Session = Depends(get_db),
):
    """
    Accept a fan's complete vote submission.

    No authentication required.  The ``platform`` field should be set from
    the ``?src=`` query parameter (handled in FanVote.jsx).

    Returns a minimal VoteOut with the new vote's id and timestamp.
    """
    try:
        return vote_service.submit_vote(db, poll_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
