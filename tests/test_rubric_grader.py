"""
Unit tests for LLM rubric grading helpers (no API calls)
"""

from discussion_rubric import CRITERION_ORDER
from rubric_grader import apply_leniency, assessment_to_levels, format_rubric_for_prompt
from rubric_models import CriterionGrade, RubricAssessment
from submission_evaluator import parse_discussion_submission
from submission_models import DiscussionSubmission


class TestApplyLeniency:
    """Tests for lenient post-processing of rubric levels"""

    def _submission(self, replies=None, late=False, initial="A" * 150):
        return DiscussionSubmission(
            initial_post=initial + " https://example.com",
            peer_replies=replies or [],
            is_late=late,
            raw_text="",
        )

    def test_on_time_timeliness_meets(self):
        levels = apply_leniency(
            {n: "below" for n in CRITERION_ORDER},
            self._submission(replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50]),
        )
        assert levels["Timeliness"] == "meets"

    def test_two_replies_bumps_engagement(self):
        levels = apply_leniency(
            {"Engagement": "needs", "Comprehension": "meets", "Timeliness": "meets", "Writing": "meets"},
            self._submission(replies=["Hi Sue, great point " + "x" * 40, "Hi Bob, I agree " + "y" * 40]),
        )
        assert levels["Engagement"] in ("meets", "exceeds")

    def test_citation_bumps_writing(self):
        levels = apply_leniency(
            {"Writing": "needs", "Comprehension": "meets", "Timeliness": "meets", "Engagement": "meets"},
            self._submission(),
        )
        assert levels["Writing"] in ("meets", "exceeds")


class TestAssessmentToLevels:
    """Tests for parsing LLM assessment structure"""

    def test_maps_criteria(self):
        assessment = RubricAssessment(
            criteria=[
                CriterionGrade(
                    criterion="Comprehension", level="exceeds", reason="Strong post"
                ),
                CriterionGrade(criterion="Timeliness", level="meets", reason="On time"),
                CriterionGrade(
                    criterion="Engagement", level="exceeds", reason="Two peer replies"
                ),
                CriterionGrade(criterion="Writing", level="meets", reason="Has URL cite"),
            ],
            overall_notes="Good work",
        )
        levels = assessment_to_levels(assessment)
        assert levels["Comprehension"] == "exceeds"
        assert levels["Timeliness"] == "meets"


class TestFormatRubric:
    """Tests for rubric prompt formatting"""

    def test_includes_all_criteria(self):
        text = format_rubric_for_prompt()
        for name in CRITERION_ORDER:
            assert name in text
        assert "Exceeds Expectations" in text
