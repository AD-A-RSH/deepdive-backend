"""
app/api/v1/endpoints/polls.py
──────────────────────────────
HTTP handlers for Poll and Question CRUD.

New endpoint added:
  POST /polls/{id}/toggle   → active ↔ paused
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.poll import (
    PollCreate, PollDetail, PollUpdate,
    QuestionCreate, QuestionOut, QuestionUpdate, ReorderRequest,
)
from app.services.poll_service import poll_service

router = APIRouter(prefix="/polls", tags=["Polls"])


# ── Poll CRUD ──────────────────────────────────────────────────

@router.get("", response_model=List[Any], status_code=status.HTTP_200_OK)
def list_polls(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all polls owned by the authenticated creator."""
    return poll_service.list_polls(db, current_user.id)


@router.post("", response_model=PollDetail, status_code=status.HTTP_201_CREATED)
def create_poll(payload: PollCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new poll with nested questions and options."""
    try:
        poll = poll_service.create_poll(db, current_user.id, payload)
        return _enrich(db, poll)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{poll_id}", response_model=PollDetail, status_code=status.HTTP_200_OK)
def get_poll(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return a single poll with all questions and options."""
    try:
        return _enrich(db, poll_service.get_poll(db, poll_id, current_user.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch("/{poll_id}", response_model=PollDetail, status_code=status.HTTP_200_OK)
def update_poll(poll_id: int, payload: PollUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Partially update a poll."""
    try:
        return _enrich(db, poll_service.update_poll(db, poll_id, current_user.id, payload))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.delete("/{poll_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poll(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Hard-delete a poll.

    Auto-closes the poll first so in-flight voters see "closed"
    instead of a 404.  All questions, options, votes, and answers
    are deleted via CASCADE.
    """
    try:
        poll_service.delete_poll(db, poll_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/{poll_id}/publish", response_model=PollDetail, status_code=status.HTTP_200_OK)
def publish_poll(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Activate a poll (draft→active or paused→active)."""
    try:
        return _enrich(db, poll_service.publish_poll(db, poll_id, current_user.id))
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/{poll_id}/close", response_model=PollDetail, status_code=status.HTTP_200_OK)
def close_poll(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently close a poll (cannot be reopened)."""
    try:
        return _enrich(db, poll_service.close_poll(db, poll_id, current_user.id))
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/{poll_id}/toggle", response_model=PollDetail, status_code=status.HTTP_200_OK)
def toggle_poll(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Toggle a poll between active and paused.

    active  → paused  (temporarily stops accepting votes)
    paused  → active  (resumes accepting votes)

    Unlike close, this is reversible.
    """
    try:
        return _enrich(db, poll_service.toggle_active(db, poll_id, current_user.id))
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# ── Question sub-resource ──────────────────────────────────────

@router.get("/{poll_id}/questions", response_model=List[QuestionOut])
def list_questions(poll_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return poll_service.list_questions(db, poll_id, current_user.id)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{poll_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(poll_id: int, payload: QuestionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return poll_service.create_question(db, poll_id, current_user.id, payload)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{poll_id}/questions/{question_id}", response_model=QuestionOut)
def update_question(poll_id: int, question_id: int, payload: QuestionUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return poll_service.update_question(db, poll_id, question_id, current_user.id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.delete("/{poll_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(poll_id: int, question_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        poll_service.delete_question(db, poll_id, question_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{poll_id}/questions/reorder", response_model=List[QuestionOut])
def reorder_questions(poll_id: int, payload: ReorderRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return poll_service.reorder_questions(db, poll_id, current_user.id, payload)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Helper ─────────────────────────────────────────────────────

def _enrich(db, poll) -> dict:
    """Convert Poll ORM → PollDetail response dict with total_votes."""
    from sqlalchemy import func
    from app.models.vote import Vote
    total_votes = db.query(func.count(Vote.id)).filter(Vote.poll_id == poll.id).scalar() or 0
    return {
        "id": poll.id, "title": poll.title, "description": poll.description,
        "status": poll.status, "total_votes": total_votes,
        "created_at": poll.created_at, "share_url": poll.share_url,
        "audience_size": poll.audience_size, "questions": poll.questions,
    }
