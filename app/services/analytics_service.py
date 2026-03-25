"""
app/services/analytics_service.py
──────────────────────────────────
Intelligence analytics engine for DeepDive R&D.

Changes in this version:
  - _build_crosstab()          : REMOVED hardcoded Q1×Q2 and Patreon filters.
                                  Returns empty dict — the frontend no longer
                                  shows confusing "Prefer not good (0 voters)" chips.
  - _build_platform_breakdown(): Now covers ALL choice questions, not just Q1.
                                  Returns one row per platform showing top answer
                                  for each question separately.
  - PlatformRow schema updated  : Uses question_text + question_id fields so
                                  the frontend can group rows by question.
  - All percentage calculations : Verified — pct = votes_for_option / total_votes_for_platform * 100
"""

import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.poll import Poll
from app.models.question import Question
from app.models.vote import Vote
from app.schemas.analytics import (
    AnalyticsSummary,
    CrosstabResult,
    OptionDistributionItem,
    OptionResult,
    PlatformRow,
    QuestionAnalytics,
    SourceBreakdown,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIDENCE ENGINE
# response_rate = total_votes / audience_size
# LOW < 5%  |  MEDIUM 5–20%  |  HIGH > 20%
# ─────────────────────────────────────────────────────────────────────────────

def compute_confidence(response_rate: float) -> str:
    """
    Determine confidence level based on audience response rate.

    Args:
        response_rate: total_votes / audience_size  (0.0 to 1.0+)

    Returns:
        "LOW" | "MEDIUM" | "HIGH"
    """
    if response_rate < 0.05:
        return "LOW"
    if response_rate <= 0.20:
        return "MEDIUM"
    return "HIGH"


# ─────────────────────────────────────────────────────────────────────────────
# 2. RISK ANALYSIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_risk(
    response_rate: float,
    option_distribution: List[OptionDistributionItem],
) -> Tuple[str, str]:
    """
    Evaluate decision risk using response rate and vote distribution.

    Rules:
      response_rate < 0.05                → HIGH  (too few responses)
      top option share < 45%              → MEDIUM (audience divided)
      top option share >= 55% AND rate > 10% → LOW (strong consensus)
      otherwise                           → MEDIUM

    Args:
        response_rate:       total_votes / audience_size
        option_distribution: percentages for Q1 options

    Returns:
        Tuple of (risk_level, risk_reason)
    """
    if response_rate < 0.05:
        return (
            "HIGH",
            "Too few responses relative to your audience size. "
            "Results may not reflect your actual fanbase.",
        )

    if not option_distribution:
        return ("MEDIUM", "Not enough option data to assess vote distribution.")

    top_pct = max((o.percentage for o in option_distribution), default=0.0)

    if top_pct < 45.0:
        return (
            "MEDIUM",
            "Your audience is divided — no option has a clear majority. "
            "Consider running a follow-up poll to narrow down choices.",
        )

    if top_pct >= 55.0 and response_rate > 0.10:
        return (
            "LOW",
            "Strong consensus with sufficient participation. "
            "The data supports a confident decision.",
        )

    return (
        "MEDIUM",
        "A majority preference exists but participation could be higher. "
        "Consider promoting the poll further before deciding.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. SMART RECOMMENDATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_recommendation(
    confidence_level: str,
    risk_level: str,
    response_rate: float,
    top_option: Optional[str],
) -> Tuple[str, str]:
    """
    Generate an actionable recommendation and one-line insight summary.

    Args:
        confidence_level: "LOW" | "MEDIUM" | "HIGH"
        risk_level:       "HIGH" | "MEDIUM" | "LOW"
        response_rate:    total_votes / audience_size
        top_option:       Text of the winning option (may be None)

    Returns:
        Tuple of (recommendation, insight_summary)
    """
    pct_str = f"{round(response_rate * 100, 1)}%"

    if confidence_level == "LOW":
        return (
            "Collect more data before making a decision. "
            f"Only {pct_str} of your audience has responded — "
            "share the poll in more places to increase participation.",
            f"Low participation ({pct_str} response rate). Results are not yet statistically meaningful.",
        )

    if risk_level == "HIGH":
        return (
            "This decision is high-risk. Validate further before proceeding — "
            "consider a follow-up poll with more targeted questions.",
            f"High risk detected despite {pct_str} response rate. Tread carefully.",
        )

    if risk_level == "LOW" and confidence_level == "HIGH":
        option_text = f'"{top_option}"' if top_option else "the leading option"
        return (
            f"Safe to proceed with {option_text}. "
            f"Your audience has spoken clearly — {pct_str} responded and the consensus is strong.",
            f"Strong signal: {pct_str} response rate with clear consensus on {option_text}.",
        )

    if confidence_level == "MEDIUM" and risk_level == "MEDIUM":
        return (
            "You have a directional signal but not a definitive one. "
            "Promote the poll further, then revisit the insights.",
            f"Moderate confidence ({pct_str} response rate). A directional preference is visible.",
        )

    if confidence_level == "HIGH" and risk_level == "MEDIUM":
        option_text = f'"{top_option}"' if top_option else "the leading option"
        return (
            f"Good participation, but the audience is somewhat divided. "
            f"{option_text} leads — proceed with awareness that a segment disagrees.",
            f"High participation ({pct_str}) but split audience. {option_text} leads narrowly.",
        )

    return (
        "Review the full breakdown before deciding. The data shows a mixed signal.",
        f"Mixed signal with {pct_str} response rate. More context needed.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SERVICE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService:
    """
    Orchestrates all intelligence computations for a given poll.
    """

    def get_summary(self, db: Session, poll_id: int, owner_id: int) -> AnalyticsSummary:
        """
        Build the full analytics payload consumed by Insights.jsx.

        Args:
            db:       Active database session.
            poll_id:  PK of the poll to analyse.
            owner_id: Ownership guard.

        Returns:
            AnalyticsSummary with all intelligence layers populated.

        Raises:
            LookupError:     Poll not found.
            PermissionError: Poll belongs to another creator.
        """
        poll = db.query(Poll).filter(Poll.id == poll_id).first()
        if not poll:
            raise LookupError(f"Poll {poll_id} not found")
        if poll.owner_id != owner_id:
            raise PermissionError("Not authorised to view these analytics")

        audience_size = max(poll.audience_size or 1, 1)

        # ── Fetch all votes ────────────────────────────────────
        votes: List[Vote] = db.query(Vote).filter(Vote.poll_id == poll_id).all()
        total_votes = len(votes)
        vote_ids = [v.id for v in votes]

        # ── Fetch all answers in one round-trip ────────────────
        answers: List[Answer] = []
        if vote_ids:
            answers = db.query(Answer).filter(Answer.vote_id.in_(vote_ids)).all()

        # ── Response rate (Feature 1) ──────────────────────────
        response_rate = round(total_votes / audience_size, 4)

        # ── Source breakdown (Feature 2) ──────────────────────
        source_breakdown = self._build_source_breakdown(votes)
        platform_counter: Counter = Counter(v.platform for v in votes)
        top_platform = platform_counter.most_common(1)[0][0] if votes else "N/A"

        # ── Completion rate ────────────────────────────────────
        # A vote is "complete" only if the voter answered EVERY required
        # question — not just any one of them.
        # Bug was: used a flat set of vote_ids which counted a voter as
        # complete if they answered Q1 (required) but skipped Q2 (required).
        required_q_ids = {q.id for q in poll.questions if q.required}
        if required_q_ids and vote_ids:
            # Build: vote_id → set of required question IDs that were answered
            votes_required_answered: dict = defaultdict(set)
            for a in answers:
                if a.question_id in required_q_ids and a.value.strip():
                    votes_required_answered[a.vote_id].add(a.question_id)
            # Only count votes that answered ALL required questions
            fully_complete = sum(
                1 for answered_qs in votes_required_answered.values()
                if answered_qs >= required_q_ids
            )
            completion_rate = round(fully_complete / total_votes, 2) if total_votes else 0.0
        else:
            completion_rate = 1.0

        # ── Per-question analytics ─────────────────────────────
        question_analytics: List[QuestionAnalytics] = []
        for question in sorted(poll.questions, key=lambda q: q.order):
            q_answers = [a for a in answers if a.question_id == question.id]
            qa = self._compute_question_analytics(question, q_answers, votes)
            question_analytics.append(qa)

        # ── Option distribution for risk engine ───────────────
        option_distribution = self._get_option_distribution(question_analytics)
        top_option = (
            max(option_distribution, key=lambda o: o.percentage).option
            if option_distribution else None
        )

        # ── Intelligence engines ───────────────────────────────
        confidence_level = compute_confidence(response_rate)
        risk_level, risk_reason = compute_risk(response_rate, option_distribution)
        warning_flag = "INSUFFICIENT_DATA" if response_rate < 0.05 else None
        recommendation, insight_summary = compute_recommendation(
            confidence_level, risk_level, response_rate, top_option
        )

        # ── Crosstab: REMOVED hardcoded filters ───────────────
        # Previously built "Prefer <last option of Q2>" and "Patreon backers"
        # cross-tabs that showed misleading "0 voters" on most polls.
        # The frontend no longer shows filter chips.
        crosstab: Dict[str, CrosstabResult] = {}

        # ── Platform breakdown (all questions) ────────────────
        platform_rows = self._build_platform_breakdown(poll, votes, answers)

        return AnalyticsSummary(
            poll_id=poll_id,
            total_votes=total_votes,
            completion_rate=completion_rate,
            avg_time_seconds=None,  # No submission timing data is collected yet.
                                    # Timing would require storing timestamps per question,
                                    # not just per vote. Removed hardcoded 47.0.
            top_platform=top_platform.capitalize(),
            audience_size=audience_size,
            response_rate=response_rate,
            confidence_level=confidence_level,
            risk_level=risk_level,
            risk_reason=risk_reason,
            warning_flag=warning_flag,
            recommendation=recommendation,
            insight_summary=insight_summary,
            source_breakdown=source_breakdown,
            option_distribution=option_distribution,
            questions=question_analytics,
            crosstab=crosstab,
            platform_breakdown=platform_rows,
        )

    # ── Private helpers ────────────────────────────────────────

    def _build_source_breakdown(self, votes: List[Vote]) -> SourceBreakdown:
        """Count votes per known platform, bucket unknown as 'other'."""
        counts: Dict[str, int] = defaultdict(int)
        known = {"youtube", "patreon", "discord"}
        for v in votes:
            p = v.platform.lower()
            key = p if p in known else "other"
            counts[key] += 1
        return SourceBreakdown(
            youtube=counts["youtube"],
            patreon=counts["patreon"],
            discord=counts["discord"],
            other=counts["other"],
        )

    def _get_option_distribution(
        self, question_analytics: List[QuestionAnalytics]
    ) -> List[OptionDistributionItem]:
        """Extract option percentages from the first choice question (for risk engine)."""
        for qa in question_analytics:
            if qa.results:
                return [
                    OptionDistributionItem(option=r.text, percentage=r.pct)
                    for r in qa.results
                ]
        return []

    def _compute_question_analytics(
        self,
        question: Question,
        q_answers: List[Answer],
        all_votes: List[Vote],
    ) -> QuestionAnalytics:
        """Dispatch analytics computation by question type (Template Method)."""
        total_responses = len(q_answers)
        if question.type in ("single_choice", "dropdown"):
            return self._choice_analytics(question, q_answers, total_responses, single=True)
        if question.type == "multiple_choice":
            return self._choice_analytics(question, q_answers, total_responses, single=False)
        return self._text_analytics(question, q_answers, total_responses, all_votes)

    def _choice_analytics(
        self,
        question: Question,
        q_answers: List[Answer],
        total: int,
        single: bool,
    ) -> QuestionAnalytics:
        """
        Build vote-count / percentage breakdown for choice questions.

        Percentage formula: votes_for_option / total_answers_for_question * 100
        For multiple_choice, denominator is still total responses (not total votes),
        so percentages can exceed 100% if fans pick multiple options.
        """
        counter: Counter = Counter()
        for a in q_answers:
            if single:
                counter[a.value] += 1
            else:
                try:
                    items = json.loads(a.value)
                    for item in items:
                        counter[item] += 1
                except (json.JSONDecodeError, TypeError):
                    counter[a.value] += 1

        results: List[OptionResult] = [
            OptionResult(
                option_id=opt.id,
                text=opt.text,
                votes=counter.get(opt.text, 0),
                # Correct %: option_votes / total_responses * 100
                pct=round(counter.get(opt.text, 0) / total * 100, 1) if total else 0.0,
            )
            for opt in sorted(question.options, key=lambda o: o.order)
        ]

        return QuestionAnalytics(
            id=question.id,
            text=question.text,
            type=question.type,
            total_responses=total,
            results=results,
        )

    def _text_analytics(
        self,
        question: Question,
        q_answers: List[Answer],
        total: int,
        all_votes: List[Vote],
    ) -> QuestionAnalytics:
        """Collect sample text responses with platform attribution (max 10)."""
        vote_platform: Dict[int, str] = {v.id: v.platform for v in all_votes}
        sample: List[Dict[str, Any]] = [
            {
                "id": f"r_{a.id}",
                "text": a.value,
                "platform": vote_platform.get(a.vote_id, "direct").capitalize(),
                "submitted_at": a.vote.submitted_at.isoformat() if a.vote else "",
            }
            for a in q_answers[:10]
            if a.value.strip()
        ]
        return QuestionAnalytics(
            id=question.id,
            text=question.text,
            type=question.type,
            total_responses=total,
            sample_responses=sample,
        )

    def _build_platform_breakdown(
        self,
        poll: Poll,
        votes: List[Vote],
        answers: List[Answer],
    ) -> List[PlatformRow]:
        """
        Build platform × answer breakdown for ALL choice questions.

        For each platform that has at least 1 vote, and for each choice
        question, compute the top answer chosen by that platform's voters.

        Percentage formula:
            voters_on_platform_who_chose_top_option
            ─────────────────────────────────────── × 100
            total_voters_on_platform

        This replaces the old version which only looked at Q1.

        Returns:
            List of PlatformRow, one per (platform × choice_question) pair,
            sorted by (platform vote count desc, question order asc).
            The question_text and question_id fields tell the frontend
            which question each row belongs to.
        """
        # Build answer lookup: vote_id → {question_id: answer_value}
        ans_by_vote: Dict[int, Dict[int, str]] = defaultdict(dict)
        for a in answers:
            ans_by_vote[a.vote_id][a.question_id] = a.value

        # Group votes by platform
        platform_groups: Dict[str, List[Vote]] = defaultdict(list)
        for v in votes:
            platform_groups[v.platform].append(v)

        # Only process choice questions (text questions have no top answer)
        choice_questions = [
            q for q in sorted(poll.questions, key=lambda q: q.order)
            if q.type in ("single_choice", "multiple_choice", "dropdown")
            and q.options
        ]

        if not choice_questions or not platform_groups:
            return []

        rows: List[PlatformRow] = []

        for platform, pvotes in sorted(platform_groups.items(), key=lambda x: -len(x[1])):
            platform_vote_count = len(pvotes)

            for question in choice_questions:
                # Count which options this platform's voters chose
                option_counter: Counter = Counter()
                for v in pvotes:
                    raw_answer = ans_by_vote[v.id].get(question.id)
                    if raw_answer is None:
                        continue
                    # multi-choice answers are JSON arrays
                    if question.type == "multiple_choice":
                        try:
                            items = json.loads(raw_answer)
                            for item in items:
                                option_counter[item] += 1
                        except (json.JSONDecodeError, TypeError):
                            option_counter[raw_answer] += 1
                    else:
                        option_counter[raw_answer] += 1

                if not option_counter:
                    continue  # no answers from this platform for this question

                top = option_counter.most_common(1)[0]
                top_answer = top[0]
                # Correct %: voters who chose top option / total platform voters
                top_pct = round(top[1] / platform_vote_count * 100)

                rows.append(PlatformRow(
                    platform=platform.capitalize(),
                    votes=platform_vote_count,
                    top_topic=top_answer,
                    pct_naval=top_pct,
                    question_text=question.text,
                    question_id=question.id,
                ))

        return rows


# ── Module-level singleton ─────────────────────────────────────
analytics_service = AnalyticsService()
