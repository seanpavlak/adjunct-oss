"""Pre-LLM analysis: measurable facts the grader and enforcement rely on."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from grading.citations import (
    CITATION_PATTERNS,
    CitationReport,
    REFERENCE_HEADING,
    build_citation_report,
    extract_link_urls_from_text,
)
from grading.parse import detect_late_submission, timeliness_level_from_days_late
from submission_models import DiscussionSubmission

# Peer reply cues (shared with parse)
_GREETING = re.compile(r"^(?:hi|hello|hey|dear)\s+([A-Z][a-z]+)", re.I)
_AGREE_ONLY_BODY = re.compile(
    r"^(?:i\s+agree(?:\s+with\s+(?:you|your(?:\s+point)?))?\.?|"
    r"(?:great|good|nice)\s+(?:point|post|thought|perspective)\.?|"
    r"well\s+said\.?|"
    r"thanks\s+for\s+sharing\.?)+[\s\W]*$",
    re.I,
)

# Topic tie-in, career/learning reflection, or enough depth for Engagement exceeds
_DIALOGUE_DEPTH = re.compile(
    r"\b("
    r"beneficial|career|field|learn(?:ing)?|formulas?|physics|semester|excited|"
    r"hands-on|important|discuss(?:ing)?|velocity|acceleration|position|metric|"
    r"helps?\s+you|can't wait|professionals?|together|step by step|"
    r"question|wonder|example|sonograph|clinical|patient|week|readings?"
    r")\b",
    re.I,
)


@dataclass
class PeerReplyMetrics:
    index: int
    text: str
    char_count: int
    word_count: int
    greets_classmate: bool
    is_meaningful: bool
    is_substantive: bool
    qualifies_for_exceeds_engagement: bool
    preview: str


@dataclass
class InitialPostRichness:
    """Signals that separate a rich initial post (exceeds-worthy) from a thin one."""

    word_count: int = 0
    char_count: int = 0
    paragraph_count: int = 0
    has_references_section: bool = False
    has_in_text_citation: bool = False
    richness_signals: List[str] = field(default_factory=list)
    signal_count: int = 0
    qualifies_for_exceeds: bool = False


def _paragraph_count(text: str) -> int:
    blocks = [p.strip() for p in re.split(r"\n\s*\n+", text) if len(p.strip()) >= 40]
    return len(blocks) if blocks else (1 if len((text or "").strip()) >= 40 else 0)


def assess_initial_post_richness(
    initial_post: str,
    *,
    min_words: int = 130,
    min_chars: int = 700,
    min_paragraphs: int = 2,
    min_signals_for_exceeds: int = 3,
) -> InitialPostRichness:
    """
    Richness bar for Comprehension exceeds (not raw length alone).

    Typical exceeds profile: multi-paragraph, ~130+ words, optional references/URLs
    (e.g. Beatriz-style). Thin single-paragraph posts (e.g. Brister-style) do not qualify
    even if they clear the course minimum length (~100 chars).
    """
    initial = (initial_post or "").strip()
    words = _word_count(initial)
    chars = len(initial)
    paragraphs = _paragraph_count(initial)
    has_refs = bool(REFERENCE_HEADING.search(initial))
    urls = extract_link_urls_from_text(initial)
    has_cite = bool(urls) or any(p.search(initial) for p in CITATION_PATTERNS)

    signals: List[str] = []
    if words >= min_words:
        signals.append(f"words>={min_words}")
    if chars >= min_chars:
        signals.append(f"chars>={min_chars}")
    if paragraphs >= min_paragraphs:
        signals.append(f"paragraphs>={min_paragraphs}")
    if has_refs:
        signals.append("references_section")
    if has_cite:
        signals.append("citations_or_urls")

    count = len(signals)
    qualifies = count >= min_signals_for_exceeds

    return InitialPostRichness(
        word_count=words,
        char_count=chars,
        paragraph_count=paragraphs,
        has_references_section=has_refs,
        has_in_text_citation=has_cite,
        richness_signals=signals,
        signal_count=count,
        qualifies_for_exceeds=qualifies,
    )


@dataclass
class SubmissionAnalysis:
    """Structured facts passed to the LLM and post-processing enforcement."""

    submission: DiscussionSubmission
    min_peer_replies: int = 2
    min_peer_reply_chars: int = 40
    min_initial_post_chars: int = 100
    min_citations: int = 1

    initial_char_count: int = 0
    initial_word_count: int = 0
    initial_meets_length: bool = False
    initial_richness: InitialPostRichness = field(default_factory=InitialPostRichness)

    peer_replies: List[PeerReplyMetrics] = field(default_factory=list)
    meaningful_peer_count: int = 0
    substantive_peer_count: int = 0
    engagement_exceeds_peer_count: int = 0
    engagement_qualifies_for_exceeds: bool = False

    citation_report: CitationReport = field(default_factory=CitationReport)
    citation_count: int = 0

    days_late: Optional[int] = None
    on_time: bool = True
    timeliness_level_hint: str = "meets"
    timeliness_summary: str = ""

    checklist: List[str] = field(default_factory=list)
    engagement_summary: str = ""
    writing_summary: str = ""
    comprehension_summary: str = ""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _strip_greeting(text: str) -> str:
    return re.sub(
        r"^(?:hi|hello|hey|dear)\s+[A-Za-z]+[,!\.\s]*",
        "",
        (text or "").strip(),
        count=1,
        flags=re.I,
    ).strip()


def is_substantive_peer_reply(text: str, min_chars: int = 40) -> bool:
    """
    True when a peer reply goes beyond a brief agreement or greeting.

    Meaningful length plus body that is not only "I agree" / "great point".
    """
    stripped = (text or "").strip()
    if len(stripped) < min_chars:
        return False
    body = _strip_greeting(stripped)
    if len(body) < 25:
        return False
    if _AGREE_ONLY_BODY.match(body):
        return False
    if len(body.split()) < 8 and not re.search(
        r"\b(because|example|clinical|patient|sonograph|however|question|wonder)\b",
        body,
        re.I,
    ):
        return False
    return True


def is_engagement_exceeds_quality(text: str, min_chars: int = 40) -> bool:
    """
    True when a peer reply supports Engagement exceeds — not only agreement.

    Examples: greets a classmate, ties the week's topic to their field or learning,
    and adds a few sentences of reflection (typical strong undergraduate replies).
    """
    if not is_substantive_peer_reply(text, min_chars):
        return False
    body = _strip_greeting((text or "").strip())
    if len(body.split()) >= 18:
        return True
    if _DIALOGUE_DEPTH.search(body):
        return True
    if "?" in body:
        return True
    return False


def analyze_peer_reply(text: str, index: int, min_chars: int) -> PeerReplyMetrics:
    stripped = (text or "").strip()
    char_count = len(stripped)
    meaningful = char_count >= min_chars
    substantive = is_substantive_peer_reply(stripped, min_chars) if meaningful else False
    exceeds_quality = (
        is_engagement_exceeds_quality(stripped, min_chars) if substantive else False
    )
    preview = stripped[:200] + ("…" if char_count > 200 else "")
    return PeerReplyMetrics(
        index=index,
        text=stripped,
        char_count=char_count,
        word_count=_word_count(stripped),
        greets_classmate=bool(_GREETING.search(stripped)),
        is_meaningful=meaningful,
        is_substantive=substantive,
        qualifies_for_exceeds_engagement=exceeds_quality,
        preview=preview,
    )


def analyze_submission(
    submission: DiscussionSubmission,
    requirements: Optional[Mapping[str, Any]] = None,
) -> SubmissionAnalysis:
    req = dict(requirements or {})
    min_peer = int(req.get("min_peer_replies", 2))
    min_peer_chars = int(req.get("min_peer_reply_chars", 40))
    min_initial = int(req.get("min_initial_post_chars", 100))
    min_citations = int(req.get("min_citations", 1))

    initial = (submission.initial_post or "").strip()
    initial_chars = len(initial)
    initial_words = _word_count(initial)
    min_richness_signals = int(req.get("min_comprehension_richness_signals", 3))
    initial_richness = assess_initial_post_richness(
        initial,
        min_signals_for_exceeds=min_richness_signals,
    )

    peer_metrics = [
        analyze_peer_reply(reply, i + 1, min_peer_chars)
        for i, reply in enumerate(submission.peer_replies)
    ]
    meaningful = sum(1 for p in peer_metrics if p.is_meaningful)
    substantive = sum(1 for p in peer_metrics if p.is_substantive)
    exceeds_engagement = sum(1 for p in peer_metrics if p.qualifies_for_exceeds_engagement)
    engagement_qualifies_for_exceeds = (
        substantive >= min_peer and exceeds_engagement >= min_peer
    )

    citation_report = build_citation_report(submission=submission)
    citation_count = citation_report.total_signals

    days_late = submission.days_late
    if days_late is not None:
        on_time = days_late <= 0
        timeliness_hint = timeliness_level_from_days_late(days_late)
        if days_late <= 0:
            timeliness_summary = "On time (0 days late per Canvas)."
        elif days_late == 1:
            timeliness_summary = "1 day late → rubric timeliness: needs."
        else:
            timeliness_summary = f"{days_late} days late → rubric timeliness: below."
    else:
        on_time = not submission.is_late and not detect_late_submission(
            submission.raw_text
        )
        timeliness_hint = "meets" if on_time else "needs"
        timeliness_summary = (
            "On time (no days-late field)."
            if on_time
            else "Late indicator in preview text."
        )

    checklist: List[str] = []
    checklist.append(
        f"Initial post: {initial_chars} chars, {initial_words} words, "
        f"{initial_richness.paragraph_count} paragraph(s) "
        f"(course minimum ~{min_initial} chars; exceeds bar: "
        f"{initial_richness.signal_count}/{min_richness_signals} richness signals "
        f"{initial_richness.richness_signals or 'none'})."
    )
    checklist.append(
        f"Peer replies: {len(peer_metrics)} total, {meaningful} meaningful "
        f"(≥{min_peer_chars} chars), {substantive} substantive (on-topic, not agreement-only). "
        f"Required: {min_peer} meaningful replies to classmates."
    )
    checklist.append(
        f"Citations: {citation_count} signal(s), {len(citation_report.urls)} URL(s). "
        f"Required: ≥{min_citations} (URLs, formatted refs, or citation attempts all count)."
    )
    checklist.append(f"Timeliness: {timeliness_summary}")

    if engagement_qualifies_for_exceeds:
        engagement_summary = (
            f"Engagement exceeds bar met ({exceeds_engagement} strong peer replies with "
            "topic/career tie-in) — two substantive classmate responses that advance dialogue."
        )
    elif substantive >= min_peer and meaningful >= min_peer:
        engagement_summary = (
            f"Meets peer-reply count ({substantive} substantive); grade whether replies "
            "add enough detail for exceeds."
        )
    elif meaningful >= min_peer:
        engagement_summary = (
            f"Has {meaningful} length-qualified replies but only {substantive} are substantive — "
            "grade Engagement on whether replies add detail, questions, or examples."
        )
    elif meaningful > 0:
        engagement_summary = (
            f"Only {meaningful}/{min_peer} meaningful replies — Engagement capped at needs or below."
        )
    else:
        engagement_summary = "No meaningful peer replies — Engagement must be below."

    if citation_report.has_quality_source:
        writing_summary = (
            "Quality source cited (URL, reference list, or book/journal line) — "
            "if the post is clear and understandable, Writing should be exceeds."
        )
    elif citation_report.has_any_citation:
        writing_summary = (
            "Weak citation attempt only — Writing is typically meets unless the source is clear."
        )
    else:
        writing_summary = (
            "No citation signals detected — Writing cannot exceed meets unless you find a source in the text."
        )

    if initial_richness.qualifies_for_exceeds:
        comprehension_summary = (
            "Initial post meets exceeds richness bar (depth, structure, and/or sources) — "
            "Comprehension may be exceeds if the prompt is fully addressed with critical thinking."
        )
    elif initial_chars >= min_initial:
        comprehension_summary = (
            "Initial post meets minimum length but not exceeds richness (single thin block or "
            "no sources) — Comprehension typically meets unless the LLM finds strong depth."
        )
    elif initial_chars >= 30:
        comprehension_summary = (
            "Initial post is short; grade Comprehension on whether the prompt is adequately addressed."
        )
    else:
        comprehension_summary = "Initial post very short or missing — Comprehension likely below."

    return SubmissionAnalysis(
        submission=submission,
        min_peer_replies=min_peer,
        min_peer_reply_chars=min_peer_chars,
        min_initial_post_chars=min_initial,
        min_citations=min_citations,
        initial_char_count=initial_chars,
        initial_word_count=initial_words,
        initial_meets_length=initial_chars >= min_initial,
        initial_richness=initial_richness,
        peer_replies=peer_metrics,
        meaningful_peer_count=meaningful,
        substantive_peer_count=substantive,
        engagement_exceeds_peer_count=exceeds_engagement,
        engagement_qualifies_for_exceeds=engagement_qualifies_for_exceeds,
        citation_report=citation_report,
        citation_count=citation_count,
        days_late=days_late,
        on_time=on_time,
        timeliness_level_hint=timeliness_hint,
        timeliness_summary=timeliness_summary,
        checklist=checklist,
        engagement_summary=engagement_summary,
        writing_summary=writing_summary,
        comprehension_summary=comprehension_summary,
    )
