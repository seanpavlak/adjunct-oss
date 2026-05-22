"""
Verify discussion submissions against course grading requirements.

Checks (configurable per course):
  - Initial post present and substantive
  - At least N meaningful peer replies to classmates
  - Initial post on time (Canvas days-late-input absent, or legacy preview text)
  - At least one citation when posts contain factual claims
"""

import re
from typing import Any, Dict, List, Optional  # noqa: F401 - Any used by llm_grader param

from submission_models import DiscussionSubmission, SubmissionEvaluation

# Boilerplate lines to drop when parsing iframe text
SKIP_TEXT_PATTERNS = [
    re.compile(r"submissions?\s+for\s+this", re.I),
    re.compile(r"^this\s+topic\s+is\s+closed", re.I),
    re.compile(r"^graded\s*:", re.I),
    re.compile(r"^posted\s+on\s*:", re.I),
    re.compile(r"^reply\s+to\s+", re.I),
    re.compile(r"^view\s+full\s+discussion", re.I),
]

# Peer reply cues (greeting a classmate by name)
PEER_REPLY_PATTERNS = [
    re.compile(r"^(hi|hello|hey|dear)\s+[A-Z][a-z]+", re.I),
    re.compile(r"^@"),
    re.compile(r"\bI agree with (you|your)\b", re.I),
    re.compile(r"\b(great|good|nice)\s+(point|post|thought)", re.I),
]

# URLs in post text or <a href> (student attempt at a source link)
URL_PATTERNS = [
    re.compile(r"https?://[^\s\]\)\"'<>]+", re.I),
    re.compile(r"\bwww\.[^\s\]\)\"'<>]+", re.I),
    re.compile(
        r"\b[a-z0-9][-a-z0-9]*\.(?:gov|edu|org|com|net|io|us)(?:/[^\s\]\)\"'<>]*)?",
        re.I,
    ),
]

# Canvas appends this to linked URLs in discussion preview text
CANVAS_LINK_SUFFIX = re.compile(
    r"\s*Links to an external site\.?\s*",
    re.I,
)

# Other citation / reference indicators
CITATION_PATTERNS = [
    re.compile(r"\bdoi:\s*\S+", re.I),
    re.compile(r"\bdoi\.org/", re.I),
    re.compile(r"\[[0-9]+\]"),
    re.compile(r"\([A-Z][a-z]+,?\s+\d{4}\)"),  # (Author, 2020)
    re.compile(r"\(\d{4},\s+[A-Za-z]+\s+\d{1,2}\)"),  # (2025, February 4)
    re.compile(r"\(n\.d\.\)", re.I),
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bretrieved from\b", re.I),
  # APA 7: Retrieved May 11, 2026, from Publisher (https://...)
    re.compile(
        r"\bRetrieved\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+from\b",
        re.I,
    ),
    # Org/Author. (n.d.). Title. Retrieved ...
    re.compile(
        r"(?im)^[\w\s&,'\-\.]+\.\s+\((?:n\.d\.|\d{4}[^)]*)\)\.\s+.+?\bRetrieved\s+",
    ),
    re.compile(r"\breferences?\s*:", re.I),
    re.compile(r"\bref[ei]ren?ces?\b", re.I),  # References / common typo Refrences
    re.compile(r"\bworks?\s+cited\s*:", re.I),
    re.compile(r"\bbibliography\s*:", re.I),
    re.compile(r"\b(?:apa|mla|chicago)\b", re.I),
    re.compile(r'".+"\s*\(\d{4}\)'),  # "Title" (2020)
    # Title. Publisher. (year...). https://...
    re.compile(
        r"\.[\s\S]{0,120}\(\d{4}[^)]*\)\.\s*https?://",
        re.I,
    ),
]

REFERENCE_HEADING = re.compile(
    r"(?i)\b(?:references?|refrences|works?\s+cited|bibliography)\b\s*:?\s*"
)

