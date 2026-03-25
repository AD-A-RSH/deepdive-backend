"""
app/api/v1/endpoints/analytics.py
───────────────────────────────────
HTTP handlers for poll analytics (Insights.jsx).

Endpoints:
  GET /analytics/{poll_id}/summary   → full analytics payload (JSON)
  GET /analytics/{poll_id}/export    → single poll CSV export
  GET /analytics/export/all          → ALL polls for this creator in one CSV
"""

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.poll import Poll
from app.models.user import User
from app.models.vote import Vote
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ── SUMMARY ────────────────────────────────────────────────────

@router.get("/{poll_id}/summary", response_model=AnalyticsSummary, status_code=status.HTTP_200_OK)
def get_summary(
    poll_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full analytics payload for Insights.jsx."""
    try:
        return analytics_service.get_summary(db, poll_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# ── SINGLE POLL CSV EXPORT ─────────────────────────────────────

@router.get("/{poll_id}/export", status_code=status.HTTP_200_OK)
def export_csv(
    poll_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export a single poll's full analytics as a rich CSV.

    Sections in the CSV:
      1. Poll Summary    — meta + intelligence metrics
      2. Platform Breakdown — votes per platform
      3. Question Results   — option votes + % per question
      4. Text Responses     — open-ended answers with platform tag
    """
    try:
        summary = analytics_service.get_summary(db, poll_id, current_user.id)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    csv_bytes = _build_single_poll_csv(summary, poll)
    filename  = _safe_filename(poll.title if poll else f"poll_{poll_id}")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}_insights.csv"',
            "Content-Length": str(len(csv_bytes)),
        },
    )


# ── ALL POLLS CSV EXPORT ───────────────────────────────────────

