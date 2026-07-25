"""Pure helpers for parsing Speed Grader UI text (no browser or LLM deps)."""

import re
from typing import Iterable, Optional, Tuple

STUDENT_INDEX_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")
DAYS_LATE_VALUE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")
RUBRIC_TOTAL_POINTS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")

# Live Canvas (Jul 2026) still wraps posts in ``div.userMessage``, but the inner
# ``span.user_content`` class is no longer present on chcp.instructure.com.
# Prefer ``userMessage``, then legacy ``user_content`` selectors.
DISCUSSION_CONTENT_SELECTORS: Tuple[str, ...] = (
    "div.userMessage",
    "span.user_content.enhanced",
    "span.user_content",
)

# Sentinel strings historically returned when scraping failed — never treat as a real post.
UNREADABLE_POST_MARKERS: Tuple[str, ...] = (
    "content not found or not loaded",
    "content not found",
    "not loaded",
)

# Reject tiny scraps that are almost certainly UI chrome, not a student essay.
MIN_USABLE_POST_CHARS: int = 40


def normalize_discussion_content(texts: Iterable[str]) -> str:
    """Join scraped discussion body fragments into a single whitespace-normalized string."""
    parts = [t.strip() for t in texts if t and t.strip()]
    if not parts:
        return ""
    return " ".join(" ".join(parts).split())


def is_usable_student_post(content: Optional[str]) -> bool:
    """True only when scraped text looks like a real student post we can safely reply to."""
    if not content or not content.strip():
        return False
    normalized = " ".join(content.split()).strip()
    lower = normalized.lower()
    if any(marker in lower for marker in UNREADABLE_POST_MARKERS):
        return False
    if len(normalized) < MIN_USABLE_POST_CHARS:
        return False
    return True


def parse_student_index(text: str) -> Optional[Tuple[int, int]]:
    """Parse '3/10' or '3/10 Students' from Speed Grader progress text."""
    if not text:
        return None
    match = STUDENT_INDEX_PATTERN.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_days_late_value(text: str) -> float:
    """
    Parse the numeric value from Canvas ``days-late-input``.

    Canvas may show fractional days (e.g. ``0.98``). When the field is present
    but empty or unparseable, assume 1 day late.
    """
    stripped = (text or "").strip()
    if not stripped:
        return 1.0
    match = DAYS_LATE_VALUE_PATTERN.search(stripped)
    if not match:
        return 1.0
    return max(0.0, float(match.group(1)))


def parse_rubric_total_points(text: str) -> Optional[str]:
    """Extract the numeric rubric sum from Canvas rubric-total element text."""
    if not text:
        return None
    match = RUBRIC_TOTAL_POINTS_PATTERN.search(text.strip())
    if not match:
        return None
    value = match.group(1)
    if value.endswith(".0"):
        return str(int(float(value)))
    return value
