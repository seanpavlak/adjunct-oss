"""
Pydantic models for LLM rubric grading structured output.

These models define the exact JSON shape returned by the LLM and are used with
LangChain's with_structured_output() for validated parsing.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from chcp.discussion_rubric import CRITERION_ORDER

CriterionName = Literal["Comprehension", "Timeliness", "Engagement", "Writing"]
RubricLevel = Literal["exceeds", "meets", "needs", "below"]

REQUIRED_CRITERIA = frozenset(CRITERION_ORDER)


class CriterionGrade(BaseModel):
    """One rubric criterion score from the LLM."""

    criterion: CriterionName = Field(
        description="Must be exactly: Comprehension, Timeliness, Engagement, or Writing"
    )
    level: RubricLevel = Field(
        description="Rating level: exceeds, meets, needs, or below"
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Brief justification referencing the rubric",
    )
    borderline: bool = Field(
        default=False,
        description=(
            "True only when torn between two adjacent levels: level 1↔2 (below/needs) "
            "or level 3↔4 (meets/exceeds). False when the chosen level is a clear fit."
        ),
    )


class RubricAssessment(BaseModel):
    """Complete rubric assessment returned by the LLM."""

    criteria: List[CriterionGrade] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Exactly one grade per rubric criterion",
    )
    overall_notes: str = Field(
        default="",
        description="Optional summary of the submission quality",
    )

    @field_validator("criteria")
    @classmethod
    def validate_all_criteria_present(
        cls, value: List[CriterionGrade]
    ) -> List[CriterionGrade]:
        """Ensure each required criterion appears exactly once."""
        names = [c.criterion for c in value]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate criterion names in assessment")
        missing = REQUIRED_CRITERIA - set(names)
        if missing:
            raise ValueError(f"Missing criteria: {sorted(missing)}")
        extra = set(names) - REQUIRED_CRITERIA
        if extra:
            raise ValueError(f"Unknown criteria: {sorted(extra)}")
        return value

    def levels_by_criterion(self) -> dict[str, RubricLevel]:
        """Map criterion name to rubric level."""
        return {c.criterion: c.level for c in self.criteria}

    def reasons_by_criterion(self) -> dict[str, str]:
        """Map criterion name to justification."""
        return {c.criterion: c.reason for c in self.criteria}

    def borderline_by_criterion(self) -> dict[str, bool]:
        """Map criterion name to whether the LLM was torn between adjacent levels."""
        return {c.criterion: c.borderline for c in self.criteria}


def assessment_to_levels(
    assessment: RubricAssessment,
    criterion_order: Optional[List[str]] = None,
) -> dict[str, RubricLevel]:
    """Convert validated RubricAssessment to criterion -> level map."""
    order = criterion_order or list(CRITERION_ORDER)
    levels: dict[str, RubricLevel] = dict(assessment.levels_by_criterion())
    for name in order:
        if name not in levels:
            levels[name] = "meets"
    return levels
