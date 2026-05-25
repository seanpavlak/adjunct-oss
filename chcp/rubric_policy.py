"""
Backward-compatible re-exports. Prefer ``from chcp.rubric import ...`` in new code.
"""

from chcp.rubric import (
    DEFAULT_CRITERION_GRADING_POLICIES,
    RUBRIC_GRADING_DEFAULTS,
    apply_rubric_policies,
    build_grading_instructions,
    build_rubric_grading_config,
    count_meaningful_peer_replies,
    format_rubric_for_prompt,
    merge_criterion_grading_policies,
)
from chcp.rubric.leniency import apply_boundary_leniency
from chcp.rubric.types import BOUNDARY_BUMP_FROM, RUBRIC_LEVEL_ORDER

__all__ = [
    "BOUNDARY_BUMP_FROM",
    "DEFAULT_CRITERION_GRADING_POLICIES",
    "RUBRIC_GRADING_DEFAULTS",
    "RUBRIC_LEVEL_ORDER",
    "apply_boundary_leniency",
    "apply_rubric_policies",
    "build_grading_instructions",
    "build_rubric_grading_config",
    "count_meaningful_peer_replies",
    "format_rubric_for_prompt",
    "merge_criterion_grading_policies",
]
