"""
Rating band descriptions for the Discussion Rubric (2021).
"""

from typing import Any, Dict, List

CRITERION_ORDER: List[str] = [
    "Comprehension",
    "Timeliness",
    "Engagement",
    "Writing",
]

RUBRIC_CRITERIA_DETAIL: Dict[str, Dict[str, Any]] = {
    "Comprehension": {
        "max_points": 40,
        "ratings": {
            "exceeds": (
                "Exceeds Expectations (100%, 40 pts): Well-organized initial post with "
                "critical thinking, analysis, or experiences using rich and significant detail."
            ),
            "meets": (
                "Meets Expectations (85%, 34 pts): Organized initial post with critical "
                "thinking, analysis, or experiences using adequate detail."
            ),
            "needs": (
                "Needs Improvement (70%, 28 pts): Initial post with gaps in organization "
                "and basic understanding, lacking adequate detail."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): Lacks organization, no critical thinking, "
                "needs detail to show understanding."
            ),
        },
    },
    "Timeliness": {
        "max_points": 10,
        "ratings": {
            "exceeds": "Exceeds Expectations (N/A, not used for timeliness).",
            "meets": "Meets Expectations (100%, 10 pts): Initial post submitted on time.",
            "needs": "Needs Improvement (70%, 7 pts): Initial post submitted one (1) day late.",
            "below": (
                "Below Expectations (0%, 0 pts): Initial post submitted two (2) or more days late."
            ),
        },
    },
    "Engagement": {
        "max_points": 30,
        "ratings": {
            "exceeds": (
                "Exceeds Expectations (100%, 30 pts): Meaningful on-topic responses with "
                "clarifying explanation and detail; expands on peers' comments in a value-adding "
                "way; promotes collaborative dialogue with follow-up questions."
            ),
            "meets": (
                "Meets Expectations (85%, 26 pts): Meaningful on-topic responses with sufficient "
                "explanation; expands on peers' comments; supports dialogue with some follow-up."
            ),
            "needs": (
                "Needs Improvement (70%, 21 pts): Simplistic responses with limited explanation, "
                "detail, and follow-up questions."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): Responses lack explanation, detail, and follow-up."
            ),
        },
    },
    "Writing": {
        "max_points": 20,
        "ratings": {
            "exceeds": (
                "Exceeds Expectations (100%, 20 pts): Easily understood, clear, concise; proper "
                "citation methods where applicable with no citation errors."
            ),
            "meets": (
                "Meets Expectations (85%, 17 pts): Easily understood; proper citation methods "
                "where applicable with few citation errors."
            ),
            "needs": (
                "Needs Improvement (70%, 14 pts): Understandable; proper citation methods where "
                "applicable with a number of citation errors."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): Others cannot understand; does not use proper "
                "citation methods where applicable."
            ),
        },
    },
}
