"""
Backward-compatible re-exports for the grading pipeline.

Prefer ``from chcp.grading import ...`` in new code.
"""

from chcp.grading import (
    CitationReport,
    InitialPostRichness,
    PeerReplyMetrics,
    SubmissionAnalysis,
    analyze_submission,
    assess_initial_post_richness,
    build_citation_report,
    build_discussion_submission_from_entries,
    count_citations,
    evaluate_submission,
    extract_link_urls_from_text,
    format_grading_brief,
    format_submission_for_prompt,
    grade_points_from_levels,
    is_citable_url,
    is_substantive_peer_reply,
    parse_discussion_submission,
    split_content_into_posts,
    timeliness_level_from_days_late,
    detect_late_submission,
    submission_citation_corpus,
)
from chcp.grading.scoring import grade_points_from_levels as _grade_from_levels
from chcp.submission_models import DiscussionSubmission, SubmissionEvaluation

__all__ = [
    "CitationReport",
    "InitialPostRichness",
    "PeerReplyMetrics",
    "SubmissionAnalysis",
    "analyze_submission",
    "assess_initial_post_richness",
    "format_grading_brief",
    "format_submission_for_prompt",
    "build_citation_report",
    "count_citations",
    "extract_link_urls_from_text",
    "is_citable_url",
    "submission_citation_corpus",
    "build_discussion_submission_from_entries",
    "detect_late_submission",
    "parse_discussion_submission",
    "split_content_into_posts",
    "timeliness_level_from_days_late",
    "is_substantive_peer_reply",
    "grade_points_from_levels",
    "_grade_from_levels",
    "evaluate_submission",
    "DiscussionSubmission",
    "SubmissionEvaluation",
]
