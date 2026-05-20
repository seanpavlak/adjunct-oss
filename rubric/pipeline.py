"""
Post-LLM grading pipeline: boundary leniency, then enforcement.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

from rubric.config import RubricGradingConfig, build_rubric_grading_config
from rubric.enforcement import apply_enforcement
from rubric.leniency import apply_boundary_leniency
from rubric.types import RubricLevel
from submission_models import DiscussionSubmission


class RubricPostProcessor:
    """Applies configured policies to LLM-produced rubric levels."""

    def __init__(self, config: RubricGradingConfig):
        self._config = config

    @classmethod
    def from_course_dict(
        cls,
        criteria: list,
        grading_requirements: Optional[dict] = None,
        grading_defaults: Optional[dict] = None,
    ) -> RubricPostProcessor:
        return cls(
            build_rubric_grading_config(criteria, grading_requirements, grading_defaults)
        )

    @property
    def config(self) -> RubricGradingConfig:
        return self._config

    def apply(
        self,
        levels: Dict[str, RubricLevel],
        submission: DiscussionSubmission,
        *,
        lenient: bool = True,
        borderline: Optional[Mapping[str, bool]] = None,
    ) -> Dict[str, RubricLevel]:
        result: Dict[str, RubricLevel] = dict(levels)
        use_lenient = lenient and self._config.lenient_enabled

        if use_lenient and borderline:
            result = apply_boundary_leniency(result, borderline, self._config)

        for name in self._config.criterion_order:
            enforcement = self._config.enforcement_for(name)
            if not enforcement:
                continue
            current = result.get(name, "meets")
            result[name] = apply_enforcement(
                current, name, submission, enforcement
            )
        return result


def apply_rubric_policies(
    levels: Dict[str, str],
    submission: DiscussionSubmission,
    rubric_config: dict,
    *,
    lenient: bool = True,
    borderline: Optional[Dict[str, bool]] = None,
) -> Dict[str, str]:
    """Backward-compatible entry point accepting a legacy config dict."""
    config = build_rubric_grading_config(
        rubric_config.get("criteria", []),
        rubric_config.get("grading_requirements"),
        rubric_config.get("grading_defaults"),
    )
    processor = RubricPostProcessor(config)
    typed_levels: Dict[str, RubricLevel] = {
        k: v  # type: ignore[misc]
        for k, v in levels.items()
    }
    result = processor.apply(
        typed_levels, submission, lenient=lenient, borderline=borderline
    )
    return dict(result)
