"""Entry point for grading a parsed discussion submission."""

from __future__ import annotations

from typing import Any, Dict, Optional

from chcp.submission_models import DiscussionSubmission, SubmissionEvaluation


def evaluate_submission(
    submission: DiscussionSubmission,
    requirements: Dict[str, Any],
    *,
    rubric_rating_levels: Optional[Dict[str, Dict[str, str]]] = None,
    discussion_prompt: str = "",
    llm_grader: Optional[Any] = None,
    dry_run: bool = False,
) -> SubmissionEvaluation:
    """
    Grade via ``RubricGrader`` (LLM + analysis-driven post-processing).

    Requires an LLM API key and ``llm_grader`` instance from ``rubric_grader.RubricGrader``.
    """
    if llm_grader is None:
        raise ValueError(
            "LLM grader is required. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY."
        )
    return llm_grader.grade(
        submission,
        discussion_prompt=discussion_prompt,
        rubric_rating_levels=rubric_rating_levels,
        requirements=requirements,
        dry_run=dry_run,
    )
