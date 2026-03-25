"""
app/schemas/analytics.py
────────────────────────
Pydantic schemas for fan-vote submission and the full analytics response.

Enhanced with:
  - audience_size / response_rate       (Audience-Aware Polling)
  - confidence_level                    (Confidence Engine)
  - risk_level / risk_reason            (Risk Analysis Engine)
  - warning_flag                        (Low Response Handling)
  - recommendation / insight_summary   (Smart Recommendation Engine)
  - source_breakdown                    (Audience Segmentation)
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


# ─── Vote submission (fan-facing) ─────────────────────────────

class AnswerIn(BaseModel):
    """One answer item in a vote submission payload."""
    question_id: int
    value: str | List[str]   # string for text/single; list for multi-choice


class VoteSubmit(BaseModel):
    """
    Body sent by FanVote.jsx on Submit Vote.

    ``platform`` is sourced from the ``?src=`` query parameter so analytics
    can segment by audience origin.
    """
    poll_id: int
    answers: List[AnswerIn]
    platform: str = "direct"


class VoteOut(BaseModel):
    """Minimal acknowledgement returned after a successful vote."""
    id: int
    submitted_at: datetime

    model_config = {"from_attributes": True}


# ─── Per-option result ────────────────────────────────────────

class OptionResult(BaseModel):
    """Vote count + percentage for one answer option."""
    option_id: Optional[int] = None
    text: str
    votes: int
    pct: float


# ─── Per-question analytics ───────────────────────────────────

class QuestionAnalytics(BaseModel):
    """
    Analytics for a single question.

    ``results`` is populated for choice questions.
    ``sample_responses`` is populated for text questions.
    """
    id: int
    text: str
    type: str
    total_responses: int
    results: List[OptionResult] = []
    sample_responses: List[Dict[str, Any]] = []


# ─── Cross-tab ────────────────────────────────────────────────

class CrosstabResult(BaseModel):
    filter_label: str
    filter_count: int
    results: List[Dict[str, Any]]


# ─── Platform breakdown ───────────────────────────────────────

class PlatformRow(BaseModel):
    """
    Per-platform top-answer row for one choice question.

    question_text and question_id allow the frontend to group
    rows by question in the cross-tabulation table.
    """
    platform: str
    votes: int
    top_topic: str
    pct_naval: int
    question_text: str = ""    # which question this row belongs to
    question_id: int = 0


# ─── Intelligence layers ──────────────────────────────────────

class SourceBreakdown(BaseModel):
    """Vote counts segmented by audience origin platform."""
    youtube: int = 0
    patreon: int = 0
    discord: int = 0
    other: int = 0


class OptionDistributionItem(BaseModel):
    """Option name + vote percentage."""
    option: str
    percentage: float


# ─── Full analytics summary ───────────────────────────────────

class AnalyticsSummary(BaseModel):
    """
    Full analytics payload consumed by Insights.jsx.

    Implements all six intelligence features from the enhancement spec.
    """

    # ── Core metrics ──────────────────────────────────────────
    poll_id: int
    total_votes: int
    completion_rate: float
    avg_time_seconds: Optional[float] = None  # None when no timing data available
    top_platform: str

    # ── Audience-Aware Polling ────────────────────────────────
    audience_size: int
    response_rate: float

    # ── Confidence Engine ─────────────────────────────────────
    confidence_level: Literal["LOW", "MEDIUM", "HIGH"]

    # ── Risk Analysis ─────────────────────────────────────────
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    risk_reason: str

    # ── Low Response Handling ─────────────────────────────────
    warning_flag: Optional[Literal["INSUFFICIENT_DATA"]] = None

    # ── Smart Recommendation Engine ───────────────────────────
    recommendation: str
    insight_summary: str

    # ── Audience Segmentation ─────────────────────────────────
    source_breakdown: SourceBreakdown
    option_distribution: List[OptionDistributionItem] = []

    # ── Question-level data ───────────────────────────────────
    questions: List[QuestionAnalytics]
    crosstab: Dict[str, CrosstabResult]
    platform_breakdown: List[PlatformRow]
