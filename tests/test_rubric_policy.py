"""
Unit tests for rubric policy engine (config-driven grading rules)
"""

from chcp.discussion_rubric import CRITERION_ORDER, DEFAULT_CRITERION_GRADING_POLICIES
from chcp.rubric import (
    apply_rubric_policies,
    build_grading_instructions,
    build_rubric_grading_config,
    format_rubric_for_prompt,
    merge_criterion_grading_policies,
)
from chcp.rubric.leniency import apply_boundary_leniency
from chcp.submission_models import DiscussionSubmission


def _config(requirements=None):
    criteria = [
        {
            "name": n,
            "grading_policy": dict(DEFAULT_CRITERION_GRADING_POLICIES[n]),
        }
        for n in CRITERION_ORDER
    ]
    return build_rubric_grading_config(criteria, requirements)


class TestMergeCriterionGradingPolicies:
    def test_legacy_requirements_overlay_engagement(self):
        legacy = merge_criterion_grading_policies(
            [{"name": "Engagement", "grading_policy": DEFAULT_CRITERION_GRADING_POLICIES["Engagement"]}],
            {"min_peer_replies": 3},
        )
        engagement = next(c for c in legacy["criteria"] if c["name"] == "Engagement")
        assert engagement["grading_policy"]["enforcement"]["min_count"] == 3


class TestApplyRubricPolicies:
    def _submission(self, replies=None, late=False, initial="A" * 150):
        return DiscussionSubmission(
            initial_post=initial + " https://example.com",
            peer_replies=replies or [],
            is_late=late,
            raw_text="",
        )

    def test_on_time_timeliness_meets(self):
        levels = apply_rubric_policies(
            {n: "below" for n in CRITERION_ORDER},
            self._submission(replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50]),
            merge_criterion_grading_policies(
                [{"name": n} for n in CRITERION_ORDER]
            ),
            lenient=True,
        )
        assert levels["Timeliness"] == "meets"

    def test_no_peer_replies_engagement_below(self):
        levels = apply_rubric_policies(
            {n: "exceeds" for n in CRITERION_ORDER},
            self._submission(replies=[]),
            merge_criterion_grading_policies(
                [{"name": n} for n in CRITERION_ORDER]
            ),
            lenient=True,
        )
        assert levels["Engagement"] == "below"

    def test_no_citations_writing_capped_at_meets(self):
        levels = apply_rubric_policies(
            {n: "exceeds" for n in CRITERION_ORDER},
            DiscussionSubmission(
                initial_post="A" * 150,
                peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
            ),
            merge_criterion_grading_policies(
                [{"name": n} for n in CRITERION_ORDER]
            ),
            lenient=True,
        )
        assert levels["Writing"] == "meets"


class TestBoundaryLeniency:
    def test_borderline_below_bumps_to_needs(self):
        config = _config()
        levels = apply_boundary_leniency(
            {"Comprehension": "below"},
            {"Comprehension": True},
            config,
        )
        assert levels["Comprehension"] == "needs"

    def test_borderline_meets_bumps_to_exceeds(self):
        config = _config()
        levels = apply_boundary_leniency(
            {"Writing": "meets"},
            {"Writing": True},
            config,
        )
        assert levels["Writing"] == "exceeds"

    def test_clear_meets_not_bumped(self):
        config = _config()
        levels = apply_boundary_leniency(
            {"Writing": "meets"},
            {"Writing": False},
            config,
        )
        assert levels["Writing"] == "meets"

    def test_clear_below_not_bumped_without_borderline(self):
        levels = apply_rubric_policies(
            {"Engagement": "below"},
            DiscussionSubmission(
                initial_post="Short but has https://example.com",
                peer_replies=["Hi Sue, " + "x" * 50, "Hi Bob, " + "y" * 50],
            ),
            merge_criterion_grading_policies(
                [{"name": n} for n in CRITERION_ORDER]
            ),
            lenient=True,
            borderline={"Engagement": False},
        )
        assert levels["Engagement"] == "below"


class TestPromptBuilding:
    def test_format_includes_grading_notes(self):
        config = _config()
        text = format_rubric_for_prompt(config.criteria)
        assert "Grading notes:" in text
        assert "Engagement" in text

    def test_build_grading_instructions_includes_global(self):
        config = _config()
        text = build_grading_instructions(config)
        assert "borderline" in text.lower() or "LENIENCY" in text
        assert "Engagement:" in text
