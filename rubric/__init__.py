"""
Rubric grading: configuration, LLM prompts, and post-processing pipeline.
"""

from rubric.config import (
    RubricGradingConfig,
    build_rubric_grading_config,
    merge_criterion_grading_policies,
)
from rubric.defaults import (
    DEFAULT_CRITERION_GRADING_POLICIES,
    RUBRIC_GRADING_DEFAULTS,
)
from grading.analysis import SubmissionAnalysis, analyze_submission
from rubric.enforcement import count_meaningful_peer_replies
from rubric.pipeline import RubricPostProcessor, apply_rubric_policies
from rubric.prompt import build_grading_instructions, format_rubric_for_prompt

__all__ = [
    "SubmissionAnalysis",
    "analyze_submission",
    "DEFAULT_CRITERION_GRADING_POLICIES",
    "RUBRIC_GRADING_DEFAULTS",
    "RubricGradingConfig",
    "RubricPostProcessor",
    "apply_rubric_policies",
    "build_grading_instructions",
    "build_rubric_grading_config",
    "count_meaningful_peer_replies",
    "format_rubric_for_prompt",
    "merge_criterion_grading_policies",
]
