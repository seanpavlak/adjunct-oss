"""
LLM-based response generator for Canvas discussions.

Pipeline (prompt + code):
1. Refuse if the student post is unreadable.
2. Extract physics/career anchors from the post in code.
3. Select authentic few-shots by text + concept overlap (skip AI-slop examples).
4. Ask the model for structured body in the instructor voice (+ optional question).
5. Humanize pass when the draft still has machine tells (voice rewrite, no new facts).
6. Assemble the final reply in code: Title-Case name lead, cleanup, ~20% questions.
"""

from __future__ import annotations

import difflib
import json
import random
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from chcp.canvas.parsers import is_usable_student_post
from chcp.llm.humanize import (
    humanize_body,
    load_voice_profile,
    needs_rewrite,
    prefer_authentic_examples,
)
from chcp.llm.manager import LLMManager
from chcp.llm.reply_craft import (
    analyze_student_post,
    assemble_reply,
    concept_overlap_score,
    format_anchors_for_prompt,
    format_display_name,
)
from chcp.paths import courses_config_path
from chcp.settings import llm_config


class ProfessorReplyDraft(BaseModel):
    """Structured model output — final public text is assembled in code."""

    body: str = Field(
        ...,
        description=(
            "2-3 sentence professor reply body WITHOUT the student name lead and "
            "WITHOUT a closing question. Dig into a concrete physics idea from their post."
        ),
    )
    follow_up_question: Optional[str] = Field(
        default=None,
        description=(
            "One short course-relevant physics question tied to their post, or null "
            "when follow-ups are disabled."
        ),
    )


