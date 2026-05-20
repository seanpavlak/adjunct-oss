"""
LLM prompt sections built from rubric configuration.
"""

from __future__ import annotations

from typing import List, Optional

from rubric.criteria_detail import CRITERION_ORDER, RUBRIC_CRITERIA_DETAIL
from rubric.config import RubricGradingConfig, RubricCriterionConfig
from rubric.defaults import DEFAULT_CRITERION_GRADING_POLICIES


def format_rubric_for_prompt(
    criteria: List[RubricCriterionConfig],
    rubric_name: str = "Discussion Rubric (2021)",
) -> str:
    """Format rubric criteria and rating bands for the LLM prompt."""
    lines = [f"{rubric_name} — grade using these exact criteria:\n"]
    if not criteria:
        for name in CRITERION_ORDER:
            lines.extend(_format_criterion_block(name, None, RUBRIC_CRITERIA_DETAIL.get(name, {})))
        return "\n".join(lines)

    for criterion in criteria:
        detail = RUBRIC_CRITERIA_DETAIL.get(criterion.name, {})
        lines.extend(_format_criterion_block(criterion.name, criterion, detail))
    return "\n".join(lines)


def _format_criterion_block(
    name: str,
    criterion: Optional[RubricCriterionConfig],
    detail: dict,
) -> List[str]:
    max_points = (criterion.max_points if criterion else 0) or detail.get("max_points", 0)
    lines = [f"## {name} ({max_points} points)"]
    for level, description in detail.get("ratings", {}).items():
        lines.append(f"  - {level}: {description}")
    if criterion:
        guidance = criterion.grading_policy.llm_guidance
    else:
        guidance = DEFAULT_CRITERION_GRADING_POLICIES.get(name, {}).get("llm_guidance")
    if guidance:
        lines.append(f"  Grading notes: {guidance}")
    lines.append("")
    return lines


def build_grading_instructions(config: RubricGradingConfig) -> str:
    """Build the finetuning block appended to the LLM prompt."""
    lines: List[str] = []
    if config.grading_defaults.global_llm_guidance:
        lines.append(config.grading_defaults.global_llm_guidance)
    lines.append("")
    lines.append("Per-criterion requirements (from this course rubric):")
    for criterion in config.criteria:
        guidance = criterion.grading_policy.llm_guidance
        if guidance:
            lines.append(f"- {criterion.name}: {guidance}")
    return "\n".join(lines).strip()
