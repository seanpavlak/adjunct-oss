"""
Default grading policies for the Discussion Rubric (2021).

Courses override via ``discussion_rubric.criteria[].grading_policy`` in courses.json.
"""

from typing import Any, Dict

DEFAULT_CRITERION_GRADING_POLICIES: Dict[str, Dict[str, Any]] = {
    "Comprehension": {
        "llm_guidance": (
            "Read the discussion prompt first, then judge ONLY the initial post (not peer "
            "replies). Exceeds: fully addresses all parts of the prompt with critical "
            "thinking, analysis, and rich examples (healthcare, sonography, personal "
            "experience). Meets: addresses the prompt with adequate detail. Needs: "
            "partially addresses the prompt or lacks depth/organization. Below: missing, "
            "off-topic, or far too short to demonstrate understanding."
        ),
        "lenient": True,
        "enforcement": {
            "type": "comprehension_effort",
            "min_chars_floor": 30,
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
        "When genuinely torn between adjacent levels only (1↔2 or 3↔4), set borderline=true "
        "and pick the lower level; post-processing may bump one step. "
        "Reserve below for missing or clearly inadequate work."
    ),
}
