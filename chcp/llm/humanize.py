"""
Voice-first de-slop for Canvas discussion replies.

Adapted from the prompt-only humanizer skill (MIT):
https://github.com/hannsxpeter/humanizer

Code scores and strips high-confidence tells. A second LLM pass rewrites only
when the draft is still machine-smooth. It does not invent facts, and it is
not a detector-evasion tool.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from chcp.paths import voice_profile_path
from chcp.settings import llm_config

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

# Dead-giveaway instructor-comment tells. Weights are relative; rewrite when
# the total on a short reply is at or above SLOP_REWRITE_THRESHOLD.
SLOP_PATTERNS: Tuple[Tuple[str, str, int], ...] = (
    ("sycophantic grading", r"\bgreat job identifying\b", 3),
    ("sycophantic grading", r"\byou'?ve correctly identified\b", 3),
    ("sycophantic grading", r"\byou'?ve correctly\b", 2),
    ("sycophantic grading", r"\byou'?ve clearly explained\b", 3),
    ("sycophantic grading", r"\byou'?ve covered all the\b", 3),
    ("sycophantic grading", r"\bexcellent comprehensive explanation\b", 3),
    ("sycophantic grading", r"\bperfect explanation of\b", 3),
    ("sycophantic grading", r"\bexcellent (?:explanation|breakdown|research) of\b", 2),
    ("sycophantic grading", r"\bit'?s also good to see that you'?ve\b", 3),
    ("sycophantic grading", r"\bit'?s insightful to\b", 2),
    ("sycophantic grading", r"\bi appreciate how you\b", 3),
    ("sycophantic grading", r"\bgreat insights?\b", 2),
    ("inflated significance", r"\bthis (?:foundational knowledge|understanding|"
     r"comprehensive understanding) is crucial\b", 3),
    ("inflated significance", r"\bthis will help (?:you )?in your field\b", 3),
    ("inflated significance", r"\bstands as a testament\b", 3),
    ("inflated significance", r"\bpivotal\b", 2),
    ("filler", r"\bit'?s(?:\s+\w+){0,2}\s+important to note\b", 2),
    ("filler", r"\bin conclusion\b", 2),
    ("filler", r"\bfurthermore\b", 2),
    ("filler", r"\bdelve\b", 3),
    ("filler", r"\brich tapestry\b", 3),
    ("filler", r"\bnavigate the complexities\b", 3),
    ("filler", r"\bat its core\b", 2),
    ("filler", r"\bthe key takeaway is\b", 2),
    ("filler", r"\bkeep up the great work\b", 3),
    ("copula dodge", r"\bserves as a\b", 1),
    ("generic wrap-up", r"\bwell done\b", 2),
    ("generic wrap-up", r"\bgood job\b", 1),
)

_COMPILED: Tuple[Tuple[str, re.Pattern[str], int], ...] = tuple(
    (name, re.compile(pattern, re.I), weight) for name, pattern, weight in SLOP_PATTERNS
)

_FENCE = re.compile(r"^```(?:\w+)?\s*|\s*```$", re.M)

HUMANIZE_SYSTEM = (
    "Rewrite this Canvas discussion reply body so it reads like the instructor "
    "in the voice profile typed it in a public thread.\n"
    "Core rule: variance over synonym-swapping. Uneven sentence lengths. Fix the "
    "thought, not the token.\n"
    "Faithfulness: do not add a fact, number, name, quote, cause, example, or "
    "lived experience the draft does not already contain. If a sentence is vague, "
    "shorten it. Never invent a specific to sound human.\n"
    "Strip grading-speak and AI filler (great job identifying, you've correctly "
    "explained, this is crucial for your field, delve, tapestry, it's important "
    "to note). Keep physics specifics that are already in the draft.\n"
    "Voice phrases like \"I dig that\", \"spot on\", \"on point\", \"excellent\", "
    "\"100% agree\" are allowed at most once, and only if they fit.\n"
    "No exclamation marks. No em dashes. No student name lead. No new question "
    "unless the draft already ends with one that must be kept.\n"
    "Return ONLY the rewritten body."
)

FALLBACK_VOICE = (
    "Casual intro-physics professor. Short agreement, then one real physics "
    "detail. Contractions. Not a rubric comment."
)


def load_voice_profile() -> str:
    path = voice_profile_path()
    if not path.exists():
        return FALLBACK_VOICE
    text = path.read_text(encoding="utf-8").strip()
    return text or FALLBACK_VOICE


def slop_hits(text: str) -> List[str]:
    """Pattern names that fire on this text (duplicates kept)."""
    hits: List[str] = []
    for name, pattern, _weight in _COMPILED:
        if pattern.search(text or ""):
            hits.append(name)
    return hits


def slop_score(text: str) -> int:
    """Weighted tell total. Short replies rewrite at a low integer threshold."""
    total = 0
    body = text or ""
    for _name, pattern, weight in _COMPILED:
        if pattern.search(body):
            total += weight
    return total


def is_authentic_example(response: str, min_words: Optional[int] = None) -> bool:
    """True when a stored example is usable as a voice few-shot."""
    words = (response or "").split()
    floor = min_words if min_words is not None else llm_config.MIN_EXAMPLE_RESPONSE_WORDS
    if len(words) < floor:
        return False
    return slop_score(response) < llm_config.SLOP_REWRITE_THRESHOLD


def needs_rewrite(text: str) -> bool:
    return slop_score(text) >= llm_config.SLOP_REWRITE_THRESHOLD


def _plain_content(result: object) -> str:
    if result is None:
        return ""
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        content = "\n".join(parts)
    text = str(content).strip()
    text = _FENCE.sub("", text).strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()
    return text


def rewrite_in_voice(
    llm: "BaseChatModel",
    body: str,
    *,
    voice: str,
    student_post: str = "",
) -> str:
    """Second-pass rewrite. Returns the original body if the model fails."""
    from langchain_core.prompts import ChatPromptTemplate

    draft = (body or "").strip()
    if not draft:
        return draft
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", HUMANIZE_SYSTEM),
            (
                "human",
                "Voice profile:\n{voice}\n\n"
                "Student post (context only; do not pull new claims from it):\n{post}\n\n"
                "Draft reply body:\n{body}",
            ),
        ]
    )
    try:
        result = (prompt | llm).invoke(
            {
                "voice": voice,
                "post": (student_post or "").strip()[:1200],
                "body": draft,
            }
        )
    except Exception as exc:  # noqa: BLE001 — keep the first-pass draft
        print(f"Humanize pass failed, keeping first draft: {exc}")
        return draft
    rewritten = _plain_content(result)
    if not rewritten:
        return draft
    return rewritten


def humanize_body(
    llm: "BaseChatModel",
    body: str,
    *,
    voice: str,
    student_post: str = "",
    force: bool = False,
) -> str:
    """Rewrite when the draft still looks machine-smooth; otherwise leave it."""
    draft = (body or "").strip()
    if not draft:
        return draft
    if not llm_config.HUMANIZE_PASS and not force:
        return draft
    if not force and not needs_rewrite(draft):
        return draft
    return rewrite_in_voice(llm, draft, voice=voice, student_post=student_post)


def prefer_authentic_examples(
    examples: Sequence[Tuple[str, str]],
    extras: Sequence[Tuple[str, str]] = (),
    k: int = 3,
    score_fn=None,
) -> List[Tuple[str, str]]:
    """Keep authentic few-shots; fill from extras if this week is mostly slop."""
    authentic = [(p, r) for p, r in examples if is_authentic_example(r)]
    if score_fn:
        authentic = sorted(authentic, key=lambda pr: score_fn(pr[0]), reverse=True)
    if len(authentic) >= k:
        return authentic[:k]
    seen = {(p, r) for p, r in authentic}
    fillers = [(p, r) for p, r in extras if (p, r) not in seen and is_authentic_example(r)]
    if score_fn:
        fillers = sorted(fillers, key=lambda pr: score_fn(pr[0]), reverse=True)
    return (authentic + fillers)[:k]
