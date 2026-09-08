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
                "Exceeds Expectations (100%, 40 pts): You develop a well-organized initial "
                "post that shows you can think critically on the topic by integrating your "
                "own thoughts, analysis, or experiences using rich and significant detail."
            ),
            "meets": (
                "Meets Expectations (85%, 34 pts): You develop an organized initial post "
                "that shows you can think critically on the topic by integrating your own "
                "thoughts, analysis, or experiences using adequate detail."
            ),
            "needs": (
                "Needs Improvement (70%, 28 pts): You develop an initial post that shows "
                "gaps in organization and a basic understanding of the topic lacking "
                "adequate detail."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): You develop an initial post that lacks "
                "organization, does not show critical thinking skills and needs detail to "
                "show understanding."
            ),
        },
    },
    "Timeliness": {
        "max_points": 10,
        "ratings": {
            "exceeds": "Exceeds Expectations (N/A, 0%; not used for timeliness).",
            "meets": "Meets Expectations (100%, 10 pts): You submit your initial post on time.",
            "needs": (
                "Needs Improvement (70%, 7 pts): You submit your initial post one (1) day late."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): You submit your initial post two (2) or "
                "more days late."
            ),
        },
    },
    "Engagement": {
        "max_points": 30,
        "ratings": {
            "exceeds": (
                "Exceeds Expectations (100%, 30 pts): You provide meaningful responses that "
                "are on-topic with clarifying explanation and detail by expanding on peers' "
                "comments in a value-adding way; promoting a collaborative, supportive "
                "community that advances the dialogue through follow-up questions."
            ),
            "meets": (
                "Meets Expectations (85%, 26 pts): You provide meaningful responses that "
                "are on-topic with sufficient explanation and detail by expanding on peers' "
                "comments; promoting a collaborative community that supports the dialogue "
                "through some follow-up questions."
            ),
            "needs": (
                "Needs Improvement (70%, 21 pts): You provide simplistic responses with "
                "limited explanation, detail and follow-up questions."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): You provide responses that lack explanation, "
                "detail and follow-up questions."
            ),
        },
    },
    "Writing": {
        "max_points": 20,
        "ratings": {
            "exceeds": (
                "Exceeds Expectations (100%, 20 pts): You write posts that are easily "
                "understood, clear, and concise using proper citation methods where "
                "applicable with no errors in citations."
            ),
            "meets": (
                "Meets Expectations (85%, 17 pts): You write posts that are easily "
                "understood using proper citation methods where applicable with few errors "
                "in citations."
            ),
            "needs": (
                "Needs Improvement (70%, 14 pts): You write posts that are understandable "
                "using proper citation methods where applicable with a number of errors in "
                "citations."
            ),
            "below": (
                "Below Expectations (0%, 0 pts): You write posts that others are not able "
                "to understand and does not use proper citation methods where applicable."
            ),
        },
    },
}
