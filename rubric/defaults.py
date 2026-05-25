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
            "Grade each peer reply to a classmate separately. A substantive reply greets "
            "the peer and adds detail, an example, a question, or clinical insight — not "
            "only 'I agree' or 'great point'. Exceeds: two or more substantive replies "
            "that advance dialogue. Meets: two meaningful replies with adequate explanation. "
            "Needs: only one substantive reply, or two replies that are thin/agreement-only. "
            "Below: no replies to classmates. Use the automated peer-reply flags in the "
            "submission packet."
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
        },
    },
    "Writing": {
        "llm_guidance": (
            "Assess clarity and citation practice. Count as citations: any URL or "
            "hyperlink, APA/MLA-style reference entries, parenthetical author-year, "
            "and citation attempts (Sources:, Author, 2019, partial refs, et al.). "
            "Excellent clear writing without any source reference should be meets, "
            "not exceeds. Do not use below for writing quality alone — reserve below "
            "for unclear or unintelligible posts."
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
        "You receive an AUTOMATED PRE-GRADE CHECKLIST — treat it as ground truth for "
        "counts (peer replies, citations, lateness) unless the student text clearly "
        "contradicts it. Your job is to judge quality (depth, on-topic, dialogue value) "
        "within those facts. LENIENCY: When the work clearly fits one level, keep it. "
        "When genuinely torn between adjacent levels only (1↔2 or 3↔4), set borderline=true "
        "and pick the lower level; post-processing may bump one step. "
        "Reserve below for missing or clearly inadequate work."
    ),
}
