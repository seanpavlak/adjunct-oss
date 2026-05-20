"""
Discussion Rubric (2021) — shared across all discussion post assignments.

Auto-grading selects full-credit ratings (100 pts total):
  - Comprehension (40): Exceeds Expectations (100%)
  - Timeliness (10): Meets Expectations (100%) — on-time; Exceeds is N/A
  - Engagement (30): Exceeds Expectations (100%)
  - Writing (20): Exceeds Expectations (100%)
"""

from typing import Any, Dict, List, Optional

# Course grading rules applied before selecting rubric ratings
GRADING_REQUIREMENTS: Dict[str, Any] = {
    "min_peer_replies": 2,
    "require_on_time": True,
    "min_citations": 1,
    "require_citation": True,
    "min_initial_post_chars": 100,
    "min_peer_reply_chars": 40,
    "lenient": True,
}

# Canvas data-testid suffixes per criterion (Discussion Rubric 2021 on CHCP)
RUBRIC_RATING_LEVELS: Dict[str, Dict[str, str]] = {
    "Comprehension": {
        "exceeds": "traditional-criterion-_6629-ratings-0",
        "meets": "traditional-criterion-_6629-ratings-1",
        "needs": "traditional-criterion-_6629-ratings-2",
        "below": "traditional-criterion-_6629-ratings-3",
    },
    "Timeliness": {
        "exceeds": "traditional-criterion-_2232-ratings-0",  # N/A in rubric
        "meets": "traditional-criterion-_2232-ratings-1",
        "needs": "traditional-criterion-_2232-ratings-2",
        "below": "traditional-criterion-_2232-ratings-3",
    },
    "Engagement": {
        "exceeds": "traditional-criterion-_2213-ratings-0",
        "meets": "traditional-criterion-_2213-ratings-1",
        "needs": "traditional-criterion-_2213-ratings-2",
        "below": "traditional-criterion-_2213-ratings-3",
    },
    "Writing": {
        "exceeds": "traditional-criterion-61199_554-ratings-0",
        "meets": "traditional-criterion-61199_554-ratings-1",
        "needs": "traditional-criterion-61199_554-ratings-2",
        "below": "traditional-criterion-61199_554-ratings-3",
    },
}

from rubric.criteria_detail import CRITERION_ORDER, RUBRIC_CRITERIA_DETAIL
from rubric.defaults import DEFAULT_CRITERION_GRADING_POLICIES, RUBRIC_GRADING_DEFAULTS

DISCUSSION_RUBRIC_2021: Dict[str, Any] = {
    "name": "Discussion Rubric (2021)",
    "grade": "100",
    "use_rubric": True,
    "criteria": [
        {
            "name": "Comprehension",
            "max_points": 40,
            "rating": "Exceeds Expectations (100%)",
            "description": (
                "Well-organized initial post with critical thinking, "
                "analysis, or experiences using rich and significant detail."
            ),
        },
        {
            "name": "Timeliness",
            "max_points": 10,
            "rating": "Meets Expectations (100%)",
            "description": "Initial post submitted on time.",
        },
        {
            "name": "Engagement",
            "max_points": 30,
            "rating": "Exceeds Expectations (100%)",
            "description": (
                "Meaningful, on-topic peer responses with clarifying detail "
                "that advance the dialogue."
            ),
        },
        {
            "name": "Writing",
            "max_points": 20,
            "rating": "Exceeds Expectations (100%)",
            "description": (
                "Posts are easily understood, clear, and concise with "
                "proper citation methods where applicable."
            ),
        },
    ],
    "grading_requirements": dict(GRADING_REQUIREMENTS),
    "grading_defaults": dict(RUBRIC_GRADING_DEFAULTS),
    "rubric_rating_levels": RUBRIC_RATING_LEVELS,
}

# Canvas data-testid values for course 93374 / 93375 (Discussion Rubric 2021).
# Order matches criteria above. Re-record with Playwright if Canvas changes IDs.
DEFAULT_RUBRIC_RATINGS: List[str] = [
    "traditional-criterion-_6629-ratings-0",  # Comprehension — Exceeds
    "traditional-criterion-_2232-ratings-1",  # Timeliness — Meets (on time)
    "traditional-criterion-_2213-ratings-0",  # Engagement — Exceeds
    "traditional-criterion-61199_554-ratings-0",  # Writing — Exceeds
]


def build_rubric_ratings_for_levels(
    levels: Dict[str, str],
    rating_levels: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[str]:
    """Build ordered rubric rating test IDs from per-criterion level keys."""
    rating_levels = rating_levels or RUBRIC_RATING_LEVELS
    ratings: List[str] = []
    for criterion in CRITERION_ORDER:
        level = levels.get(criterion, "below")
        criterion_ratings = rating_levels.get(criterion, {})
        test_id = criterion_ratings.get(level) or criterion_ratings.get("below")
        if test_id:
            ratings.append(test_id)
    return ratings


def build_discussion_rubric_config(
    rubric_ratings: List[str] | None = None,
) -> Dict[str, Any]:
    """Build a course-level discussion_rubric config block for courses.json."""
    config = dict(DISCUSSION_RUBRIC_2021)
    config["rubric_ratings"] = rubric_ratings or list(DEFAULT_RUBRIC_RATINGS)
    config["grading_requirements"] = dict(GRADING_REQUIREMENTS)
    config["grading_defaults"] = dict(RUBRIC_GRADING_DEFAULTS)
    config["rubric_rating_levels"] = dict(RUBRIC_RATING_LEVELS)
    return config
