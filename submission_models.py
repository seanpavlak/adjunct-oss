"""
Data models for Speed Grader discussion submission extraction and evaluation.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from grading.analysis import SubmissionAnalysis


@dataclass
class DiscussionSubmission:
    """Parsed discussion attempt from the Speed Grader preview iframe."""

    initial_post: str
    peer_replies: List[str] = field(default_factory=list)
    all_posts: List[str] = field(default_factory=list)
    is_late: bool = False
    """Legacy flag from preview text; prefer ``days_late`` from Speed Grader."""

    days_late: Optional[int] = None
    """Days late from Canvas ``days-late-input``; ``None`` when the field is absent (on time)."""

    raw_text: str = ""
    link_urls: List[str] = field(default_factory=list)
    """External URLs from ``<a href>`` in posts (Canvas often hides URL in visible text)."""

    @property
    def peer_reply_count(self) -> int:
        return len(self.peer_replies)


@dataclass
class SubmissionEvaluation:
    """Result of verifying a submission against course grading requirements."""

    passed: bool
    issues: List[str] = field(default_factory=list)
    peer_reply_count: int = 0
    citation_count: int = 0
    on_time: bool = True
    rubric_ratings: List[str] = field(default_factory=list)
    grade: str = "100"
    submission: Optional[DiscussionSubmission] = None
    criterion_levels: Dict[str, str] = field(default_factory=dict)
    criterion_reasons: Dict[str, str] = field(default_factory=dict)
    overall_notes: str = ""
    analysis: Optional["SubmissionAnalysis"] = None

    def summary_lines(self) -> List[str]:
        """Human-readable verification summary."""
        lines = []
        if self.analysis:
            for item in self.analysis.checklist:
                lines.append(f"  {item}")
        lines.extend([
            f"  Initial post: {len(self.submission.initial_post) if self.submission else 0} chars",
            f"  Peer replies (meaningful): {self.peer_reply_count}",
            f"  Substantive peer replies: {self.analysis.substantive_peer_count if self.analysis else '—'}",
            f"  Engagement exceeds bar: {'yes' if self.analysis and self.analysis.engagement_qualifies_for_exceeds else 'no'}",
            f"  Comprehension exceeds bar: {'yes' if self.analysis and self.analysis.initial_richness.qualifies_for_exceeds else 'no'}",
            f"  Citations found: {self.citation_count}",
        ])
        lines.extend([
            (
                f"  Days late: {self.submission.days_late}"
                if self.submission and self.submission.days_late is not None
                else f"  On time: {'yes' if self.on_time else 'no'}"
            ),
            f"  Grade: {self.grade} pts",
        ])
        if self.criterion_levels:
            lines.append("  Rubric levels (lenient LLM):")
            for name, level in self.criterion_levels.items():
                reason = self.criterion_reasons.get(name, "")
                suffix = f" — {reason[:80]}..." if len(reason) > 80 else f" — {reason}" if reason else ""
                lines.append(f"    {name}: {level}{suffix}")
        if self.overall_notes:
            lines.append(f"  Notes: {self.overall_notes[:120]}")
        lines.append(f"  Result: {'PASS' if self.passed else 'REVIEW'}")
        for issue in self.issues:
            lines.append(f"    - {issue}")
        return lines


def grading_requirements_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve grading requirements from speed grader / rubric config."""
    from discussion_rubric import GRADING_REQUIREMENTS

    requirements = dict(GRADING_REQUIREMENTS)
    overrides = config.get("grading_requirements") or {}
    requirements.update(overrides)
    return requirements
