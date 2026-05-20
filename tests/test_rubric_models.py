"""
Unit tests for rubric Pydantic models
"""

import pytest
from pydantic import ValidationError

from rubric_models import CriterionGrade, RubricAssessment


class TestCriterionGrade:
    """Tests for CriterionGrade model"""

    def test_valid_criterion(self):
        grade = CriterionGrade(
            criterion="Comprehension",
            level="exceeds",
            reason="Strong analysis with detail.",
        )
        assert grade.level == "exceeds"
        assert grade.borderline is False

    def test_borderline_flag(self):
        grade = CriterionGrade(
            criterion="Writing",
            level="meets",
            reason="Borderline between meets and exceeds.",
            borderline=True,
        )
        assert grade.borderline is True

    def test_rejects_invalid_criterion_name(self):
        with pytest.raises(ValidationError):
            CriterionGrade(
                criterion="Participation",
                level="meets",
                reason="Good effort.",
            )

    def test_rejects_invalid_level(self):
        with pytest.raises(ValidationError):
            CriterionGrade(
                criterion="Writing",
                level="good",
                reason="Clear writing.",
            )


class TestRubricAssessment:
    """Tests for RubricAssessment model"""

    def _four_criteria(self):
        return [
            CriterionGrade(
                criterion="Comprehension", level="exceeds", reason="Detailed post."
            ),
            CriterionGrade(
                criterion="Timeliness", level="meets", reason="On time."
            ),
            CriterionGrade(
                criterion="Engagement", level="exceeds", reason="Two peer replies."
            ),
            CriterionGrade(
                criterion="Writing", level="meets", reason="Includes citation."
            ),
        ]

    def test_valid_assessment(self):
        assessment = RubricAssessment(criteria=self._four_criteria())
        assert len(assessment.criteria) == 4
        assert assessment.levels_by_criterion()["Engagement"] == "exceeds"

    def test_rejects_duplicate_criterion(self):
        criteria = self._four_criteria()
        criteria[1] = CriterionGrade(
            criterion="Comprehension", level="meets", reason="Duplicate."
        )
        with pytest.raises(ValidationError, match="Duplicate"):
            RubricAssessment(criteria=criteria)

    def test_rejects_missing_criterion(self):
        criteria = self._four_criteria()[:3]
        with pytest.raises(ValidationError):
            RubricAssessment(criteria=criteria)

    def test_model_json_schema_has_criteria(self):
        schema = RubricAssessment.model_json_schema()
        assert "criteria" in schema["properties"]
