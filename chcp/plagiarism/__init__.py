"""Discussion post plagiarism detection."""

from chcp.plagiarism.checker import (
    DEFAULT_MIN_MATCHING_FRACTION,
    DEFAULT_MIN_WORDS,
    DEFAULT_SIMILARITY_THRESHOLD,
    DiscussionPost,
    PlagiarismMatch,
    find_plagiarism_pairs,
    format_match_report,
)

__all__ = [
    "DEFAULT_MIN_MATCHING_FRACTION",
    "DEFAULT_MIN_WORDS",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DiscussionPost",
    "PlagiarismMatch",
    "find_plagiarism_pairs",
    "format_match_report",
]
