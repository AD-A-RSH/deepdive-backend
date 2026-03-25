"""
app/schemas/poll.py
───────────────────
Pydantic schemas for Poll, Question, and Option CRUD operations.

Enhanced: PollCreate and PollUpdate now include audience_size.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ─── Option ───────────────────────────────────────────────────

class OptionBase(BaseModel):
    text: str
    order: int = 1


class OptionCreate(OptionBase):
    """Payload for creating one answer option."""
    pass


class OptionOut(OptionBase):
    """Option as returned in API responses."""
    id: int
    model_config = {"from_attributes": True}


# ─── Question ─────────────────────────────────────────────────

class QuestionBase(BaseModel):
    type: str
    text: str
    order: int = 1
    required: bool = True


class QuestionCreate(QuestionBase):
    """Payload for creating one question, optionally with its options."""
    options: List[OptionCreate] = []


class QuestionUpdate(BaseModel):
    """All fields are optional for PATCH semantics."""
    type: Optional[str] = None
    text: Optional[str] = None
    order: Optional[int] = None
    required: Optional[bool] = None


class QuestionOut(QuestionBase):
    """Question as returned in API responses, including nested options."""
    id: int
    poll_id: int
    options: List[OptionOut] = []
    model_config = {"from_attributes": True}


# ─── Poll ─────────────────────────────────────────────────────

class PollBase(BaseModel):
    title: str
    description: Optional[str] = None
    audience_size: int = Field(default=1000, ge=1, description="Creator's estimated audience size")


class PollCreate(PollBase):
    """
    Payload sent by PollBuilder.jsx on Save & Publish.

    audience_size is required to enable response rate / confidence / risk
    computation in the analytics engine.
    """
    questions: List[QuestionCreate] = []


class PollUpdate(BaseModel):
    """All fields optional — used by PATCH /polls/{id}."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    closes_at: Optional[datetime] = None
    audience_size: Optional[int] = Field(default=None, ge=1)


class PollListItem(PollBase):
    """Compact poll representation used in Dashboard.jsx poll list."""
    id: int
    status: str
    total_votes: int
    question_count: int
    created_at: datetime
    closes_at: Optional[datetime]
    share_url: Optional[str]
    platforms: List[str] = []
    model_config = {"from_attributes": True}


class PollDetail(PollBase):
    """
    Full poll representation including nested questions + options.

    Used by PollBuilder (edit mode) and FanVote.jsx.
    """
    id: int
    status: str
    total_votes: int
    created_at: datetime
    share_url: Optional[str]
    questions: List[QuestionOut] = []
    model_config = {"from_attributes": True}


# ─── Question reorder ─────────────────────────────────────────

class ReorderRequest(BaseModel):
    """Body for POST /polls/{id}/questions/reorder."""
    order: List[int]
