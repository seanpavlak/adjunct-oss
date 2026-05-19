"""
Verify discussion submissions against course grading requirements.

Checks (configurable per course):
  - Initial post present and substantive
  - At least N meaningful peer replies to classmates
  - Initial post submitted on time (no late indicator in preview)
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

# Citation / reference indicators
CITATION_PATTERNS = [
    re.compile(r"https?://", re.I),
    re.compile(r"\bdoi:\s*\S+", re.I),
    re.compile(r"\bdoi\.org/", re.I),
    re.compile(r"\[[0-9]+\]"),
    re.compile(r"\([A-Z][a-z]+,?\s+\d{4}\)"),  # (Author, 2020)
    re.compile(r"\baccording to\b", re.I),
    re.compile(r"\bretrieved from\b", re.I),
    re.compile(r"\breferences?\s*:", re.I),
    re.compile(r"\bworks?\s+cited\s*:", re.I),
    re.compile(r"\b(?:apa|mla|chicago)\b", re.I),
    re.compile(r'".+"\s*\(\d{4}\)'),  # "Title" (2020)
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


def parse_discussion_submission(raw_text: str, is_late: bool = False) -> DiscussionSubmission:
    """Build a DiscussionSubmission from raw iframe text."""
    posts = split_content_into_posts(raw_text)
    initial = posts[0] if posts else ""
    replies = posts[1:] if len(posts) > 1 else []

    # Re-classify: lines that look like peer replies but landed in initial
    if not replies and initial:
        split = _split_on_peer_greetings(initial)
        if len(split) > 1:
            initial = split[0]
            replies = split[1:]

    return DiscussionSubmission(
        initial_post=initial.strip(),
        peer_replies=[r.strip() for r in replies if r.strip()],
        all_posts=posts,
        is_late=is_late,
        raw_text=raw_text,
    )


def count_citations(text: str) -> int:
    """Count distinct citation indicators in text."""
    if not text:
        return 0
    found = 0
    for pattern in CITATION_PATTERNS:
        if pattern.search(text):
            found += 1
    return found


def detect_late_submission(raw_text: str) -> bool:
    """Detect late submission markers in preview text."""
    return any(p.search(raw_text) for p in LATE_PATTERNS)


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
