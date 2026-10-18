"""One course, one week, frozen for a single browser process.

A binding is the only course material a discussion reply or grade is allowed
to see. Other courses contribute forbidden markers used to reject a prompt
that picked up their text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from chcp.core.course_utils import resolve_course
from chcp.llm.humanize import load_voice_profile

ExamplePair = Tuple[str, str]
ALL_COURSES = "ALL"


class CourseIsolationError(RuntimeError):
    """Raised when one course's material would be used for another course."""


def is_all_courses(course_selector: Optional[str]) -> bool:
    return str(course_selector or "").strip().upper() == ALL_COURSES


def url_is_course(url: str, course_id: str) -> bool:
    """True when a Canvas URL is inside this course, not a lookalike id."""
    if not url or not course_id:
        return False
    return f"/courses/{course_id}/" in url


def assert_worker_course(course_selector: str) -> None:
    """Refuse to run a course that this process was not sealed to."""
    if is_all_courses(course_selector):
        raise CourseIsolationError(
            "ALL must be split into one process per course before a browser starts"
        )
    sealed = os.environ.get("CHCP_COURSE_KEY")
    if sealed and sealed != course_selector:
        raise CourseIsolationError(
            f"This process is sealed to course {sealed} and cannot run {course_selector}"
        )


def resolve_window_slot(arg_slot: Optional[int]) -> Optional[int]:
    """Window slot from the CLI, checked against the process seal."""
    env_slot = os.environ.get("CHCP_WINDOW_SLOT")
    if env_slot is not None and arg_slot is not None and str(arg_slot) != str(env_slot):
        raise CourseIsolationError(
            f"Window slot {arg_slot} does not match sealed slot {env_slot}"
        )
    if arg_slot is not None:
        return int(arg_slot)
    if env_slot is not None and env_slot != "":
        return int(env_slot)
    return None


def chromium_launch_args(window_slot: Optional[int]) -> list[str]:
    """Cascade each course's Chromium window so the title bars stay visible."""
    if window_slot is None:
        return []
    slot = int(window_slot)
    x = 80 * slot
    y = 56 * slot
    return [f"--window-position={x},{y}", "--window-size=1100,820"]


def _course_key(course_selector: str, config: Dict[str, Any]) -> str:
    courses = config.get("courses", {})
    if course_selector in courses:
        return course_selector
    for key, course in courses.items():
        if course.get("course_id") == str(course_selector):
            return key
    raise CourseIsolationError(f"Course '{course_selector}' not found in courses.json")


def _pairs(discussion_data: Any) -> Tuple[ExamplePair, ...]:
    pairs: list[ExamplePair] = []
    for item in discussion_data or []:
        post = str(item.get("post", "")).strip()
        response = str(item.get("response", "")).strip()
        if post and response:
            pairs.append((post, response))
    return tuple(pairs)


def _marker(text: str, length: int = 120) -> str:
    compact = " ".join((text or "").split())
    return compact[:length]


@dataclass(frozen=True)
class CourseBinding:
    """Snapshot of a single course section for one week."""

    course_key: str
    course_id: str
    course_name: str
    subject: str
    voice_filename: str
    voice_profile: str
    week_id: int
    discussion_prompt: str
    topic_id: str
    week_examples: Tuple[ExamplePair, ...]
    course_examples: Tuple[ExamplePair, ...]
    foreign_markers: Tuple[str, ...]

    def assert_outbound(
        self,
        *,
        discussion_prompt: str,
        voice_profile: str,
        subject: str,
        few_shots: Sequence[ExamplePair],
        outbound_text: str,
    ) -> None:
        """Reject a reply payload that is not this course's own material."""
        if discussion_prompt != self.discussion_prompt:
            raise CourseIsolationError(
                f"Course {self.course_key} reply used a discussion prompt "
                "that is not this course's week prompt"
            )
        if voice_profile != self.voice_profile:
            raise CourseIsolationError(
                f"Course {self.course_key} reply used another course's voice profile"
            )
        if (subject or "").strip().lower() != self.subject.strip().lower():
            raise CourseIsolationError(
                f"Course {self.course_key} reply used subject {subject!r}, "
                f"expected {self.subject!r}"
            )
        allowed = set(self.course_examples)
        for pair in few_shots:
            if pair not in allowed:
                raise CourseIsolationError(
                    f"Course {self.course_key} reply included an example "
                    "that does not belong to this course"
                )
        collapsed = " ".join((outbound_text or "").split())
        for marker in self.foreign_markers:
            if marker and marker in collapsed:
                raise CourseIsolationError(
                    f"Course {self.course_key} outbound prompt contains another course's material"
                )

    def assert_grade_prompt(self, discussion_prompt: str) -> None:
        if discussion_prompt != self.discussion_prompt:
            raise CourseIsolationError(
                f"Course {self.course_key} grade used a discussion prompt "
                "that is not this course's week prompt"
            )


def bind_course(course_selector: str, week_id: int, config: Dict[str, Any]) -> CourseBinding:
    """Freeze one course's week. Other courses are recorded only as forbidden text."""
    if is_all_courses(course_selector):
        raise CourseIsolationError(
            "Cannot bind ALL. Bind one course key inside its own process."
        )
    key = _course_key(course_selector, config)
    course = resolve_course(key, config)
    week_data = (course.get("weeks") or {}).get(str(week_id))
    if not week_data:
        raise CourseIsolationError(
            f"Week {week_id} data not found in course {key}"
        )
    prompt = (week_data.get("discussion_prompt") or "").strip()
    if not prompt:
        raise CourseIsolationError(
            f"No discussion prompt for week {week_id} in course {key}"
        )
    topic_id = str(week_data.get("topic_id") or "").strip()
    voice_filename = course.get("voice") or "VOICE.md"
    voice_profile = load_voice_profile(voice_filename)
    subject = (course.get("subject") or "physics").strip()

    week_examples = _pairs(week_data.get("discussion_data"))
    course_examples: list[ExamplePair] = []
    for week in (course.get("weeks") or {}).values():
        course_examples.extend(_pairs(week.get("discussion_data")))

    own_responses = {response for _, response in course_examples}
    own_prompt_marker = _marker(prompt)
    own_voice_marker = _marker(voice_profile)
    foreign: list[str] = []
    for other_key, other in (config.get("courses") or {}).items():
        if other_key == key:
            continue
        other_voice = load_voice_profile(other.get("voice") or "VOICE.md")
        voice_marker = _marker(other_voice)
        if voice_marker and voice_marker != own_voice_marker:
            foreign.append(voice_marker)
        for other_week in (other.get("weeks") or {}).values():
            other_prompt = (other_week.get("discussion_prompt") or "").strip()
            prompt_marker = _marker(other_prompt)
            if prompt_marker and prompt_marker != own_prompt_marker:
                foreign.append(prompt_marker)
            for _, response in _pairs(other_week.get("discussion_data")):
                if response in own_responses:
                    continue
                response_marker = _marker(response, 80)
                if response_marker:
                    foreign.append(response_marker)

    # Stable, de-duplicated markers. Skip markers so short they could collide.
    unique = tuple(dict.fromkeys(m for m in foreign if len(m) >= 40))

    return CourseBinding(
        course_key=key,
        course_id=str(course.get("course_id") or ""),
        course_name=str(course.get("name") or key),
        subject=subject,
        voice_filename=voice_filename,
        voice_profile=voice_profile,
        week_id=int(week_id),
        discussion_prompt=prompt,
        topic_id=topic_id,
        week_examples=week_examples,
        course_examples=tuple(course_examples),
        foreign_markers=unique,
    )
