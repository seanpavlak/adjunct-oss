"""
Unit tests for discussion submission parsing and evaluation
"""

import pytest

from submission_evaluator import (
    build_discussion_submission_from_entries,
    count_citations,
    evaluate_submission,
    extract_link_urls_from_text,
    parse_discussion_submission,
    split_content_into_posts,
)
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

    def test_nist_url_citation(self):
        text = "See https://www.nist.gov/pml/owm/metric-si for details."
        assert count_citations(text) >= 1

    def test_href_only_counts_via_link_urls(self):
        assert count_citations("Read more on the NIST site.", link_urls=[]) == 0
        assert (
            count_citations(
                "Read more on the NIST site.",
                link_urls=["https://www.nist.gov/pml/owm/metric-si"],
            )
            >= 1
        )

    def test_submission_link_urls_count(self):
        sub = DiscussionSubmission(
            initial_post="I used an external source for this claim.",
            link_urls=["https://www.nist.gov/pml/owm/metric-si"],
        )
        assert count_citations(submission=sub) >= 1

    def test_apa_retrieved_from_citations(self):
        text = (
            "National Institute of Standards and Technology. (n.d.). Metric system basics. "
            "Retrieved May 11, 2026, from National Institute of Standards and Technology "
            "(https://www.nist.gov?utm_source=chatgpt.com)\n\n"
            "NASA. (n.d.). The metric system and science. Retrieved May 11, 2026, from "
            "NASA (https://www.nasa.gov?utm_source=chatgpt.com)"
        )
        assert count_citations(text) >= 1
        assert len(extract_link_urls_from_text(text)) >= 2

    def test_apa_retrieved_without_urls_in_text(self):
        text = (
            "National Institute of Standards and Technology. (n.d.). Metric system basics. "
            "Retrieved May 11, 2026, from National Institute of Standards and Technology\n\n"
            "NASA. (n.d.). The metric system and science. Retrieved May 11, 2026, from NASA"
        )
        assert count_citations(text) >= 1

    def test_apa_bibliography_merged_without_heading(self):
        refs = (
            "National Institute of Standards and Technology. (n.d.). Metric system basics. "
            "Retrieved May 11, 2026, from National Institute of Standards and Technology "
            "(https://www.nist.gov?utm_source=chatgpt.com)\n\n"
            "NASA. (n.d.). The metric system and science. Retrieved May 11, 2026, from "
            "NASA (https://www.nasa.gov?utm_source=chatgpt.com)"
        )
        main = "Discussion post body. " * 12
        sub = build_discussion_submission_from_entries([main], raw_text=main + "\n\n" + refs)
        assert "Retrieved May" in sub.initial_post
        assert count_citations(submission=sub) >= 1

    def test_references_only_in_raw_text(self):
        refs = (
            "Refrences\n\n"
            "The reason the U.S. doesn't use the metric system. NIST. (2025, February 4). "
            "https://www.nist.gov/news-events/news/2024/06/reason-us-doesnt-use-metric-system"
            "Links to an external site.\n\n"
            "Why doesn't the U.S. use the metric system? - the ANSI blog. (n.d.). "
            "https://blog.ansi.org/ansi/why-does-the-u-s-not-use-the-metric-system/"
            "Links to an external site."
        )
        main = "Even though most of the world uses the metric system. " * 8
        raw = f"{main}\n\n{refs}"
        sub = build_discussion_submission_from_entries([main], raw_text=raw)
        assert "refrenc" in sub.initial_post.lower()
        assert count_citations(submission=sub) >= 1
        assert len(sub.link_urls) >= 2

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


class TestBuildDiscussionSubmissionFromEntries:
    """Tests for Speed Grader discussion_entry DOM order parsing"""

    def test_first_entry_initial_rest_are_peer_replies(self):
        initial = (
            "The metric system is not used in the United States currently because "
            "it was never implemented as the main system use."
        )
        reply_lidia = (
            "Hi Lidia, I agree with your point regarding making the switch to the "
            "metric system. This would cause many conflicts within the country."
        )
        reply_bailee = (
            "Hello Bailee, I agree with you perspective on everything being a little "
            "better if we all used the metric system and avoiding the conversions."
        )
        sub = build_discussion_submission_from_entries(
            [initial, reply_lidia, reply_bailee]
        )
        assert initial in sub.initial_post
        assert len(sub.peer_replies) == 2
        assert "Hi Lidia" in sub.peer_replies[0]
        assert "Hello Bailee" in sub.peer_replies[1]
        assert sub.peer_reply_count == 2

    def test_single_entry_no_peer_replies(self):
        sub = build_discussion_submission_from_entries(
            ["Only the initial post with enough characters to count."]
        )
        assert sub.initial_post
        assert sub.peer_replies == []


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
