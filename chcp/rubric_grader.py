"""
LLM-based rubric grading for discussion submissions.

Pipeline: analyze submission → rich grading brief → LLM assessment →
post-process (leniency + enforcement with analysis) → Canvas ratings.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from chcp.discussion_rubric import (
    CRITERION_ORDER,
    DISCUSSION_RUBRIC_2021,
    RUBRIC_RATING_LEVELS,
    build_rubric_ratings_for_levels,
)
from chcp.grading.analysis import SubmissionAnalysis, analyze_submission
from chcp.grading.brief import format_grading_brief
from chcp.grading.parse import detect_late_submission
from chcp.grading.scoring import grade_points_from_levels
from chcp.rubric import (
    RubricGradingConfig,
    RubricPostProcessor,
    build_grading_instructions,
    build_rubric_grading_config,
    format_rubric_for_prompt,
)
from chcp.rubric.types import RubricLevel
from chcp.rubric_models import RubricAssessment, assessment_to_levels
from chcp.submission_models import DiscussionSubmission, SubmissionEvaluation

def format_submission_for_prompt(
    submission: DiscussionSubmission,
    discussion_prompt: str = "",
) -> str:
    """Backward-compatible wrapper building the full grading brief."""
    analysis = analyze_submission(submission)
    return format_grading_brief(analysis, discussion_prompt)


def _print_section(title: str, body: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(title)
    print("=" * width)
    print(body)
    print("=" * width)


class RubricGrader:
    """Grade discussion submissions against the rubric using an LLM."""

    def __init__(
        self,
        provider: Literal["openai", "anthropic", "deepseek"] = "openai",
        openai_key: str = "",
        anthropic_key: str = "",
        deepseek_key: str = "",
        lenient: bool = True,
        rubric_criteria: Optional[List[Dict[str, Any]]] = None,
        grading_defaults: Optional[Dict[str, Any]] = None,
        rubric_name: Optional[str] = None,
        rubric_grading_config: Optional[Dict[str, Any]] = None,
    ):
        self.provider = provider
        self.lenient = lenient
        self.rubric_name = rubric_name or DISCUSSION_RUBRIC_2021["name"]

        if rubric_grading_config:
            self._config = build_rubric_grading_config(
                rubric_grading_config.get("criteria", []),
                rubric_grading_config.get("grading_requirements"),
                rubric_grading_config.get("grading_defaults"),
            )
        else:
            self._config = build_rubric_grading_config(
                rubric_criteria or DISCUSSION_RUBRIC_2021["criteria"],
                grading_defaults=grading_defaults,
            )

        self._processor = RubricPostProcessor(self._config)
        self.llm = self._initialize_llm(openai_key, anthropic_key, deepseek_key)
        self.structured_llm = self.llm.with_structured_output(RubricAssessment)

        criteria_names = ", ".join(self._config.criterion_order)
        self.prompt = PromptTemplate(
            template=(
                "You are an experienced instructor grading a weekly discussion assignment. "
                "Grade like a fair human: use the rubric, the discussion prompt, and the "
                "automated checklist in the student packet. Return a structured assessment "
                f"with exactly one entry per criterion ({criteria_names}). "
                "Each entry: level (exceeds, meets, needs, below), reason citing specific "
                "evidence from the initial post and/or peer replies, and borderline (true "
                "only when torn between adjacent levels 1↔2 or 3↔4).\n\n"
                "{rubric_text}\n\n"
                "{submission_text}\n\n"
                "Course-specific grading guidance:\n"
                "{grading_instructions}\n"
            ),
            input_variables=["submission_text"],
            partial_variables={
                "rubric_text": format_rubric_for_prompt(
                    self._config.criteria,
                    rubric_name=self.rubric_name,
                ),
                "grading_instructions": build_grading_instructions(self._config),
            },
        )

    @property
    def config(self) -> RubricGradingConfig:
        return self._config

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

    def format_full_prompt(
        self, discussion_prompt: str, submission: DiscussionSubmission
    ) -> str:
        analysis = analyze_submission(
            submission, self._config.grading_requirements.model_dump()
        )
        brief = format_grading_brief(analysis, discussion_prompt)
        schema_hint = (
            "\n\n[Structured output: RubricAssessment with criteria: "
            f"List[CriterionGrade] — one per {', '.join(self._config.criterion_order)}]"
        )
        return self.prompt.format(submission_text=brief) + schema_hint

    def _invoke_assessment(self, submission_text: str) -> RubricAssessment:
        chain = self.prompt | self.structured_llm
        result = chain.invoke({"submission_text": submission_text})
        if isinstance(result, RubricAssessment):
            return result
        return RubricAssessment.model_validate(result)

    def _resolve_config(
        self, requirements: Optional[Dict[str, Any]]
    ) -> RubricGradingConfig:
        if not requirements:
            return self._config
        merged_req = {
            **self._config.grading_requirements.model_dump(),
            **requirements,
        }
        return build_rubric_grading_config(
            [
                {
                    "name": c.name,
                    "max_points": c.max_points,
                    "rating": c.rating,
                    "description": c.description,
                    "grading_policy": c.grading_policy.model_dump(exclude_none=True),
                }
                for c in self._config.criteria
            ],
            merged_req,
            self._config.grading_defaults.model_dump(exclude_none=True),
        )

    def grade(
        self,
        submission: DiscussionSubmission,
        discussion_prompt: str,
        rubric_rating_levels: Optional[Dict[str, Dict[str, str]]] = None,
        requirements: Optional[Dict[str, Any]] = None,
        rubric_config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> SubmissionEvaluation:
        """Grade a submission and return rubric ratings for Canvas Speed Grader."""
        rubric_rating_levels = rubric_rating_levels or RUBRIC_RATING_LEVELS
        requirements = requirements or {}

        if rubric_config:
            config = build_rubric_grading_config(
                rubric_config.get("criteria", []),
                rubric_config.get("grading_requirements"),
                rubric_config.get("grading_defaults"),
            )
        else:
            config = self._resolve_config(requirements)

        req_dict = config.grading_requirements.model_dump()
        analysis = analyze_submission(submission, req_dict)
        submission_text = format_grading_brief(analysis, discussion_prompt)
        processor = RubricPostProcessor(config)
        criterion_order = config.criterion_order

        if dry_run:
            _print_section("DRY RUN — Discussion prompt", discussion_prompt)
            _print_section("DRY RUN — Pre-grade analysis", "\n".join(analysis.checklist))
            _print_section("DRY RUN — Submission packet sent to LLM", submission_text)
            _print_section(
                "DRY RUN — Full LLM prompt",
                self.format_full_prompt(discussion_prompt, submission),
            )
            _print_section(
                "DRY RUN — Expected Pydantic schema",
                json.dumps(RubricAssessment.model_json_schema(), indent=2),
            )
            print("\nCalling LLM (structured output → RubricAssessment)...\n")

        assessment = self._invoke_assessment(submission_text)
        levels = assessment_to_levels(assessment, criterion_order)
        levels_before_policy = dict(levels)
        borderline = assessment.borderline_by_criterion()

        if dry_run:
            _print_section(
                "DRY RUN — LLM response (validated RubricAssessment)",
                assessment.model_dump_json(indent=2),
            )
            lines = ["Levels before policy post-processing:"]
            for name in criterion_order:
                bl = " [borderline]" if borderline.get(name) else ""
                lines.append(f"  {name}: {levels_before_policy.get(name, '?')}{bl}")
            _print_section("DRY RUN — Rubric levels (LLM only)", "\n".join(lines))

        use_lenient = self.lenient and bool(
            requirements.get("lenient", config.lenient_enabled)
        )
        levels = processor.apply(
            levels,
            submission,
            lenient=use_lenient,
            borderline=borderline,
            analysis=analysis,
        )

        rubric_ratings = build_rubric_ratings_for_levels(levels, rubric_rating_levels)
        grade = grade_points_from_levels(levels)

        if dry_run:
            lines = ["Levels after policy post-processing:"]
            for name in criterion_order:
                before = levels_before_policy.get(name, "?")
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
        for name in criterion_order:
            level = levels.get(name, "meets")
            reason = criterion_reasons.get(name, "")
            if level in ("needs", "below"):
                issues.append(f"{name} ({level}): {reason or 'see rubric'}")

        passed = all(levels.get(n) in ("exceeds", "meets") for n in criterion_order)

        return SubmissionEvaluation(
            passed=passed,
            issues=issues,
            peer_reply_count=analysis.meaningful_peer_count,
            citation_count=analysis.citation_count,
            on_time=analysis.on_time,
            rubric_ratings=rubric_ratings,
            grade=grade,
            submission=submission,
            criterion_levels=dict(levels),
            criterion_reasons=criterion_reasons,
            overall_notes=assessment.overall_notes,
            analysis=analysis,
        )
