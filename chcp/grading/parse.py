"""Parse Speed Grader discussion preview into DiscussionSubmission."""

from __future__ import annotations

import re
from typing import List, Optional, Union

from chcp.grading.citations import (
    APA_REFERENCE_ENTRY,
    REFERENCE_HEADING,
    extract_link_urls_from_text,
)
from chcp.submission_models import DiscussionSubmission

SKIP_TEXT_PATTERNS = [
    re.compile(r"submissions?\s+for\s+this", re.I),
    re.compile(r"^this\s+topic\s+is\s+closed", re.I),
    re.compile(r"^graded\s*:", re.I),
    re.compile(r"^posted\s+on\s*:", re.I),
    re.compile(r"^reply\s+to\s+", re.I),
    re.compile(r"^view\s+full\s+discussion", re.I),
]

PEER_REPLY_PATTERNS = [
    re.compile(r"^(hi|hello|hey|dear)\s+[A-Z][a-z]+", re.I),
    re.compile(r"^@"),
    re.compile(r"\bI agree with (you|your)\b", re.I),
    re.compile(r"\b(great|good|nice)\s+(point|post|thought)", re.I),
]

LATE_PATTERNS = [
    re.compile(r"\blate\s+submission\b", re.I),
    re.compile(r"\bsubmitted\s+late\b", re.I),
    re.compile(r"\b\d+\s+days?\s+late\b", re.I),
]


def _should_skip_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return True
    return any(p.search(stripped) for p in SKIP_TEXT_PATTERNS)


def split_content_into_posts(raw_text: str) -> List[str]:
    if not raw_text or not raw_text.strip():
        return []

    text = re.sub(
        r"The submissions for this[^.]*\.?",
        "",
        raw_text,
        flags=re.I,
    )
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    paragraphs = [p for p in paragraphs if not _should_skip_text(p)]

    if not paragraphs:
        return []

    posts: List[str] = []
    current: List[str] = []

    for para in paragraphs:
        is_new_peer_reply = any(p.search(para) for p in PEER_REPLY_PATTERNS)
        if current and is_new_peer_reply and len(current) >= 1:
            posts.append("\n".join(current))
            current = [para]
        else:
            current.append(para)

    if current:
        posts.append("\n".join(current))

    if len(posts) == 1:
        split_posts = _split_on_peer_greetings(posts[0])
        if len(split_posts) > 1:
            posts = split_posts

    return [p for p in posts if len(p.strip()) >= 20]


def _split_on_peer_greetings(text: str) -> List[str]:
    pattern = re.compile(
        r"(?=(?:^|\n)(?:Hi|Hello|Hey|Dear)\s+[A-Z][a-z]+)",
        re.MULTILINE,
    )
    parts = [p.strip() for p in pattern.split(text) if p.strip()]
    return parts if len(parts) > 1 else [text]


def _is_meaningful_entry_text(text: str, min_chars: int = 10) -> bool:
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    if stripped in ("\xa0", "&nbsp;"):
        return False
    return not _should_skip_text(stripped)


def _references_section_from_raw(raw_text: str) -> str:
    if not raw_text:
        return ""
    match = REFERENCE_HEADING.search(raw_text)
    if not match:
        return ""
    tail = raw_text[match.start() :].strip()
    stop = re.search(
        r"\nfrom Week \d+ Discussion\n|\n(?:Hi|Hello|Hey|Dear)\s+[A-Z][a-z]+,",
        tail[20:],
        re.I,
    )
    if stop:
        tail = tail[: 20 + stop.start()].strip()
    return tail


def _bibliography_tail_from_raw(raw_text: str) -> str:
    if not raw_text:
        return ""
    entries = [m.group(0).strip() for m in APA_REFERENCE_ENTRY.finditer(raw_text)]
    if not entries:
        return ""
    return "\n\n".join(entries)


def enrich_initial_with_raw_references(initial: str, raw_text: str) -> str:
    section = _references_section_from_raw(raw_text) or _bibliography_tail_from_raw(raw_text)
    if not section:
        return initial
    if section.lower() in (initial or "").lower():
        return initial
    return f"{initial.rstrip()}\n\n{section}" if initial else section


def _dedupe_urls(urls: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for url in urls:
        u = url.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def build_discussion_submission_from_entries(
    entry_messages: List[str],
    raw_text: str = "",
    is_late: bool = False,
    days_late: Optional[float] = None,
    link_urls: Optional[List[str]] = None,
) -> DiscussionSubmission:
    messages = [m.strip() for m in entry_messages if _is_meaningful_entry_text(m)]
    initial = enrich_initial_with_raw_references(
        messages[0] if messages else "",
        raw_text,
    )
    merged_urls = _dedupe_urls(
        list(link_urls or []) + extract_link_urls_from_text(raw_text)
    )
    return DiscussionSubmission(
        initial_post=initial,
        peer_replies=messages[1:] if len(messages) > 1 else [],
        all_posts=list(messages),
        is_late=is_late,
        days_late=days_late,
        link_urls=merged_urls,
        raw_text=raw_text,
    )


def parse_discussion_submission(
    raw_text: str,
    is_late: bool = False,
    days_late: Optional[float] = None,
    link_urls: Optional[List[str]] = None,
) -> DiscussionSubmission:
    posts = split_content_into_posts(raw_text)
    initial = posts[0] if posts else ""
    replies = posts[1:] if len(posts) > 1 else []

    if not replies and initial:
        split = _split_on_peer_greetings(initial)
        if len(split) > 1:
            initial = split[0]
            replies = split[1:]

    initial = enrich_initial_with_raw_references(initial.strip(), raw_text)
    merged_urls = _dedupe_urls(
        list(link_urls or []) + extract_link_urls_from_text(raw_text)
    )
    return DiscussionSubmission(
        initial_post=initial,
        peer_replies=[r.strip() for r in replies if r.strip()],
        all_posts=posts,
        is_late=is_late,
        days_late=days_late,
        link_urls=merged_urls,
        raw_text=raw_text,
    )


def detect_late_submission(raw_text: str) -> bool:
    return any(p.search(raw_text) for p in LATE_PATTERNS)


def timeliness_level_from_days_late(days_late: Union[int, float]) -> str:
    """
    Map Canvas days-late to Discussion Rubric (2021) timeliness bands.

    Fractional Canvas values are rounded to the nearest whole day (standard
    ``round``): 0.49 → on time, 0.51 → one day late (needs), 2.0+ → below.
    """
    whole_days = round(float(days_late))
    if whole_days <= 0:
        return "meets"
    if whole_days == 1:
        return "needs"
    return "below"
