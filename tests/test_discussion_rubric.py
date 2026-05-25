"""
Unit tests for discussion rubric configuration
"""

from chcp.discussion_rubric import (
    DISCUSSION_RUBRIC_2021,
    DEFAULT_RUBRIC_RATINGS,
    build_discussion_rubric_config,
)


class TestDiscussionRubric2021:
    """Tests for Discussion Rubric (2021) defaults"""

    def test_four_criteria(self):
        assert len(DISCUSSION_RUBRIC_2021["criteria"]) == 4

    def test_total_points(self):
        total = sum(c["max_points"] for c in DISCUSSION_RUBRIC_2021["criteria"])
        assert total == 100

    def test_timeliness_uses_meets_not_exceeds(self):
        timeliness = next(
            c for c in DISCUSSION_RUBRIC_2021["criteria"] if c["name"] == "Timeliness"
        )
        assert timeliness["rating"] == "Meets Expectations (100%)"

    def test_default_rubric_ratings_count(self):
        assert len(DEFAULT_RUBRIC_RATINGS) == 4

    def test_build_config(self):
        config = build_discussion_rubric_config()
        assert config["name"] == "Discussion Rubric (2021)"
        assert len(config["rubric_ratings"]) == 4
