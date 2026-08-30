"""Deterministic helpers that shape professor discussion replies (no LLM calls)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# Physics / course lexicon used to surface anchors from a student post.
PHYSICS_CONCEPTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("metric system / units", ("metric", "imperial", "si unit", "kilogram", "celsius", "conversion")),
    ("speed vs velocity", ("velocity", "speed", "instantaneous", "mph", "kph")),
    ("acceleration / gravity", ("acceleration", "gravity", "free fall", "9.8", "air resistance")),
    ("Newton's laws / force", ("newton", "force", "inertia", "action-reaction", "mass")),
    ("energy", ("kinetic", "potential", "energy", "work")),
    ("waves / ultrasound / Doppler", ("wave", "ultrasound", "sonograph", "doppler", "frequency", "piezo")),
    ("buoyancy / density", ("buoyancy", "density", "archimedes", "float", "sink")),
    ("electricity / circuits", ("battery", "circuit", "current", "voltage", "charge", "electron")),
    ("optics / color / light", ("light", "color", "photon", "lens", "reflection", "refraction")),
    ("atoms / periodic table", ("atom", "electron", "valence", "periodic", "element", "bond")),
    ("motion / kinematics", ("motion", "displacement", "distance", "kinematics")),
    ("scientific method / models", ("scientific method", "hypothesis", "model", "predict")),
)

CAREER_HOOKS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("sonography / ultrasound", ("sonograph", "ultrasound", "doppler", "echo", "cardiac", "vascular")),
    ("nursing / patient care", ("nursing", "patient", "medication", "dosage", "clinical")),
    ("medicine / healthcare", ("healthcare", "medical", "medicine", "hospital", "provider")),
)

AI_FILLER_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bi appreciate how you\b",
        r"\bgreat insights?\b",
        r"\bit'?s(?:\s+\w+){0,2}\s+important to note(?: that)?\b",
        r"\bworth noting(?: that)?\b",
        r"\bplease note(?: that)?\b",
        r"\bnote that\b",
        r"\bas you noted,?\b",
        r"\bon a side note,?\b",
        r"\bdelve(?: into)?\b",
        r"\bfurthermore,?\b",
        r"\bin conclusion,?\b",
        r"\bkeep up the great work\b",
        r"\bwell done\b",
        r"\bgood job\b",
        r"\bsolid takeaway\b",
        r"\bthis will help (you )?in your field\b",
        r"\bgreat job identifying\b",
        r"\byou'?ve correctly identified\b",
        r"\byou'?ve covered all the key concepts\b",
        r"\bit'?s also good to see that you'?ve\b",
        r"\bit'?s insightful to\b",
        r"\bthis (?:foundational knowledge|understanding) is crucial\b",
        r"\brich tapestry\b",
        r"\bnavigate the complexities\b",
        r"\bat its core,?\b",
        r"\bthe key takeaway is\b",
        r"\bstands as a testament\b",
    )
)

QUESTION_SPLIT = re.compile(r"(?<=[.!?])\s+")
PADDED_NAME_LEAD = re.compile(
    r"^(?:Exactly|Yeah|Yep|Yes|Totally agree|I agree|Great point|Nice point)"
    r"\s*[,:.—–-]\s*",
    re.I,
)
I_PRONOUN = re.compile(r"^I(?:['’](?:m|ll|d|ve|re))?$", re.I)
LEAD_TOKEN = re.compile(r"^(\S+)(\s*)(.*)$", re.S)

# After "Name, …" only these stay capped. Everything else is a continuation.
PROPER_NOUNS = frozenset(
    {
        "doppler", "newton", "newton's", "archimedes", "archimedes'",
        "mendeleev", "einstein", "celsius", "kelvin", "fahrenheit",
        "nasa", "hubble", "joule", "watt", "pascal", "hertz", "ohm",
        "tesla", "maxwell", "planck", "galileo", "kepler", "ampere",
        "volta", "coulomb", "faraday", "bernoulli", "hooke",
    }
)


@dataclass(frozen=True)
class PostAnchors:
    """Salient bits extracted from a student post for grounded prompting."""

    concepts: Tuple[str, ...] = ()
    career_hooks: Tuple[str, ...] = ()
    key_sentences: Tuple[str, ...] = ()
    word_count: int = 0

    @property
    def has_signal(self) -> bool:
        return bool(self.concepts or self.career_hooks or self.key_sentences)


def format_display_name(name: Optional[str]) -> str:
    """Normalize a first name to Title Case for public replies."""
    if not name or not name.strip():
        return ""
    cleaned = re.sub(r"\s+", " ", name.strip())
    parts: List[str] = []
    for chunk in cleaned.split(" "):
        sub: List[str] = []
        for piece in re.split(r"([-'])", chunk):
            if piece in {"-", "'"}:
                sub.append(piece)
            elif piece:
                sub.append(piece[:1].upper() + piece[1:].lower())
        parts.append("".join(sub))
    return " ".join(parts)


def _match_labels(text_lower: str, catalog: Sequence[Tuple[str, Tuple[str, ...]]]) -> List[str]:
    hits: List[str] = []
    for label, keywords in catalog:
        if any(k in text_lower for k in keywords):
            hits.append(label)
    return hits


def _key_sentences(content: str, limit: int = 3) -> List[str]:
    raw = re.split(r"(?<=[.!?])\s+", content.strip())
    sentences = [s.strip() for s in raw if len(s.strip()) >= 40]
    if not sentences:
        clauses = [c.strip() for c in re.split(r"[,;]", content) if len(c.strip()) >= 30]
        return sorted(clauses, key=len, reverse=True)[:limit]
    ranked = sorted(sentences, key=len, reverse=True)
    return ranked[:limit]


def analyze_student_post(content: str) -> PostAnchors:
    """Pull concept/career anchors and representative sentences from a post."""
    text = (content or "").strip()
    if not text:
        return PostAnchors()
    lower = text.lower()
    return PostAnchors(
        concepts=tuple(_match_labels(lower, PHYSICS_CONCEPTS)),
        career_hooks=tuple(_match_labels(lower, CAREER_HOOKS)),
        key_sentences=tuple(_key_sentences(text)),
        word_count=len(text.split()),
    )


def format_anchors_for_prompt(anchors: PostAnchors) -> str:
    """Human-readable briefing block injected into the LLM prompt."""
    lines: List[str] = []
    if anchors.concepts:
        lines.append("Physics concepts they raised: " + "; ".join(anchors.concepts))
    else:
        lines.append("Physics concepts they raised: (none matched — dig into their concrete claims)")
    if anchors.career_hooks:
        lines.append("Career / applied hooks: " + "; ".join(anchors.career_hooks))
    if anchors.key_sentences:
        lines.append("Lines to touch (paraphrase, do not quote dump):")
        for s in anchors.key_sentences:
            lines.append(f"- {s[:220]}")
    lines.append(f"Approx. post length: {anchors.word_count} words")
    return "\n".join(lines)


def concept_overlap_score(content: str, example_post: str) -> float:
    """Score example relevance by shared physics/career labels (0..1)."""
    a = set(analyze_student_post(content).concepts) | set(analyze_student_post(content).career_hooks)
    b = set(analyze_student_post(example_post).concepts) | set(
        analyze_student_post(example_post).career_hooks
    )
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def strip_ai_filler(text: str) -> str:
    cleaned = text
    for pattern in AI_FILLER_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:?])", r"\1", cleaned)
    return cleaned.strip()


def strip_trailing_questions(text: str) -> str:
    """Remove trailing question sentences when follow-ups are disabled."""
    parts = [p.strip() for p in QUESTION_SPLIT.split(text.strip()) if p.strip()]
    kept = [p for p in parts if not p.endswith("?")]
    if not kept:
        return text.strip().rstrip("?").strip()
    out = " ".join(kept)
    if out and out[-1] not in ".!\"":
        out += "."
    return out


def ensure_question(text: str) -> str:
    q = (text or "").strip()
    if not q:
        return ""
    q = q.rstrip(" .!")
    if not q.endswith("?"):
        q += "?"
    # Capitalize first letter
    if q[0].islower():
        q = q[0].upper() + q[1:]
    return q


def strip_leading_name(text: str, name: str) -> str:
    """Remove an existing name lead so we can re-attach a normalized one."""
    body = (text or "").strip()
    if not body:
        return ""
    body = PADDED_NAME_LEAD.sub("", body)
    if name:
        body = re.sub(
            rf"^{re.escape(name)}\s*[,:.—–\-\"'“”]*\s*",
            "",
            body,
            count=1,
            flags=re.IGNORECASE,
        )
    return body.lstrip(" ,.-—–\"'“”")


def _token_core(token: str) -> str:
    return re.sub(r"^[^\w'’]+|[^\w'’]+$", "", token)


def _is_i_pronoun(core: str) -> bool:
    return bool(I_PRONOUN.match(core))


def _keep_leading_cap(core: str) -> bool:
    """True only for I, known names, and acronyms — not Your/This/When/etc."""
    if not core:
        return False
    if _is_i_pronoun(core):
        return True
    letters = re.sub(r"[^A-Za-z]", "", core)
    if letters.isupper() and len(letters) >= 2:
        return True
    folded = core.casefold()
    if folded in PROPER_NOUNS:
        return True
    if folded.endswith("'s") and folded[:-2] in PROPER_NOUNS:
        return True
    if folded.endswith("’s") and folded[:-2] in PROPER_NOUNS:
        return True
    return False


def fit_body_after_name(body: str) -> str:
    """Lowercase a continuation after 'Name, ' unless the lead word must stay capped."""
    text = (body or "").lstrip(" ,")
    if not text:
        return text
    match = LEAD_TOKEN.match(text)
    if not match:
        return text
    token, space, rest = match.group(1), match.group(2), match.group(3)
    core = _token_core(token)
    if not core:
        return text
    if _is_i_pronoun(core):
        new_core = "I" + core[1:]
        return token.replace(core, new_core, 1) + space + rest
    if _keep_leading_cap(core):
        letters = re.sub(r"[^A-Za-z]", "", core)
        if letters.isupper() and len(letters) >= 2:
            new_core = core
        else:
            new_core = core[0].upper() + core[1:]
        return token.replace(core, new_core, 1) + space + rest
    new_core = core[0].lower() + core[1:]
    return token.replace(core, new_core, 1) + space + rest


def assemble_reply(
    *,
    student_name: str,
    body: str,
    follow_up_question: Optional[str] = None,
    include_follow_up: bool = False,
) -> str:
    """
    Assemble the final public reply in code.

    Guarantees: Title-Case name lead, no padded Exactly/Yeah opener, optional question.
    """
    name = format_display_name(student_name)
    body = strip_ai_filler(body or "")
    body = strip_leading_name(body, name or student_name or "")
    body = body.replace("!", ".")
    # Em/en dashes → comma + space (avoid "word,word")
    body = re.sub(r"\s*[—–]\s*", ", ", body)
    body = re.sub(r"\s{2,}", " ", body).strip()
    # Clean " ," artifacts if dash sat next to existing punctuation
    body = re.sub(r",\s*,+", ",", body)
    body = body.lstrip(" ,")

    if not include_follow_up:
        body = strip_trailing_questions(body)
        question = ""
    else:
        # Keep body free of a second trailing question; attach the structured one
        body = strip_trailing_questions(body)
        question = ensure_question(follow_up_question or "")

    body = fit_body_after_name(body)
    if body and body[-1] not in ".!\"":
        body += "."

    if not name:
        core = body
    else:
        core = f"{name}, {body}" if body else f"{name}."

    if include_follow_up and question:
        return f"{core} {question}".strip()
    return core.strip()
