"""
Unit tests for LLM rubric grading helpers (no API calls)
"""

from chcp.discussion_rubric import CRITERION_ORDER
from chcp.rubric import (
    RubricPostProcessor,
    build_rubric_grading_config,
    format_rubric_for_prompt,
)
from chcp.rubric.enforcement import apply_enforcement
from chcp.rubric_models import CriterionGrade, RubricAssessment, assessment_to_levels
from chcp.submission_models import DiscussionSubmission


def _processor(requirements=None):
    criteria = [{"name": n} for n in CRITERION_ORDER]
    config = build_rubric_grading_config(criteria, requirements)
    return RubricPostProcessor(config), config


class TestPostProcessor:
    def _submission(self, replies=None, late=False, initial="A" * 150):
        return DiscussionSubmission(
            initial_post=initial + " https://example.com",
            peer_replies=replies or [],
            is_late=late,
            raw_text="",
        )

    def test_on_time_timeliness_meets(self):
        processor, _ = _processor()
        levels = processor.apply(
            {n: "below" for n in CRITERION_ORDER},
            self._submission(replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50]),
            lenient=True,
        )
        assert levels["Timeliness"] == "meets"

    def test_one_day_late_timeliness_needs(self):
        processor, _ = _processor()
        levels = processor.apply(
            {n: "exceeds" for n in CRITERION_ORDER},
            DiscussionSubmission(
                initial_post="A" * 150,
                peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
                days_late=1,
            ),
            lenient=True,
        )
        assert levels["Timeliness"] == "needs"

    def test_two_days_late_timeliness_below(self):
        processor, _ = _processor()
        levels = processor.apply(
            {n: "exceeds" for n in CRITERION_ORDER},
            DiscussionSubmission(
                initial_post="A" * 150,
                peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
                days_late=2,
            ),
            lenient=True,
        )
        assert levels["Timeliness"] == "below"

    def test_clear_meets_stays_meets_with_two_replies(self):
        processor, _ = _processor()
        levels = processor.apply(
            {
                "Engagement": "meets",
                "Comprehension": "meets",
                "Timeliness": "meets",
                "Writing": "meets",
            },
            self._submission(
                replies=["Hi Sue, great point " + "x" * 40, "Hi Bob, I agree " + "y" * 40]
            ),
            lenient=True,
        )
        assert levels["Engagement"] == "meets"

    def test_strong_peer_replies_promote_engagement_to_exceeds(self):
        from chcp.grading.analysis import analyze_submission
        from chcp.grading.fixtures import TIONNA_PEER_REPLY_CHEYENE, TIONNA_PEER_REPLY_LIDIA

        sub = DiscussionSubmission(
            initial_post="A" * 150,
            peer_replies=[TIONNA_PEER_REPLY_LIDIA, TIONNA_PEER_REPLY_CHEYENE],
        )
        analysis = analyze_submission(sub)
        processor, _ = _processor()
        levels = processor.apply(
            {n: "meets" for n in CRITERION_ORDER},
            sub,
            lenient=True,
            analysis=analysis,
        )
        assert levels["Engagement"] == "exceeds"

    def test_clear_needs_stays_needs_with_citation(self):
        processor, _ = _processor()
        levels = processor.apply(
            {
                "Writing": "needs",
                "Comprehension": "meets",
                "Timeliness": "meets",
                "Engagement": "meets",
            },
            self._submission(),
            lenient=True,
        )
        assert levels["Writing"] == "needs"

    def test_no_peer_replies_engagement_zero(self):
        processor, _ = _processor()
        levels = processor.apply(
            {n: "exceeds" for n in CRITERION_ORDER},
            self._submission(replies=[]),
            lenient=True,
        )
        assert levels["Engagement"] == "below"

    def test_one_peer_reply_engagement_not_full_credit(self):
        processor, config = _processor()
        enforcement = config.enforcement_for("Engagement") or {}
        level = apply_enforcement(
            "exceeds",
            "Engagement",
            self._submission(replies=["Hi Sue, " + "x" * 50]),
            enforcement,
        )
        assert level == "needs"

    def test_no_citations_writing_capped_at_meets(self):
        processor, _ = _processor()
        levels = processor.apply(
            {n: "exceeds" for n in CRITERION_ORDER},
            DiscussionSubmission(
                initial_post="A" * 150,
                peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
            ),
            lenient=True,
        )
        assert levels["Writing"] == "meets"

    def test_rich_initial_post_bumps_comprehension_meets_to_exceeds(self):
        from chcp.grading.fixtures import BRITO_RICH_INITIAL

        processor, _ = _processor()
        sub = DiscussionSubmission(
            initial_post=BRITO_RICH_INITIAL,
            peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
        )
        from chcp.grading.analysis import analyze_submission

        analysis = analyze_submission(sub)
        assert analysis.initial_richness.qualifies_for_exceeds
        levels = processor.apply(
            {
                "Comprehension": "meets",
                "Timeliness": "meets",
                "Engagement": "exceeds",
                "Writing": "meets",
            },
            sub,
            lenient=True,
            analysis=analysis,
        )
        assert levels["Comprehension"] == "exceeds"

    def test_padding_alone_does_not_bump_comprehension(self):
        from chcp.grading.fixtures import LESLEY_ADEQUATE_INITIAL

        processor, _ = _processor()
        sub = DiscussionSubmission(initial_post=LESLEY_ADEQUATE_INITIAL)
        from chcp.grading.analysis import analyze_submission

        analysis = analyze_submission(sub)
        levels = processor.apply(
            {"Comprehension": "meets", "Timeliness": "meets", "Engagement": "meets", "Writing": "meets"},
            sub,
            lenient=True,
            analysis=analysis,
        )
        assert levels["Comprehension"] == "meets"

    def test_citation_present_does_not_force_writing_below(self):
        _, config = _processor()
        enforcement = config.enforcement_for("Writing") or {}
        level = apply_enforcement(
            "exceeds",
            "Writing",
            self._submission(),
            enforcement,
        )
        assert level == "exceeds"

    def test_book_citation_promotes_writing_meets_to_exceeds(self):
        from chcp.grading.analysis import analyze_submission
        from chcp.grading.fixtures import PROJECTILE_WITH_BOOK_CITATION

        sub = DiscussionSubmission(
            initial_post=PROJECTILE_WITH_BOOK_CITATION,
            peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
        )
        analysis = analyze_submission(sub)
        assert analysis.citation_report.has_quality_source
        processor, _ = _processor()
        levels = processor.apply(
            {
                "Comprehension": "meets",
                "Timeliness": "meets",
                "Engagement": "meets",
                "Writing": "meets",
            },
            sub,
            analysis=analysis,
        )
        assert levels["Writing"] == "exceeds"


class TestAssessmentToLevels:
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
    def test_includes_all_criteria(self):
        text = format_rubric_for_prompt([])
        for name in CRITERION_ORDER:
            assert name in text
        assert "Exceeds Expectations" in text
