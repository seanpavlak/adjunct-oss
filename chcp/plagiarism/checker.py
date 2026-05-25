"""
Many-to-many plagiarism detection for discussion posts.

Tuned for leniency: only flag pairs with very high similarity and substantial
shared text, so topic overlap and shared prompt language are unlikely to trigger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional

# Defaults favor fewer false positives (higher bar to flag).
DEFAULT_SIMILARITY_THRESHOLD = 0.92
DEFAULT_MIN_WORDS = 80
DEFAULT_MIN_MATCHING_FRACTION = 0.40


@dataclass(frozen=True)
class DiscussionPost:
    author_id: str
    full_name: str
    content: str


@dataclass(frozen=True)
class PlagiarismMatch:
    post_a: DiscussionPost
    post_b: DiscussionPost
    similarity_ratio: float
    matching_fraction: float
    shared_word_count: int


def normalize_text(text: str) -> str:
    """Lowercase, strip URLs/punctuation, collapse whitespace."""
    lowered = text.lower()
    without_urls = re.sub(r"https?://\S+", " ", lowered)
    alphanumeric = re.sub(r"[^\w\s]", " ", without_urls)
    return re.sub(r"\s+", " ", alphanumeric).strip()


def word_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    return len(normalized.split())


def strip_prompt_from_text(text: str, prompt: Optional[str]) -> str:
    """Remove discussion prompt fragments that inflate similarity scores."""
    if not prompt or not text:
        return text

    normalized_post = normalize_text(text)
    normalized_prompt = normalize_text(prompt)
    if not normalized_prompt:
        return text

    # Drop prompt sentences that appear verbatim in the post.
    remainder = normalized_post
    for sentence in re.split(r"(?<=[.!?])\s+", normalized_prompt):
        sentence = sentence.strip()
        if len(sentence) < 40:
            continue
        if sentence in remainder:
            remainder = remainder.replace(sentence, " ")

    remainder = re.sub(r"\s+", " ", remainder).strip()
    return remainder if len(remainder) >= 50 else normalized_post


def _matching_fraction(a: str, b: str) -> tuple[float, int]:
    """Fraction of the shorter text covered by matching blocks; also shared word count."""
    if not a or not b:
        return 0.0, 0

    matcher = SequenceMatcher(None, a, b)
    blocks = matcher.get_matching_blocks()
    matched_chars = sum(block.size for block in blocks[:-1])
    shorter_len = min(len(a), len(b))
    fraction = matched_chars / shorter_len if shorter_len else 0.0

    words_a = set(a.split())
    words_b = set(b.split())
    shared_words = len(words_a & words_b)
    return fraction, shared_words


def compare_posts(
    post_a: DiscussionPost,
    post_b: DiscussionPost,
    *,
    prompt: Optional[str] = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_words: int = DEFAULT_MIN_WORDS,
    min_matching_fraction: float = DEFAULT_MIN_MATCHING_FRACTION,
) -> Optional[PlagiarismMatch]:
    """
    Return a PlagiarismMatch only when all leniency gates pass; otherwise None.
    """
    if post_a.author_id == post_b.author_id:
        return None

    if word_count(post_a.content) < min_words or word_count(post_b.content) < min_words:
        return None

    text_a = strip_prompt_from_text(post_a.content, prompt)
    text_b = strip_prompt_from_text(post_b.content, prompt)

    if not text_a or not text_b:
        return None

    ratio = SequenceMatcher(None, text_a, text_b).ratio()
    if ratio < similarity_threshold:
        return None

    matching_fraction, shared_word_count = _matching_fraction(text_a, text_b)
    if matching_fraction < min_matching_fraction:
        return None

    # Require meaningful lexical overlap, not just character-level coincidence.
    min_shared = max(40, int(min_words * 0.35))
    if shared_word_count < min_shared:
        return None

    return PlagiarismMatch(
        post_a=post_a,
        post_b=post_b,
        similarity_ratio=ratio,
        matching_fraction=matching_fraction,
        shared_word_count=shared_word_count,
    )


def find_plagiarism_pairs(
    posts: Iterable[DiscussionPost],
    *,
    prompt: Optional[str] = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_words: int = DEFAULT_MIN_WORDS,
    min_matching_fraction: float = DEFAULT_MIN_MATCHING_FRACTION,
) -> list[PlagiarismMatch]:
    """Compare every unique pair of student posts (many-to-many)."""
    unique: dict[str, DiscussionPost] = {}
    for post in posts:
        if post.author_id and post.author_id not in unique:
            unique[post.author_id] = post

    post_list = list(unique.values())
    matches: list[PlagiarismMatch] = []

    for i, post_a in enumerate(post_list):
        for post_b in post_list[i + 1 :]:
            match = compare_posts(
                post_a,
                post_b,
                prompt=prompt,
                similarity_threshold=similarity_threshold,
                min_words=min_words,
                min_matching_fraction=min_matching_fraction,
            )
            if match:
                matches.append(match)

    matches.sort(key=lambda m: m.similarity_ratio, reverse=True)
    return matches


def format_match_report(match: PlagiarismMatch) -> str:
    """Human-readable report block for terminal output."""
    pct = match.similarity_ratio * 100
    overlap_pct = match.matching_fraction * 100
    a = match.post_a
    b = match.post_b
    preview_len = 200

    def preview(text: str) -> str:
        one_line = re.sub(r"\s+", " ", text).strip()
        if len(one_line) <= preview_len:
            return one_line
        return one_line[:preview_len] + "..."

    lines = [
        "",
        "=" * 72,
        f"SUSPECTED PLAGIARISM ({pct:.1f}% similar, {overlap_pct:.1f}% text overlap)",
        f"  Student A: {a.full_name} (author {a.author_id})",
        f"  Student B: {b.full_name} (author {b.author_id})",
        f"  Shared vocabulary: ~{match.shared_word_count} words",
        "",
        f"  A preview: {preview(a.content)}",
        "",
        f"  B preview: {preview(b.content)}",
        "=" * 72,
    ]
    return "\n".join(lines)
