"""
Deterministic enforcement rules applied after LLM grading.

Each rule type is registered in ENFORCEMENT_HANDLERS. Add new rule types here
when a course rubric needs different post-LLM logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from rubric.types import RUBRIC_LEVEL_ORDER, RubricLevel
from submission_evaluator import (
    count_citations,
    detect_late_submission,
    timeliness_level_from_days_late,
)
from submission_models import DiscussionSubmission

EnforcementHandler = Callable[["EnforcementContext"], RubricLevel]


@dataclass(frozen=True)
class EnforcementContext:
    """Inputs for a single criterion enforcement rule."""

    criterion_name: str
    level: RubricLevel
    submission: DiscussionSubmission
    params: Mapping[str, Any]


def _cap_at_most(level: RubricLevel, ceiling: RubricLevel) -> RubricLevel:
    """Lower the level if it is above ceiling (e.g. exceeds → meets when no citations)."""
    if RUBRIC_LEVEL_ORDER.index(level) > RUBRIC_LEVEL_ORDER.index(ceiling):
        return ceiling
    return level


def count_meaningful_peer_replies(
    submission: DiscussionSubmission, min_chars: int = 40
) -> int:
    return len([r for r in submission.peer_replies if len(r.strip()) >= min_chars])


def _apply_timeliness(ctx: EnforcementContext) -> RubricLevel:
    days_late = ctx.submission.days_late
    if days_late is not None:
        return timeliness_level_from_days_late(days_late)  # type: ignore[return-value]

    is_late = ctx.submission.is_late or detect_late_submission(ctx.submission.raw_text)
    if not is_late:
        return ctx.params.get("on_time_level", "meets")
    return ctx.level


def _apply_min_peer_replies(ctx: EnforcementContext) -> RubricLevel:
    min_chars = int(ctx.params.get("min_chars_per_reply", 40))
    min_count = int(ctx.params.get("min_count", 2))
    peer_count = count_meaningful_peer_replies(ctx.submission, min_chars)
    if peer_count == 0:
        return ctx.params.get("level_when_zero", "below")
    if peer_count < min_count:
        return ctx.params.get("level_when_insufficient", "needs")
    return ctx.level


def _apply_min_citations(ctx: EnforcementContext) -> RubricLevel:
    """
    Citation enforcement caps Writing — it does not zero out the criterion.

    Clear writing without a citation may earn meets but not exceeds.
    """
    if not ctx.params.get("require_citation", True):
        return ctx.level
    citation_count = count_citations(submission=ctx.submission)
    min_count = int(ctx.params.get("min_count", 1))
    if citation_count == 0:
        ceiling = ctx.params.get("level_when_zero", "meets")
        return _cap_at_most(ctx.level, ceiling)
    if citation_count < min_count:
        ceiling = ctx.params.get("level_when_insufficient", "meets")
        return _cap_at_most(ctx.level, ceiling)
    return ctx.level


def _apply_comprehension_effort(ctx: EnforcementContext) -> RubricLevel:
    """
    Floor very short posts at below; promote substantive initial posts to exceeds
    when the LLM underrated a clearly rich response.
    """
    initial_len = len(ctx.submission.initial_post.strip())
    floor = int(ctx.params.get("min_chars_floor", 30))
    exceeds_at = int(ctx.params.get("min_chars_exceeds", 120))
    if initial_len < floor:
        return "below"
    if initial_len >= exceeds_at and ctx.level == "meets":
        return "exceeds"
    return ctx.level


ENFORCEMENT_HANDLERS: Dict[str, EnforcementHandler] = {
    "timeliness": _apply_timeliness,
    "min_meaningful_peer_replies": _apply_min_peer_replies,
    "min_citations": _apply_min_citations,
    "comprehension_effort": _apply_comprehension_effort,
}


def apply_enforcement(
    level: RubricLevel,
    criterion_name: str,
    submission: DiscussionSubmission,
    enforcement: Mapping[str, Any],
) -> RubricLevel:
    """Run a single enforcement rule; return unchanged level if type is unknown."""
    rule_type = enforcement.get("type")
    if not rule_type or rule_type not in ENFORCEMENT_HANDLERS:
        return level
    ctx = EnforcementContext(
        criterion_name=criterion_name,
        level=level,
        submission=submission,
        params=enforcement,
    )
    result = ENFORCEMENT_HANDLERS[rule_type](ctx)
    return result  # type: ignore[return-value]