@dataclass
class ResponseGenerator:
    week: int = field(init=True, repr=False)
    course_selector: str = field(init=True, repr=False, default="A")
    provider: Literal["openai", "anthropic", "deepseek"] = field(
        init=True, repr=False, default="openai"
    )
    openai_key: str = field(init=True, repr=False, default="")
    anthropic_key: str = field(init=True, repr=False, default="")
    deepseek_key: str = field(init=True, repr=False, default="")
    student_name: str = field(init=True, repr=False, default="")
    llm: BaseChatModel = field(init=False)
    humanize_llm: Optional[BaseChatModel] = field(init=False, default=None)
    parser: JsonOutputParser = field(init=False, default=None)
    dq_prompt: str = field(init=False, default="")
    voice_profile: str = field(init=False, default="")
    prompt: ChatPromptTemplate = field(init=False, default=None)

    def _load_courses(self) -> dict:
        courses_path = courses_config_path()
        if not courses_path.exists():
            raise FileNotFoundError(f"courses.json not found: {courses_path}")
        with open(courses_path, encoding="utf-8") as f:
            config = json.load(f)
        courses = config.get("courses", {})
        if not courses:
            raise ValueError("No courses found in courses.json")
        return courses

    def _resolve_course(self, courses: dict) -> dict:
        if self.course_selector in courses:
            return courses[self.course_selector]
        course = next(
            (c for c in courses.values() if c.get("course_id") == str(self.course_selector)),
            None,
        )
        if not course:
            raise ValueError(f"Course '{self.course_selector}' not found in courses.json")
        return course

    def _get_week_data(self) -> dict:
        course = self._resolve_course(self._load_courses())
        week_data = course.get("weeks", {}).get(str(self.week))
        if not week_data:
            raise ValueError(f"Week {self.week} data not found in course {self.course_selector}")
        return week_data

    def _get_week_prompt(self) -> str:
        prompt = self._get_week_data().get("discussion_prompt")
        if not prompt:
            raise ValueError(
                f"No discussion prompt found for week {self.week} in course {self.course_selector}"
            )
        return prompt

    def __post_init__(self):
        api_key = {
            "openai": self.openai_key,
            "anthropic": self.anthropic_key,
            "deepseek": self.deepseek_key,
        }.get(self.provider, "")
        self.llm = LLMManager.create_llm(self.provider, api_key)
        self.parser = JsonOutputParser(pydantic_object=ProfessorReplyDraft)
        self.dq_prompt = self._get_week_prompt()
        self.voice_profile = load_voice_profile()
        max_words = llm_config.MAX_RESPONSE_WORDS

        system = (
            "You are drafting Canvas discussion replies as this instructor, for an "
            "introductory college physics course (allied-health / healthcare students).\n"
            "Write in their voice first. Then strip machine smoothness. Do not invent a persona.\n"
            "Variance over synonym-swapping: uneven sentence lengths, not a thesaurus pass. "
            "A short line next to a longer one is correct. A tidy 2-3 sentence template is not.\n"
            "You never invent what the student wrote, and you never invent physics facts, "
            "stories, numbers, or quotes to sound concrete. If you lack a detail, say less.\n"
            f"Hard cap: {max_words} words in body (before any question).\n"
            "No exclamation marks. No em dashes.\n"
            "Do not start the body with the student name — code adds the name lead.\n"
            "Do not put a question in body; use follow_up_question only when asked.\n"
            "Do not recap their post, grade their post, or close with career payoff.\n"
            "Never call their post a note. No \"your note on X\", \"note that\", "
            "\"worth noting\", or \"as you noted\".\n\n"
            "Voice profile:\n{voice}"
        )

        human = (
            "Course discussion prompt:\n{dq_prompt}\n\n"
            "Anchors extracted from THIS student's post (use at least one concept deeply):\n"
            "{anchors}\n\n"
            "Examples of my real replies (match cadence and stance, not their sentences):\n"
            "{examples}\n\n"
            "Student post (source of truth — touch what they actually said):\n"
            "{content}\n\n"
            "Student first name (for context only; do NOT put it in body): {student_name}\n\n"
            "Follow-up mode: {follow_up_mode}\n"
            "- If follow-up mode is ON: also fill follow_up_question with one short, concrete "
            "physics question tied to their post and this course week.\n"
            "- If follow-up mode is OFF: set follow_up_question to null.\n\n"
            "Write body that:\n"
            "1) Reacts to a specific claim from their post (not generic praise),\n"
            "2) Adds one physics step (tighten a definition, later-week hook, or a real "
            "healthcare physics detail they already raised),\n"
            "3) Sounds like the voice profile, not like a grading comment.\n\n"
            "{format_instructions}"
        )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("human", human),
            ]
        ).partial(
            dq_prompt=self.dq_prompt,
            voice=self.voice_profile,
            format_instructions=self.parser.get_format_instructions(),
        )

    def _provider_api_key(self) -> str:
        return {
            "openai": self.openai_key,
            "anthropic": self.anthropic_key,
            "deepseek": self.deepseek_key,
        }.get(self.provider, "")

    def _get_humanize_llm(self) -> BaseChatModel:
        if self.humanize_llm is None:
            self.humanize_llm = LLMManager.create_llm(
                self.provider,
                self._provider_api_key(),
                temperature=llm_config.HUMANIZE_TEMPERATURE,
                verbose=False,
            )
        return self.humanize_llm

    def _pairs_from_discussion_data(self, discussion_data: list) -> List[Tuple[str, str]]:
        examples: List[Tuple[str, str]] = []
        for item in discussion_data:
            post = item.get("post", "").strip()
            response = item.get("response", "").strip()
            if post and response:
                examples.append((post, response))
        return examples

    def _load_discussion_examples(self) -> List[Tuple[str, str]]:
        week_data = self._get_week_data()
        examples = self._pairs_from_discussion_data(week_data.get("discussion_data", []))
        if not examples:
            raise ValueError(
                f"No discussion data found for week {self.week} in course {self.course_selector}"
            )
        return examples

    def _load_course_examples(self) -> List[Tuple[str, str]]:
        course = self._resolve_course(self._load_courses())
        examples: List[Tuple[str, str]] = []
        for week_data in course.get("weeks", {}).values():
            examples.extend(self._pairs_from_discussion_data(week_data.get("discussion_data", [])))
        return examples

    def _select_few_shots(
        self, content: str, examples: List[Tuple[str, str]], k: int = 3
    ) -> List[Tuple[str, str]]:
        def score(example_post: str) -> float:
            text_sim = difflib.SequenceMatcher(
                None, content.lower(), example_post.lower()
            ).ratio()
            concept_sim = concept_overlap_score(content, example_post)
            return 0.55 * text_sim + 0.45 * concept_sim

        return prefer_authentic_examples(
            examples,
            extras=self._load_course_examples(),
            k=k,
            score_fn=score,
        )

    def _format_examples(self, few_shots: List[Tuple[str, str]]) -> str:
        if not few_shots:
            return (
                "(no stored replies passed the voice filter — match the voice profile, "
                "not a grading comment)"
            )
        lines: List[str] = []
        for post, response in few_shots:
            lines.append(f"Post: {post[:550]}\nResponse: {response[:600]}")
        return "\n\n".join(lines)

    def reply(self, content, student_name: str = None) -> Optional[str]:
        if not self.llm:
            print("Error: No LLM Init'd")
            return None

        if not is_usable_student_post(content):
            print(
                "REFUSING to generate reply: student post was empty/unreadable. "
                "No text will be posted."
            )
            return None

        raw_name = student_name or self.student_name
        display_name = format_display_name(raw_name)
        if not display_name:
            print("REFUSING to generate reply: missing student first name.")
            return None

        anchors = analyze_student_post(content)
        examples = self._load_discussion_examples()
        few_shots = self._select_few_shots(content, examples, k=llm_config.FEW_SHOT_K)
        examples_text = self._format_examples(few_shots)

        include_follow_up = random.random() < llm_config.FOLLOW_UP_QUESTION_PROBABILITY
        follow_up_mode = "ON" if include_follow_up else "OFF"

        chain = self.prompt | self.llm | self.parser
        draft = chain.invoke(
            {
                "content": content,
                "examples": examples_text,
                "anchors": format_anchors_for_prompt(anchors),
                "student_name": display_name,
                "follow_up_mode": follow_up_mode,
            }
        )

        # JsonOutputParser may return dict or model depending on version
        if isinstance(draft, ProfessorReplyDraft):
            body = draft.body
            question = draft.follow_up_question
        else:
            body = (draft or {}).get("body", "")
            question = (draft or {}).get("follow_up_question")

        if not body or not str(body).strip():
            print("REFUSING to post: model returned empty body.")
            return None

        body = str(body)
        if needs_rewrite(body):
            body = humanize_body(
                self._get_humanize_llm(),
                body,
                voice=self.voice_profile,
                student_post=str(content),
                force=True,
            )

        return assemble_reply(
            student_name=display_name,
            body=str(body),
            follow_up_question=str(question) if question else None,
            include_follow_up=include_follow_up,
        )
