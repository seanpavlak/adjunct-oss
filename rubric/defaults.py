"""
Default grading policies for the Discussion Rubric (2021).

Courses override via ``discussion_rubric.criteria[].grading_policy`` in courses.json.
"""

from typing import Any, Dict

DEFAULT_CRITERION_GRADING_POLICIES: Dict[str, Dict[str, Any]] = {
    "Comprehension": {
        "llm_guidance": (
            "Use exceeds when the initial post fully addresses every part of the "
            "discussion prompt with rich detail, critical thinking, and personal or "
            "professional examples (e.g. medicine, sonography, daily life). Use meets "
            "for adequate posts that are thinner or less developed. Reserve below for "
            "missing, off-topic, or clearly inadequate work."
        ),
        "lenient": True,
        "enforcement": {
            "type": "comprehension_effort",
            "min_chars_floor": 30,
            "min_chars_exceeds": 120,
        },
    },
    "Timeliness": {
        "llm_guidance": (
            "Timeliness is set from Canvas days-late-input when provided (0=meets, "
            "1 day=needs, 2+=below). Otherwise use 'meets' for on-time posts. Do not "
            "use 'exceeds' for timeliness (N/A in this rubric)."
        ),
        "lenient": True,
        "enforcement": {
            "type": "timeliness",
            "on_time_level": "meets",
        },
    },
    "Engagement": {
        "llm_guidance": (
            "Give 'exceeds' when the student has two or more thoughtful peer replies that "
            "advance the dialogue. Engagement MUST be 'below' (0 points) if there are no "
            "replies to classmates, and 'needs' or lower if fewer than two meaningful "
            "peer responses."
        ),
        "lenient": True,
        "enforcement": {
            "type": "min_meaningful_peer_replies",
            "min_count": 2,
            "min_chars_per_reply": 40,
            "level_when_zero": "below",
            "level_when_insufficient": "needs",
        },
    },
    "Writing": {
        "llm_guidance": (
            "Assess clarity and citation practice. Hyperlinks and APA-style reference "
            "entries (e.g. Author. (n.d.). Title. Retrieved [date], from Source (URL)) "
            "count as citations. Excellent clear writing without any citation should be "
            "meets, not exceeds. "
            "Do not use below for writing quality alone — reserve below for unclear or "
            "unintelligible posts."
        ),
        "lenient": True,
        "enforcement": {
            "type": "min_citations",
            "min_count": 1,
            "require_citation": True,
            "level_when_zero": "meets",
            "level_when_insufficient": "meets",
        },
    },
}

RUBRIC_GRADING_DEFAULTS: Dict[str, Any] = {
    "lenient": True,
    "global_llm_guidance": (
        "Rubric levels (1–4): 1=below, 2=needs, 3=meets, 4=exceeds. "
        "LENIENCY: When the work clearly fits one level, keep that level "
        "(a clear 1 stays 1; a clear 3 stays 3 — do not bump 3 to 4). "
        "When genuinely torn between two adjacent levels only — 1↔2 or 3↔4 — "
        "set borderline=true and choose the lower of the two in `level`; "
        "post-processing will optimistically bump one step. "
        "Do not use borderline=true when the level is a clear fit. "
        "Reserve level 1 (below) for missing or clearly inadequate work."
    ),
}
