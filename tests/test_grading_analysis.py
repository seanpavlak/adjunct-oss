"""Tests for grading.analysis and substantive peer reply detection."""

from grading.analysis import (
    assess_initial_post_richness,
    analyze_submission,
    is_substantive_peer_reply,
)
from grading.brief import format_grading_brief
from rubric import RubricPostProcessor, build_rubric_grading_config
from discussion_rubric import CRITERION_ORDER
from submission_models import DiscussionSubmission


class TestSubstantivePeerReplies:
    def test_agree_only_not_substantive(self):
        text = "Hi Maria, I agree with your point. " + "x" * 40
        assert len(text) >= 40
        assert not is_substantive_peer_reply(text, 40)

    def test_substantive_with_detail(self):
        text = (
            "Hi Maria, I agree with your point about metric units in sonography. "
            "In clinical practice we also use m/s for blood flow, which connects to "
            "your example about velocity."
        )
        assert is_substantive_peer_reply(text, 40)

    def test_analysis_flags_thin_replies(self):
        sub = DiscussionSubmission(
            initial_post="Discussion answer. " * 15,
            peer_replies=[
                "Hi Sue, I agree with your point. " + "x" * 35,
                "Hi Bob, great post! " + "y" * 35,
            ],
            link_urls=["https://example.com/source"],
        )
        analysis = analyze_submission(sub, {"min_peer_replies": 2, "min_peer_reply_chars": 40})
        assert analysis.meaningful_peer_count == 2
        assert analysis.substantive_peer_count == 0
        assert "agreement-only" in analysis.engagement_summary.lower() or "substantive" in (
            analysis.engagement_summary.lower()
        )

    def test_engagement_capped_when_replies_not_substantive(self):
        sub = DiscussionSubmission(
            initial_post="A" * 150 + " https://example.com",
            peer_replies=[
                "Hi Sue, I agree with your point. " + "x" * 35,
                "Hi Bob, great post! " + "y" * 35,
            ],
        )
        analysis = analyze_submission(sub)
        config = build_rubric_grading_config([{"name": n} for n in CRITERION_ORDER])
        processor = RubricPostProcessor(config)
        levels = processor.apply(
            {n: "exceeds" for n in CRITERION_ORDER},
            sub,
            lenient=True,
            analysis=analysis,
        )
        assert levels["Engagement"] == "needs"


from grading.fixtures import BRISTER_THIN_INITIAL, BRITO_RICH_INITIAL, LESLEY_ADEQUATE_INITIAL


class TestInitialPostRichness:
    def test_rich_post_qualifies_for_exceeds(self):
        r = assess_initial_post_richness(BRITO_RICH_INITIAL)
        assert r.qualifies_for_exceeds
        assert r.paragraph_count >= 2
        assert "references_section" in r.richness_signals or "citations_or_urls" in r.richness_signals

    def test_thin_post_does_not_qualify(self):
        r = assess_initial_post_richness(BRISTER_THIN_INITIAL)
        assert not r.qualifies_for_exceeds

    def test_adequate_single_block_does_not_qualify(self):
        r = assess_initial_post_richness(LESLEY_ADEQUATE_INITIAL)
        assert not r.qualifies_for_exceeds

    def test_lesley_like_meets_stays_meets_after_enforcement(self):
        sub = DiscussionSubmission(initial_post=LESLEY_ADEQUATE_INITIAL)
        analysis = analyze_submission(sub)
        assert not analysis.initial_richness.qualifies_for_exceeds
        config = build_rubric_grading_config([{"name": n} for n in CRITERION_ORDER])
        processor = RubricPostProcessor(config)
        levels = processor.apply(
            {"Comprehension": "meets", "Timeliness": "meets", "Engagement": "meets", "Writing": "meets"},
            sub,
            analysis=analysis,
        )
        assert levels["Comprehension"] == "meets"


class TestGradingBrief:
    def test_includes_prompt_and_checklist(self):
        sub = DiscussionSubmission(initial_post="Post " * 30)
        analysis = analyze_submission(sub)
        brief = format_grading_brief(analysis, "Week 3: Explain the metric system.")
        assert "Week 3" in brief
        assert "AUTOMATED PRE-GRADE CHECKLIST" in brief
        assert "INITIAL POST" in brief
