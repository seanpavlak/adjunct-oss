"""
LLM-based rubric grading for discussion submissions.

Uses Pydantic models (rubric_models.RubricAssessment) with LangChain structured
output so the LLM response is validated against the expected JSON schema.
"""

import json
from typing import Any, Dict, List, Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from discussion_rubric import (
    CRITERION_ORDER,
    RUBRIC_CRITERIA_DETAIL,
    RUBRIC_RATING_LEVELS,
    build_rubric_ratings_for_levels,
)
from rubric_models import RubricAssessment
from submission_evaluator import (
    _grade_from_levels,
    count_citations,
    detect_late_submission,
)
from submission_models import DiscussionSubmission, SubmissionEvaluation


def format_rubric_for_prompt() -> str:
    """Format full rubric criteria and rating bands for the LLM prompt."""
    lines = ["Discussion Rubric (2021) — grade using these exact criteria:\n"]
    for name in CRITERION_ORDER:
        detail = RUBRIC_CRITERIA_DETAIL[name]
        lines.append(f"## {name} ({detail['max_points']} points)")
        for level, description in detail["ratings"].items():
            lines.append(f"  - {level}: {description}")
        lines.append("")
    return "\n".join(lines)


def format_submission_for_prompt(submission: DiscussionSubmission) -> str:
    """Format extracted submission for the LLM."""
    parts = [
        "=== INITIAL POST ===",
        submission.initial_post or "(empty)",
        "",
        f"=== PEER REPLIES ({len(submission.peer_replies)}) ===",
    ]
    if submission.peer_replies:
        for i, reply in enumerate(submission.peer_replies, start=1):
            parts.append(f"--- Reply {i} ---")
            parts.append(reply)
    else:
        parts.append("(none detected)")
    parts.append("")
    parts.append(f"Late indicator in preview: {'yes' if submission.is_late else 'no'}")
    return "\n".join(parts)


def count_meaningful_peer_replies(
    submission: DiscussionSubmission, min_chars: int = 40
) -> int:
    """Count classmate replies that meet minimum length."""
    return len([r for r in submission.peer_replies if len(r.strip()) >= min_chars])


def apply_peer_engagement_rules(
    levels: Dict[str, str],
    submission: DiscussionSubmission,
    min_peer_replies: int = 2,
    min_peer_reply_chars: int = 40,
) -> Dict[str, str]:
    """
    Hard Engagement rules (not lenient): required peer responses.

    - 0 meaningful replies → below (0 pts on Engagement)
    - Fewer than required → needs (partial credit)
    """
    result = dict(levels)
    peer_count = count_meaningful_peer_replies(submission, min_peer_reply_chars)

    if peer_count == 0:
        result["Engagement"] = "below"
    elif peer_count < min_peer_replies:
        result["Engagement"] = "needs"

    return result


