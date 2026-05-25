"""Citation detection for discussion submissions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from submission_models import DiscussionSubmission

URL_PATTERNS = [
    re.compile(r"https?://[^\s\]\)\"'<>]+", re.I),
    re.compile(r"\bwww\.[^\s\]\)\"'<>]+", re.I),
    re.compile(
        r"\b[a-z0-9][-a-z0-9]*\.(?:gov|edu|org|com|net|io|us|info|co|uk|ca|int|me|tv)"
        r"(?:/[^\s\]\)\"'<>]*)?",
        re.I,
    ),
]

CITATION_ATTEMPT_PATTERNS = [
    re.compile(r"\bsource[s]?\s*:", re.I),
    re.compile(r"\bcitation[s]?\s*:", re.I),
    re.compile(r"\bworks?\s+cited\b", re.I),
    re.compile(r"\bbibliography\b", re.I),
    re.compile(r"\bcited\s+(?:from|in|at|by)\b", re.I),
    re.compile(r"\bavailable\s+at\s*:", re.I),
    re.compile(r"\baccessed\s+on\b", re.I),
    re.compile(r"\bread\s+more\s+(?:at|here)\b", re.I),
    re.compile(r"\bsee\s+(?:also\s+)?(?:at|here)\s*:", re.I),
    re.compile(r"\bet\s+al\.?\b", re.I),
    re.compile(r"\bpp\.\s*\d+", re.I),
    re.compile(r"\bvol\.\s*\d+", re.I),
    re.compile(r"\bISBN[\s:-]*[\d\-Xx]+", re.I),
    re.compile(r"\b(?:19|20)\d{2}\)\s*\."),
    re.compile(r"\([A-Za-z][A-Za-z\s&'\-]+,?\s+(?:19|20)\d{2}\)"),
    re.compile(r"\b[A-Z][a-z]+,\s+(?:19|20)\d{2}\b"),
    re.compile(r"\b(?:19|20)\d{2},\s+[A-Za-z]+\s+\d{1,2}\)"),
    re.compile(r"\b(?:n\.d\.|no\s+date)\b", re.I),
    re.compile(r"\b(?:apa|mla|chicago|harvard)\s+(?:style|format|7|8)?\b", re.I),
]

CANVAS_LINK_SUFFIX = re.compile(r"\s*Links to an external site\.?\s*", re.I)

CITATION_PATTERNS = [
    re.compile(r"\bdoi:\s*\S+", re.I),
    re.compile(r"\bdoi\.org/", re.I),
    re.compile(r"\[[0-9]+\]"),
    re.compile(r"\([A-Z][a-z]+,?\s+\d{4}\)"),
    re.compile(r"\(\d{4},\s+[A-Za-z]+\s+\d{1,2}\)"),
    re.compile(r"\(n\.d\.\)", re.I),
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bretrieved from\b", re.I),
    re.compile(r"\bRetrieved\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+from\b", re.I),
    re.compile(
        r"(?im)^[\w\s&,'\-\.]+\.\s+\((?:n\.d\.|\d{4}[^)]*)\)\.\s+.+?\bRetrieved\s+",
    ),
    re.compile(r"\breferences?\s*:", re.I),
    re.compile(r"\bref[ei]ren?ces?\b", re.I),
    re.compile(r"\bworks?\s+cited\s*:", re.I),
    re.compile(r"\bbibliography\s*:", re.I),
    re.compile(r"\b(?:apa|mla|chicago)\b", re.I),
    re.compile(r'".+"\s*\(\d{4}\)'),
    re.compile(r"\.[\s\S]{0,120}\(\d{4}[^)]*\)\.\s*https?://", re.I),
]

REFERENCE_HEADING = re.compile(
    r"(?i)\b(?:references?|refrences|works?\s+cited|bibliography)\b\s*:?\s*"
)

APA_REFERENCE_ENTRY = re.compile(
    r"(?im)"
    r"^[\w\s&,'\-\.]+\.\s+"
    r"\((?:n\.d\.|\d{4}[^)]*)\)\.\s+"
    r".+?"
    r"\bRetrieved\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+from\b"
    r".*?$"
)

# Textbook / journal lines without URL (e.g. Griffith, W. T. (2024). Title (10th ed.). Publisher)
BOOK_REFERENCE_PATTERNS = [
    re.compile(r",\s*(?:19|20)\d{2}\)\.\s+[A-Za-z]"),
    re.compile(r"\(\d{1,2}(?:st|nd|rd|th)\s+ed\.?\)", re.I),
    re.compile(
        r"\b[A-Za-z][A-Za-z\.\s&']+,\s+(?:[A-Z]\.\s*)*(?:19|20)\d{2}\)",
    ),
]


@dataclass
class CitationReport:
    """Structured citation signals for grading and enforcement."""

    urls: List[str] = field(default_factory=list)
    has_formatted_reference_block: bool = False
    has_traditional_citation: bool = False
    has_book_or_journal_reference: bool = False
    has_citation_attempt: bool = False
    signal_labels: List[str] = field(default_factory=list)

    @property
    def total_signals(self) -> int:
        n = len(self.urls)
        if self.has_formatted_reference_block:
            n += 1
        if self.has_traditional_citation:
            n += 1
        if self.has_book_or_journal_reference:
            n += 1
        if self.has_citation_attempt:
            n += 1
        return max(n, len(self.signal_labels))

    @property
    def has_any_citation(self) -> bool:
        return self.total_signals > 0 or bool(self.urls)

    @property
    def has_quality_source(self) -> bool:
        """True when the student cited a real source (not only a vague 'Sources:' label)."""
        return bool(
            self.urls
            or self.has_formatted_reference_block
            or self.has_traditional_citation
            or self.has_book_or_journal_reference
        )


def normalize_citation_corpus(text: str) -> str:
    if not text:
        return ""
    cleaned = CANVAS_LINK_SUFFIX.sub(" ", text)
    return re.sub(r"[ \t]+", " ", cleaned)


def extract_link_urls_from_text(text: str) -> List[str]:
    normalized = normalize_citation_corpus(text)
    urls: List[str] = []
    for pattern in (
        r"\((https?://[^)]+)\)",
        r"https?://[^\s\]\)\"'<>]+",
    ):
        for match in re.finditer(pattern, normalized, re.I):
            url = match.group(1) if match.lastindex else match.group(0)
            url = url.rstrip(".,;)")
            if url and url not in urls:
                urls.append(url)
    return urls


def _collect_citation_urls(corpus: str) -> List[str]:
    urls = extract_link_urls_from_text(corpus)
    seen = set(urls)
    for pattern in URL_PATTERNS:
        for match in pattern.finditer(corpus):
            url = match.group(0).rstrip(".,;)")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def submission_citation_corpus(submission: DiscussionSubmission) -> str:
    parts = [submission.initial_post, *submission.peer_replies]
    if submission.raw_text:
        parts.append(normalize_citation_corpus(submission.raw_text))
    parts.extend(submission.link_urls)
    return "\n".join(p for p in parts if p)


def is_citable_url(href: str) -> bool:
    h = (href or "").strip()
    if not h or h.startswith(("#", "mailto:", "javascript:", "data:")):
        return False
    if h.startswith("/") and not h.startswith("//"):
        return False
    lower = h.lower()
    if lower.startswith(("http://", "https://", "www.", "//")):
        return True
    return any(p.search(h) for p in URL_PATTERNS)


def build_citation_report(
    submission: Optional[DiscussionSubmission] = None,
    text: str = "",
    *,
    link_urls: Optional[List[str]] = None,
) -> CitationReport:
    if submission is not None:
        corpus = submission_citation_corpus(submission)
    else:
        corpus = text or ""
        if link_urls:
            corpus = corpus + "\n" + "\n".join(link_urls)

    if not corpus.strip():
        return CitationReport()

    corpus = normalize_citation_corpus(corpus)
    urls = _collect_citation_urls(corpus)
    labels: List[str] = []
    for url in urls:
        labels.append(f"URL: {url[:80]}{'…' if len(url) > 80 else ''}")

    has_formatted = bool(REFERENCE_HEADING.search(corpus)) or bool(
        APA_REFERENCE_ENTRY.search(corpus)
    )
    if has_formatted:
        labels.append("Formatted reference list (APA/References heading)")

    has_traditional = any(p.search(corpus) for p in CITATION_PATTERNS)
    if has_traditional:
        labels.append("Traditional citation marker (APA/DOI/parenthetical)")

    has_book = any(p.search(corpus) for p in BOOK_REFERENCE_PATTERNS)
    if has_book:
        labels.append("Book/journal reference (author-year, edition, or publisher)")

    has_attempt = any(p.search(corpus) for p in CITATION_ATTEMPT_PATTERNS)
    if has_attempt:
        labels.append("Citation attempt (Sources:, Author year, etc.)")

    return CitationReport(
        urls=urls,
        has_formatted_reference_block=has_formatted,
        has_traditional_citation=has_traditional,
        has_book_or_journal_reference=has_book,
        has_citation_attempt=has_attempt,
        signal_labels=labels,
    )


def count_citations(
    text: str = "",
    *,
    link_urls: Optional[List[str]] = None,
    submission: Optional[DiscussionSubmission] = None,
) -> int:
    """Backward-compatible citation count (signals, not deduped academic sources)."""
    report = build_citation_report(submission=submission, text=text, link_urls=link_urls)
    if not report.has_any_citation:
        return 0
    count = len(report.urls)
    if report.has_formatted_reference_block:
        count += 1
    if report.has_traditional_citation:
        count += 1
    if report.has_book_or_journal_reference:
        count += 1
    if report.has_citation_attempt:
        count += 1
    return count
