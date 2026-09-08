"""
Default grading policies for the Discussion Rubric (2021).

Courses override via ``discussion_rubric.criteria[].grading_policy`` in courses.json.
"""

from typing import Any, Dict

DEFAULT_CRITERION_GRADING_POLICIES: Dict[str, Dict[str, Any]] = {
    "Comprehension": {
        "llm_guidance": (
            "Read the discussion prompt first, then judge ONLY the initial post (not peer "
            "replies). Be slightly generous at the undergraduate level. Exceeds: a "
            "well-organized post that thinks critically on the topic by integrating the "
            "student's own thoughts, analysis, or experiences with rich and significant "
            "detail — a complete solid answer counts; do not require exhaustive or "
            "graduate-level depth. Meets: organized and on-topic with adequate detail, "
            "but thinner or missing a requested part. Needs: gaps in organization or only "
            "a basic understanding, lacking adequate detail. Below: missing, off-topic, "
            "or far too short. When torn between meets and exceeds, choose exceeds."
        ),
        "lenient": True,
        "enforcement": {
            "type": "comprehension_effort",
            "min_chars_floor": 30,
        },
    },
    "Timeliness": {
        "llm_guidance": (
            "Timeliness follows Canvas days-late-input rounded to the nearest whole "
            "day (0.49→on time/meets, 0.51→1 day/needs, 2+→below). Do not use "
            "'exceeds' for timeliness (N/A in this rubric)."
        ),
        "lenient": True,
        "enforcement": {
            "type": "timeliness",
            "on_time_level": "meets",
        },
    },
    "Engagement": {
        "llm_guidance": (
            "Grade each peer reply separately. Exceeds: two replies that greet a classmate "
            "by name and add real content — tie the week's topic to their field, learning, "
            "or experience (not only 'I agree' or 'great point'). Meets: two on-topic replies "
            "with some explanation but thinner. Needs: one strong reply or two thin ones. "
            "Below: no classmate replies. Use exceeds-quality flags in the submission packet."
        ),
        "lenient": True,
        "enforcement": {
            "type": "min_meaningful_peer_replies",
            "min_count": 2,
            "min_substantive": 2,
            "min_chars_per_reply": 40,
            "level_when_zero": "below",
            "level_when_insufficient": "needs",
            "level_when_low_quality": "needs",
            "promote_meets_to_exceeds_when_strong": True,
        },
    },
    "Writing": {
        "llm_guidance": (
            "Assess clarity and citation practice. Exceeds: easily understood writing "
            "plus at least one real source — URL, APA reference list, or textbook/journal "
            "line (e.g. Author, I. I. (2024). Title (10th ed.). Publisher). Meets: clear "
            "writing with no source, or weak citation attempts only. Do not use below for "
            "writing quality alone."
        ),
        "lenient": True,
        "enforcement": {
            "type": "min_citations",
            "min_count": 1,
            "require_citation": True,
            "level_when_zero": "meets",
            "level_when_insufficient": "meets",
            "promote_meets_to_exceeds_when_cited": True,
        },
    },
}

RUBRIC_GRADING_DEFAULTS: Dict[str, Any] = {
    "lenient": True,
    "global_llm_guidance": (
        "Rubric levels (1–4): 1=below, 2=needs, 3=meets, 4=exceeds. "
        "You receive an AUTOMATED PRE-GRADE CHECKLIST — treat it as ground truth for "
        "counts (peer replies, citations, lateness) unless the student text clearly "
        "contradicts it. Your job is to judge quality (depth, on-topic, dialogue value) "
        "within those facts. LENIENCY: When the work clearly fits one level, keep it. "
        "When genuinely torn between adjacent levels only (1↔2 or 3↔4), set "
        "borderline=true. For Comprehension, prefer exceeds over meets when torn. "
        "For other criteria, pick the lower level; post-processing may bump one step. "
        "Reserve below for missing or clearly inadequate work."
    ),
}