def apply_leniency(
    levels: Dict[str, str],
    submission: DiscussionSubmission,
    requirements: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Bump rubric levels toward leniency after LLM grading.

    Lenient on Comprehension, Writing, and Timeliness when effort is shown.
    Engagement is enforced separately — missing peer replies are not bumped up.
    """
    requirements = requirements or {}
    min_peer_replies = int(requirements.get("min_peer_replies", 2))
    min_peer_reply_chars = int(requirements.get("min_peer_reply_chars", 40))

    result = dict(levels)
    is_late = submission.is_late or detect_late_submission(submission.raw_text)
    peer_count = count_meaningful_peer_replies(submission, min_peer_reply_chars)
    citations = count_citations(
        submission.initial_post + "\n" + "\n".join(submission.peer_replies)
    )
    initial_len = len(submission.initial_post.strip())

    if not is_late:
        result["Timeliness"] = "meets"
    elif result.get("Timeliness") == "below":
        result["Timeliness"] = "needs"

    # Engagement leniency only when the student met the peer reply requirement
    if peer_count >= min_peer_replies:
        if result.get("Engagement") in ("below", "needs"):
            result["Engagement"] = "meets"
        elif result.get("Engagement") == "meets":
            result["Engagement"] = "exceeds"

    if citations >= 1 and result.get("Writing") in ("below", "needs"):
        result["Writing"] = "meets"
    elif citations >= 1 and result.get("Writing") == "meets":
        result["Writing"] = "exceeds"

    if initial_len >= 80 and result.get("Comprehension") in ("below", "needs"):
        result["Comprehension"] = "meets"
    if initial_len >= 120 and result.get("Comprehension") == "meets":
        result["Comprehension"] = "exceeds"

    if initial_len < 30:
        result["Comprehension"] = "below"
    else:
        for name in ("Comprehension", "Writing"):
            if result.get(name) == "below":
                result[name] = "needs"

    return apply_peer_engagement_rules(
        result, submission, min_peer_replies, min_peer_reply_chars
    )


def _print_section(title: str, body: str) -> None:
    """Print a labeled block for dry-run console output."""
    width = 72
    print()
    print("=" * width)
    print(title)
    print("=" * width)
    print(body)
    print("=" * width)


def assessment_to_levels(assessment: RubricAssessment) -> Dict[str, str]:
    """Convert validated RubricAssessment to criterion -> level map."""
    levels = assessment.levels_by_criterion()
    for name in CRITERION_ORDER:
        if name not in levels:
            levels[name] = "meets"
    return levels


class RubricGrader:
    """Grade discussion submissions against the rubric using an LLM."""

    def __init__(
        self,
        provider: Literal["openai", "anthropic", "deepseek"] = "openai",
        openai_key: str = "",
        anthropic_key: str = "",
        deepseek_key: str = "",
        lenient: bool = True,
    ):
        self.provider = provider
        self.lenient = lenient
        self.llm = self._initialize_llm(openai_key, anthropic_key, deepseek_key)
        self.structured_llm = self.llm.with_structured_output(RubricAssessment)
        self.prompt = PromptTemplate(
            template=(
                "You are an experienced, fair instructor grading a discussion assignment "
                "using the rubric below. Return a structured assessment with exactly one "
                "entry per criterion (Comprehension, Timeliness, Engagement, Writing). "
                "Each entry must use level: exceeds, meets, needs, or below.\n\n"
                "{rubric_text}\n\n"
                "Discussion prompt for this week:\n{discussion_prompt}\n\n"
                "Student submission:\n{submission_text}\n\n"
                "Grading requirements for this course:\n"
                "- Initial post addresses the prompt with substantive effort.\n"
                "- Student must respond meaningfully to at least 2 classmates.\n"
                "- Initial post should be on time (late indicator noted above).\n"
                "- Posts with factual claims should include at least one citation "
                "(URL, DOI, in-text cite, or reference).\n\n"
                "LENIENCY (important): Err on the side of leniency. When a submission "
                "reasonably meets a level, choose that level or the one above it. "
                "Do not penalize minor grammar issues, informal tone, or imperfect "
                "citation format if the student clearly tried. If borderline between "
                "two adjacent levels, choose the higher level. Reserve 'below' only "
                "for missing or clearly inadequate work. For Timeliness, use 'meets' "
                "for on-time work (do not use exceeds — it is N/A). Give 'exceeds' on "
                "Engagement when the student has two or more thoughtful peer replies. "
                "Engagement MUST be 'below' (0 points) if there are no replies to "
                "classmates, and 'needs' or lower if fewer than two meaningful "
                "peer responses."
            ),
            input_variables=["discussion_prompt", "submission_text"],
            partial_variables={"rubric_text": format_rubric_for_prompt()},
        )

    def _initialize_llm(
        self, openai_key: str, anthropic_key: str, deepseek_key: str
    ) -> BaseChatModel:
        if self.provider == "openai":
            if not openai_key:
                raise ValueError("OPENAI_API_KEY required for LLM rubric grading")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.2,
                openai_api_key=openai_key,
            )
        if self.provider == "anthropic":
            if not anthropic_key:
                raise ValueError("ANTHROPIC_API_KEY required for LLM rubric grading")
            return ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.2,
                anthropic_api_key=anthropic_key,
            )
        if self.provider == "deepseek":
            if not deepseek_key:
                raise ValueError("DEEPSEEK_API_KEY required for LLM rubric grading")
            return ChatOpenAI(
                model="deepseek-chat",
                temperature=0.2,
                openai_api_key=deepseek_key,
                base_url="https://api.deepseek.com/v1",
            )
        raise ValueError(f"Unsupported provider: {self.provider}")

    def format_full_prompt(self, discussion_prompt: str, submission_text: str) -> str:
        """Render the complete prompt string sent to the LLM."""
        schema_hint = (
            "\n\n[Structured output schema: RubricAssessment with criteria: "
            f"List[CriterionGrade] — one per {', '.join(CRITERION_ORDER)}]"
        )
        return self.prompt.format(
            discussion_prompt=discussion_prompt,
            submission_text=submission_text,
        ) + schema_hint

    def _invoke_assessment(
        self, discussion_prompt: str, submission_text: str
    ) -> RubricAssessment:
        """Call LLM and return a validated RubricAssessment."""
        chain = self.prompt | self.structured_llm
        result = chain.invoke(
            {
                "discussion_prompt": discussion_prompt,
                "submission_text": submission_text,
            }
        )
        if isinstance(result, RubricAssessment):
            return result
        return RubricAssessment.model_validate(result)

    def grade(
        self,
        submission: DiscussionSubmission,
        discussion_prompt: str,
        rubric_rating_levels: Optional[Dict[str, Dict[str, str]]] = None,
        requirements: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> SubmissionEvaluation:
        """Grade a submission and return rubric ratings for Canvas Speed Grader."""
        rubric_rating_levels = rubric_rating_levels or RUBRIC_RATING_LEVELS
        requirements = requirements or {}
        submission_text = format_submission_for_prompt(submission)

        if dry_run:
            _print_section("DRY RUN — Discussion prompt", discussion_prompt)
            _print_section("DRY RUN — Submission sent to LLM", submission_text)
            _print_section(
                "DRY RUN — Full LLM prompt",
                self.format_full_prompt(discussion_prompt, submission_text),
            )
            _print_section(
                "DRY RUN — Expected Pydantic schema",
                json.dumps(RubricAssessment.model_json_schema(), indent=2),
            )
            print("\nCalling LLM (structured output → RubricAssessment)...\n")

        assessment = self._invoke_assessment(discussion_prompt, submission_text)

        levels = assessment_to_levels(assessment)
        levels_before_leniency = dict(levels)

        if dry_run:
            _print_section(
                "DRY RUN — LLM response (validated RubricAssessment)",
                assessment.model_dump_json(indent=2),
            )
            lines = ["Levels before leniency:"]
            for name in CRITERION_ORDER:
                lines.append(f"  {name}: {levels_before_leniency.get(name, '?')}")
            _print_section("DRY RUN — Rubric levels (LLM only)", "\n".join(lines))

        if self.lenient or requirements.get("lenient", True):
            levels = apply_leniency(levels, submission, requirements)
        else:
            levels = apply_peer_engagement_rules(
                levels,
                submission,
                int(requirements.get("min_peer_replies", 2)),
                int(requirements.get("min_peer_reply_chars", 40)),
            )

        if not submission.is_late and not detect_late_submission(submission.raw_text):
            levels["Timeliness"] = "meets"

        rubric_ratings = build_rubric_ratings_for_levels(levels, rubric_rating_levels)
        grade = _grade_from_levels(levels)

        if dry_run:
            lines = ["Levels after leniency:"]
            for name in CRITERION_ORDER:
                before = levels_before_leniency.get(name, "?")
                after = levels.get(name, "?")
                changed = " (adjusted)" if before != after else ""
                lines.append(f"  {name}: {after}{changed}")
            lines.append("")
            lines.append(f"Calculated grade: {grade} pts")
            lines.append("")
            lines.append("Canvas rubric buttons that would be clicked:")
            for i, test_id in enumerate(rubric_ratings, start=1):
                lines.append(f"  {i}. {test_id}")
            _print_section("DRY RUN — Would apply in Speed Grader", "\n".join(lines))

        criterion_reasons = assessment.reasons_by_criterion()
        issues: List[str] = []
        for name in CRITERION_ORDER:
            level = levels.get(name, "meets")
            reason = criterion_reasons.get(name, "")
            if level in ("needs", "below"):
                issues.append(f"{name} ({level}): {reason or 'see rubric'}")

        peer_count = count_meaningful_peer_replies(
            submission, int(requirements.get("min_peer_reply_chars", 40))
        )
        citation_count = count_citations(
            submission.initial_post + "\n" + "\n".join(submission.peer_replies)
        )
        on_time = not submission.is_late and not detect_late_submission(submission.raw_text)
        passed = all(levels.get(n) in ("exceeds", "meets") for n in CRITERION_ORDER)

        return SubmissionEvaluation(
            passed=passed,
            issues=issues,
            peer_reply_count=peer_count,
            citation_count=citation_count,
            on_time=on_time,
            rubric_ratings=rubric_ratings,
            grade=grade,
            submission=submission,
            criterion_levels=levels,
            criterion_reasons=criterion_reasons,
            overall_notes=assessment.overall_notes,
        )