@router.get("/export/all", status_code=status.HTTP_200_OK)
def export_all_polls_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export analytics for ALL polls owned by this creator in one CSV file.

    The CSV is structured in clearly labelled sections:

      ► EXPORT HEADER   — creator name, export date, total polls
      ► POLL OVERVIEW   — one row per poll: title, status, votes, rate, confidence, risk
      ► QUESTION RESULTS (per poll, per question)
          — option, votes, percentage
      ► PLATFORM BREAKDOWN (per poll)
          — platform, votes, percentage of total
      ► TEXT RESPONSES (per poll, per text question)
          — question, response text, platform, submitted_at

    Polls with zero votes are included in the overview but skipped in
    question/platform sections (no data to show).
    """
    # Fetch all polls for this creator
    polls = (
        db.query(Poll)
        .filter(Poll.owner_id == current_user.id)
        .order_by(Poll.created_at.desc())
        .all()
    )

    if not polls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No polls found for this account.",
        )

    # Build analytics for each poll that has votes
    summaries = {}
    for poll in polls:
        vote_count = db.query(func.count(Vote.id)).filter(Vote.poll_id == poll.id).scalar() or 0
        if vote_count > 0:
            try:
                summaries[poll.id] = analytics_service.get_summary(db, poll.id, current_user.id)
            except Exception:
                pass  # Skip polls with errors gracefully

    csv_bytes = _build_all_polls_csv(polls, summaries, current_user)
    export_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="deepdive_all_polls_{export_date}.csv"',
            "Content-Length": str(len(csv_bytes)),
        },
    )


# ── CSV BUILDERS ───────────────────────────────────────────────

def _build_single_poll_csv(summary: AnalyticsSummary, poll) -> bytes:
    """
    Build a rich CSV for one poll.

    Structure:
      Section 1: POLL SUMMARY
      Section 2: PLATFORM BREAKDOWN
      Section 3: QUESTION RESULTS (choice questions)
      Section 4: TEXT RESPONSES (open-ended)
    """
    output = io.StringIO()
    w = csv.writer(output)
    blank = lambda: w.writerow([])

    # ─── Section 1: POLL SUMMARY ──────────────────────────────
    w.writerow(["POLL SUMMARY"])
    w.writerow(["Field", "Value"])
    w.writerow(["Poll Title",       poll.title if poll else f"Poll {summary.poll_id}"])
    w.writerow(["Poll Status",      poll.status if poll else "—"])
    w.writerow(["Total Votes",      summary.total_votes])
    w.writerow(["Audience Size",    summary.audience_size])
    w.writerow(["Response Rate",    f"{round(summary.response_rate * 100, 1)}%"])
    w.writerow(["Confidence Level", summary.confidence_level])
    w.writerow(["Decision Risk",    summary.risk_level])
    w.writerow(["Risk Reason",      summary.risk_reason])
    w.writerow(["Top Platform",     summary.top_platform])
    w.writerow(["AI Recommendation",summary.recommendation])
    w.writerow(["Insight Summary",  summary.insight_summary])
    w.writerow(["Export Date",      datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    blank()

    # ─── Section 2: PLATFORM BREAKDOWN ────────────────────────
    if summary.source_breakdown:
        w.writerow(["PLATFORM BREAKDOWN"])
        w.writerow(["Platform", "Votes", "% of Total"])
        total = summary.total_votes or 1
        sb = summary.source_breakdown
        for platform, count in [
            ("YouTube",  sb.youtube),
            ("Patreon",  sb.patreon),
            ("Discord",  sb.discord),
            ("Other",    sb.other),
        ]:
            if count > 0:
                w.writerow([platform, count, f"{round(count / total * 100, 1)}%"])
        blank()

    # ─── Section 3: QUESTION RESULTS ──────────────────────────
    choice_qs = [q for q in summary.questions if q.results]
    if choice_qs:
        w.writerow(["QUESTION RESULTS"])
        w.writerow(["Question", "Option", "Votes", "% of Responses", "Question Type"])
        for q in choice_qs:
            for r in sorted(q.results, key=lambda x: x.votes, reverse=True):
                w.writerow([
                    q.text,
                    r.text,
                    r.votes,
                    f"{r.pct}%",
                    q.type.replace("_", " ").title(),
                ])
        blank()

    # ─── Section 4: TEXT RESPONSES ────────────────────────────
    text_qs = [q for q in summary.questions if q.sample_responses]
    if text_qs:
        w.writerow(["TEXT RESPONSES"])
        w.writerow(["Question", "Response", "Platform", "Submitted At"])
        for q in text_qs:
            for r in q.sample_responses:
                w.writerow([
                    q.text,
                    r.get("text", ""),
                    r.get("platform", "—"),
                    r.get("submitted_at", "—"),
                ])

    return output.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility


def _build_all_polls_csv(polls, summaries: dict, user) -> bytes:
    """
    Build a multi-section CSV covering all polls.
    """
    output = io.StringIO()
    w = csv.writer(output)
    blank = lambda: w.writerow([])
    divider = lambda label: (blank(), w.writerow([f"{'='*6} {label} {'='*6}"]), blank())

    # ─── EXPORT HEADER ────────────────────────────────────────
    w.writerow(["DeepDive R&D — Full Poll Export"])
    w.writerow(["Creator",     user.name or user.email])
    w.writerow(["Export Date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    w.writerow(["Total Polls", len(polls)])
    w.writerow(["Polls With Responses", len(summaries)])
    blank()

    # ─── SECTION 1: POLL OVERVIEW ─────────────────────────────
    divider("SECTION 1: POLL OVERVIEW")
    w.writerow([
        "Poll Title", "Status", "Total Votes", "Audience Size",
        "Response Rate", "Confidence", "Risk", "Top Platform", "Created At"
    ])

    for poll in polls:
        s = summaries.get(poll.id)
        if s:
            w.writerow([
                poll.title,
                poll.status.upper(),
                s.total_votes,
                s.audience_size,
                f"{round(s.response_rate * 100, 1)}%",
                s.confidence_level,
                s.risk_level,
                s.top_platform,
                poll.created_at.strftime("%Y-%m-%d") if poll.created_at else "—",
            ])
        else:
            w.writerow([
                poll.title,
                poll.status.upper(),
                0,
                poll.audience_size or 0,
                "0%",
                "—", "—", "—",
                poll.created_at.strftime("%Y-%m-%d") if poll.created_at else "—",
            ])

    blank()

    # ─── SECTION 2: QUESTION RESULTS PER POLL ─────────────────
    divider("SECTION 2: QUESTION RESULTS (Choice Questions)")
    w.writerow([
        "Poll Title", "Question #", "Question Text", "Question Type",
        "Option", "Votes", "% of Responses"
    ])

    for poll in polls:
        s = summaries.get(poll.id)
        if not s:
            continue
        choice_qs = [q for q in s.questions if q.results]
        for qi, q in enumerate(choice_qs, 1):
            for r in sorted(q.results, key=lambda x: x.votes, reverse=True):
                w.writerow([
                    poll.title,
                    f"Q{qi}",
                    q.text,
                    q.type.replace("_", " ").title(),
                    r.text,
                    r.votes,
                    f"{r.pct}%",
                ])

    blank()

    # ─── SECTION 3: PLATFORM BREAKDOWN PER POLL ───────────────
    divider("SECTION 3: PLATFORM BREAKDOWN")
    w.writerow(["Poll Title", "Platform", "Votes", "% of Total Votes"])

    for poll in polls:
        s = summaries.get(poll.id)
        if not s or not s.source_breakdown:
            continue
        total = s.total_votes or 1
        sb = s.source_breakdown
        for platform, count in [
            ("YouTube",  sb.youtube),
            ("Patreon",  sb.patreon),
            ("Discord",  sb.discord),
            ("Other",    sb.other),
        ]:
            if count > 0:
                w.writerow([
                    poll.title,
                    platform,
                    count,
                    f"{round(count / total * 100, 1)}%",
                ])

    blank()

    # ─── SECTION 4: TEXT RESPONSES PER POLL ───────────────────
    divider("SECTION 4: TEXT RESPONSES (Open-Ended)")
    w.writerow(["Poll Title", "Question", "Response", "Platform", "Submitted At"])

    for poll in polls:
        s = summaries.get(poll.id)
        if not s:
            continue
        text_qs = [q for q in s.questions if q.sample_responses]
        for q in text_qs:
            for r in q.sample_responses:
                w.writerow([
                    poll.title,
                    q.text,
                    r.get("text", ""),
                    r.get("platform", "—"),
                    r.get("submitted_at", "—"),
                ])

    # ─── SECTION 5: AI RECOMMENDATIONS PER POLL ───────────────
    divider("SECTION 5: AI RECOMMENDATIONS")
    w.writerow(["Poll Title", "Recommendation", "Insight Summary"])

    for poll in polls:
        s = summaries.get(poll.id)
        if not s:
            continue
        w.writerow([poll.title, s.recommendation, s.insight_summary])

    return output.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel BOM


def _safe_filename(title: str) -> str:
    """Convert poll title to a safe ASCII filename."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    return safe.strip().replace(" ", "_")[:60]
