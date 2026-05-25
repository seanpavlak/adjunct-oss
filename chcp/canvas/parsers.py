"""Pure helpers for parsing Speed Grader UI text (no browser or LLM deps)."""

import re
from typing import Optional, Tuple

STUDENT_INDEX_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")
DAYS_LATE_VALUE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")
RUBRIC_TOTAL_POINTS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")


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