# APA reference list entry (ChatGPT / Canvas common format)
APA_REFERENCE_ENTRY = re.compile(
    r"(?im)"
    r"^[\w\s&,'\-\.]+\.\s+"
    r"\((?:n\.d\.|\d{4}[^)]*)\)\.\s+"
    r".+?"
    r"\bRetrieved\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+from\b"
    r".*?$"
)

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
    """
    Split iframe #content text into separate posts.

    Uses paragraph blocks and peer-reply cues to separate initial post from replies.
    """
    if not raw_text or not raw_text.strip():
        return []

    # Normalize and remove known header block about "submissions for this assignment"
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

    # If we only got one blob, try splitting on peer greeting mid-text
    if len(posts) == 1:
        split_posts = _split_on_peer_greetings(posts[0])
        if len(split_posts) > 1:
            posts = split_posts

    return [p for p in posts if len(p.strip()) >= 20]


def _split_on_peer_greetings(text: str) -> List[str]:
    """Split a single block when peer greetings appear after the initial post."""
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


def normalize_citation_corpus(text: str) -> str:
    """Strip Canvas link boilerplate so URLs and reference lines match reliably."""
    if not text:
        return ""
    cleaned = CANVAS_LINK_SUFFIX.sub(" ", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def extract_link_urls_from_text(text: str) -> List[str]:
    """Pull https URLs from post or iframe text (including reference lists)."""
    normalized = normalize_citation_corpus(text)
    urls: List[str] = []
    for pattern in (
        r"\((https?://[^)]+)\)",  # (https://www.nist.gov?utm_source=...)
        r"https?://[^\s\]\)\"'<>]+",
    ):
        for match in re.finditer(pattern, normalized, re.I):
            url = match.group(1) if match.lastindex else match.group(0)
            url = url.rstrip(".,;)")
            if url and url not in urls:
                urls.append(url)
    return urls


def _references_section_from_raw(raw_text: str) -> str:
    """
    Return the References / Works Cited block from full iframe text, if present.

    Canvas often includes this in ``raw_text`` but not in the first
    ``discussion_entry`` message body.
    """
    if not raw_text:
        return ""
    match = REFERENCE_HEADING.search(raw_text)
    if not match:
        return ""
    tail = raw_text[match.start() :].strip()
    # Stop before the next discussion post header when present in raw preview
    stop = re.search(
        r"\nfrom Week \d+ Discussion\n|\n(?:Hi|Hello|Hey|Dear)\s+[A-Z][a-z]+,",
        tail[20:],
        re.I,
    )
    if stop:
        tail = tail[: 20 + stop.start()].strip()
    return tail


def _bibliography_tail_from_raw(raw_text: str) -> str:
    """
    APA entries without a ``References`` heading, e.g.::

        NASA. (n.d.). Title. Retrieved May 11, 2026, from NASA (https://...)
    """
    if not raw_text:
        return ""
    entries = [m.group(0).strip() for m in APA_REFERENCE_ENTRY.finditer(raw_text)]
    if not entries:
        return ""
    return "\n\n".join(entries)


def enrich_initial_with_raw_references(initial: str, raw_text: str) -> str:
    """Append reference list from iframe text when missing from the parsed initial post."""
    section = _references_section_from_raw(raw_text) or _bibliography_tail_from_raw(raw_text)
    if not section:
        return initial
    if section.lower() in (initial or "").lower():
        return initial
    return f"{initial.rstrip()}\n\n{section}" if initial else section


def build_discussion_submission_from_entries(
    entry_messages: List[str],
    raw_text: str = "",
    is_late: bool = False,
    days_late: Optional[int] = None,
    link_urls: Optional[List[str]] = None,
) -> DiscussionSubmission:
    """
    Build a submission from Speed Grader discussion_entry blocks.

    Canvas lists one ``discussion_entry`` per post: the first is the student's
    initial post; the rest are peer replies.
    """
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


def _dedupe_urls(urls: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for url in urls:
        u = url.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_discussion_submission(
    raw_text: str,
    is_late: bool = False,
    days_late: Optional[int] = None,
    link_urls: Optional[List[str]] = None,
) -> DiscussionSubmission:
    """Build a DiscussionSubmission from raw iframe text (fallback when DOM parse fails)."""
    posts = split_content_into_posts(raw_text)
    initial = posts[0] if posts else ""
    replies = posts[1:] if len(posts) > 1 else []

    # Re-classify: lines that look like peer replies but landed in initial
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


def is_citable_url(href: str) -> bool:
    """True when an anchor href looks like an external source link (not mailto / in-page)."""
    h = (href or "").strip()
    if not h or h.startswith(("#", "mailto:", "javascript:")):
        return False
    if h.startswith("/") and not h.startswith("//"):
        return False
    return any(p.search(h) for p in URL_PATTERNS)


def submission_citation_corpus(submission: DiscussionSubmission) -> str:
    """All post text, iframe raw text, and link URLs for citation detection."""
    parts = [submission.initial_post, *submission.peer_replies]
    if submission.raw_text:
        parts.append(normalize_citation_corpus(submission.raw_text))
    parts.extend(submission.link_urls)
    return "\n".join(p for p in parts if p)


def count_citations(
    text: str = "",
    *,
    link_urls: Optional[List[str]] = None,
    submission: Optional[DiscussionSubmission] = None,
) -> int:
    """
    Count citation indicators in post text and/or link URLs.

    A single https/www link (including from Canvas ``<a href>``) counts as a citation.
    """
    if submission is not None:
        corpus = submission_citation_corpus(submission)
    else:
        corpus = text or ""
        if link_urls:
            corpus = corpus + "\n" + "\n".join(link_urls)

    if not corpus.strip():
        return 0

    corpus = normalize_citation_corpus(corpus)

    found = 0
    if any(p.search(corpus) for p in URL_PATTERNS):
        found += 1
    for pattern in CITATION_PATTERNS:
        if pattern.search(corpus):
            found += 1
    return found


def detect_late_submission(raw_text: str) -> bool:
    """Detect late submission markers in preview text."""
    return any(p.search(raw_text) for p in LATE_PATTERNS)


def timeliness_level_from_days_late(days_late: int) -> str:
    """
    Map Canvas days-late count to Discussion Rubric (2021) timeliness levels.

    - 0 days (edge case): meets (on time)
    - 1 day: needs
    - 2+ days: below
    """
    if days_late <= 0:
        return "meets"
    if days_late == 1:
        return "needs"
    return "below"


def evaluate_submission(
    submission: DiscussionSubmission,
    requirements: Dict[str, Any],
    rubric_rating_levels: Optional[Dict[str, Dict[str, str]]] = None,
    discussion_prompt: str = "",
    llm_grader: Optional[Any] = None,
    dry_run: bool = False,
) -> SubmissionEvaluation:
    """Grade submission via LLM rubric assessment (required)."""
    if llm_grader is None:
        raise ValueError(
            "LLM grader is required. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY."
        )
    return llm_grader.grade(
        submission,
        discussion_prompt=discussion_prompt,
        rubric_rating_levels=rubric_rating_levels,
        requirements=requirements,
        dry_run=dry_run,
    )


def _grade_from_levels(levels: Dict[str, str]) -> str:
    """Approximate total points from rubric level keys (for non-passing submissions)."""
    points_map = {
        "exceeds": 1.0,
        "meets": 0.85,
        "needs": 0.70,
        "below": 0.0,
    }
    criterion_points = {
        "Comprehension": 40,
        "Timeliness": 10,
        "Engagement": 30,
        "Writing": 20,
    }
    total = 0.0
    for name, pts in criterion_points.items():
        level = levels.get(name, "below")
        total += pts * points_map.get(level, 0.0)
    return str(int(round(total)))
