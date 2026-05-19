"""
Unit tests for discussion submission parsing and evaluation
"""

import pytest

from submission_evaluator import (
    count_citations,
    evaluate_submission,
    parse_discussion_submission,
    split_content_into_posts,
)
from submission_models import DiscussionSubmission
from submission_models import DiscussionSubmission


class TestSplitContentIntoPosts:
    """Tests for splitting iframe content into posts"""

    def test_initial_and_two_peer_replies(self):
        raw = """
        The submissions for this assignment are shown below.

        The metric system is not used in the United States for many reasons.
        According to NASA (2020), only three countries still use imperial units.

        Hi Lidia, I agree with your point about medicine using metric measurements.
        That is a great example from clinical practice.

        Hello Bailee, I agree with your post about road signs and the cost of conversion.
        Switching would take decades of effort.
        """
        posts = split_content_into_posts(raw)
        assert len(posts) >= 3

    def test_skips_submissions_header(self):
        raw = "The submissions for this discussion are listed below.\n\nShort"
        posts = split_content_into_posts(raw)
        assert all("submissions for this" not in p.lower() for p in posts)


class TestCitations:
    """Tests for citation detection"""

    def test_url_citation(self):
        text = "See https://www.nasa.gov/metric for more information."
        assert count_citations(text) >= 1

    def test_no_citation(self):
        assert count_citations("I think physics is interesting.") == 0

    def test_in_text_citation(self):
        text = 'According to Smith (2019), the speed of light is constant.'
        assert count_citations(text) >= 1


class TestEvaluateSubmission:
    """Tests for evaluate_submission entry point"""

    def test_requires_llm_grader(self):
        with pytest.raises(ValueError, match="LLM grader is required"):
            evaluate_submission(
                DiscussionSubmission(initial_post="test"),
                {},
            )


class TestParseDiscussionSubmission:
    """Tests for parse_discussion_submission"""

    def test_splits_initial_and_replies(self):
        raw = (
            "Initial post about physics with enough content to count as substantive. "
            "https://example.com/source\n\n"
            "Hi Maria, I agree with your analysis of velocity and speed in sonography."
        )
        sub = parse_discussion_submission(raw)
        assert sub.initial_post
        assert "Hi Maria" in (sub.peer_replies[0] if sub.peer_replies else "")
