"""Build and soft-drop course config from Canvas course payloads.

Mapping is pure: callers fetch Canvas JSON and pass it in. Nothing here
opens a browser or writes a file.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Optional

from chcp.discussion_rubric import build_discussion_rubric_config

_SECTION_CODE = re.compile(r"-C(\d{2})(\d{2})(\d{2})(?!\d)")
_SUBJECT_CODE = re.compile(r"(?<![A-Za-z])(PHYS|CRT)(?![A-Za-z])")
_COURSE_URL = re.compile(r"/courses/(\d+)")
_HTML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "blockquote"}

_SUBJECTS = {
    "PHYS": {"subject": "physics", "voice": None},
    "CRT": {"subject": "critical_thinking", "voice": "VOICE_CRT.md"},
}


class TermSetupError(ValueError):
    """The course payload cannot be turned into a config entry."""


@dataclass(frozen=True)
class DiscussionChoice:
    title: str
    topic_id: str
    assignment_id: Optional[str]


class AmbiguousModuleError(TermSetupError):
    """A module has several discussions and not exactly one graded topic."""

    def __init__(self, module_title: str, choices: list[DiscussionChoice]):
        self.module_title = module_title
        self.choices = list(choices)
        lines = [
            f"Module '{module_title}' has more than one discussion " "and no single graded topic:"
        ]
        for choice in self.choices:
            assignment = choice.assignment_id or "-"
            lines.append(f"  {choice.title} topic_id={choice.topic_id} assignment_id={assignment}")
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class CourseIdentity:
    subject: str
    voice: Optional[str]
    start_date: str


@dataclass(frozen=True)
class MappedWeek:
    week: int
    module_title: str
    topic_id: str
    assignment_id: Optional[str]
    prompt: str
    html_stripped: bool
    ignored_titles: tuple[str, ...] = ()


@dataclass
class ImportPlan:
    key: str
    course: dict[str, Any]
    announcements: Optional[list]
    notes: list[str] = field(default_factory=list)
    donor_key: Optional[str] = None
    weeks: list[MappedWeek] = field(default_factory=list)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS and tag != "br":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalize_course_id(value: str) -> str:
    """Accept a numeric id or a Canvas course URL."""
    text = (value or "").strip()
    url_match = _COURSE_URL.search(text)
    if url_match:
        return url_match.group(1)
    if text.isdigit():
        return text
    raise TermSetupError(f"Course id must be numeric, got: {value}")


def parse_course_identity(name: str) -> CourseIdentity:
    """Subject, voice, and start date from a CHCP course name."""
    codes = list(dict.fromkeys(_SUBJECT_CODE.findall(name or "")))
    if len(codes) != 1:
        found = ", ".join(codes) if codes else "none"
        raise TermSetupError(
            f"Cannot tell the course type from '{name}'. " f"Expected PHYS or CRT, found {found}."
        )
    profile = _SUBJECTS[codes[0]]
    match = _SECTION_CODE.search(name or "")
    if not match:
        raise TermSetupError(f"Course name '{name}' has no section code like C260908.")
    year = 2000 + int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    try:
        start = datetime(year, month, day)
    except ValueError as exc:
        code = f"C{match.group(1)}{match.group(2)}{match.group(3)}"
        raise TermSetupError(f"Section code {code} is not a real date.") from exc
    return CourseIdentity(
        subject=profile["subject"],
        voice=profile["voice"],
        start_date=start.strftime("%Y-%m-%d"),
    )


def course_subject(course: dict[str, Any]) -> str:
    """Subject used to find a donor course. Name is the fallback."""
    explicit = str(course.get("subject") or "").strip().lower().replace(" ", "_")
    if explicit == "crt":
        return "critical_thinking"
    if explicit:
        return explicit
    try:
        return parse_course_identity(str(course.get("name") or "")).subject
    except TermSetupError:
        return "physics"


def message_to_prompt(message: str) -> tuple[str, bool]:
    """Plain discussion text, and whether HTML tags were removed."""
    text = message or ""
    if not _HTML_TAG.search(text):
        return text.strip(), False
    parser = _HTMLText()
    parser.feed(text)
    parser.close()
    plain = "".join(parser.parts)
    plain = re.sub(r"[ \t]+\n", "\n", plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip(), True


def next_course_key(courses: dict[str, Any]) -> str:
    """First unused letter from A through Z."""
    for index in range(26):
        key = chr(ord("A") + index)
        if key not in courses:
            return key
    raise TermSetupError("No unused course keys from A to Z remain.")


def find_course_key_by_id(courses: dict[str, Any], course_id: str) -> Optional[str]:
    wanted = str(course_id)
    for key, course in courses.items():
        if str(course.get("course_id")) == wanted:
            return key
    return None


def find_donor(courses: dict[str, Any], subject: str) -> Optional[tuple[str, dict[str, Any]]]:
    """Latest same-subject course, including ones already soft-dropped.

    The same start date keeps the later course in file order.
    """
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for index, (key, course) in enumerate(courses.items()):
        if course_subject(course) == subject:
            matches.append((index, key, course))
    if not matches:
        return None
    _index, key, course = max(
        matches,
        key=lambda item: (str(item[2].get("course_start_date") or ""), item[0]),
    )
    return key, course


def map_weeks(modules: list[dict[str, Any]], discussions: list[dict[str, Any]]) -> list[MappedWeek]:
    """Week 0 is Getting Started. Later discussion modules are weeks 1, 2, 3.

    Module position wins over due dates. A module with no discussion is skipped.
    """
    by_id = {_topic_id(topic): topic for topic in discussions if _topic_id(topic)}
    ordered = sorted(enumerate(modules or []), key=lambda pair: _module_sort_key(*pair))
    mapped: list[MappedWeek] = []
    used: dict[int, str] = {}
    next_week = 1

    for _index, module in ordered:
        items = _discussion_items(module)
        if not items:
            continue
        title = _module_title(module)
        chosen, ignored = _choose_discussion(title, items, by_id)
        topic_id = str(chosen.get("content_id"))
        topic = by_id.get(topic_id)
        if topic is None:
            raise TermSetupError(
                f"Module '{title}' points at discussion {topic_id}, "
                "which was not in the Canvas topics response."
            )
        if _is_getting_started(title):
            week = 0
        else:
            week = next_week
            next_week += 1
        if week in used:
            raise TermSetupError(
                f"Week {week} is already used by '{used[week]}'. " f"'{title}' would use it too."
            )
        used[week] = title
        prompt, stripped = message_to_prompt(str(topic.get("message") or ""))
        if not prompt:
            raise TermSetupError(f"Discussion {topic_id} in module '{title}' has no prompt text.")
        mapped.append(
            MappedWeek(
                week=week,
                module_title=title,
                topic_id=topic_id,
                assignment_id=_assignment_id(topic),
                prompt=prompt,
                html_stripped=stripped,
                ignored_titles=tuple(ignored),
            )
        )
    if not mapped:
        raise TermSetupError("No discussion modules were found for this course.")
    return sorted(mapped, key=lambda week: week.week)


def prepare_import(
    courses_config: dict[str, Any],
    announcements_config: dict[str, Any],
    canvas_course: dict[str, Any],
    modules: list[dict[str, Any]],
    discussions: list[dict[str, Any]],
) -> ImportPlan:
    """Build a new course entry. Does not mutate the configs."""
    courses = courses_config.get("courses") or {}
    name = str(canvas_course.get("name") or "").strip()
    if not name:
        raise TermSetupError("Canvas course has no name.")
    course_id = str(canvas_course.get("id") or "").strip()
    if not course_id.isdigit():
        raw_id = course_id or canvas_course.get("id")
        raise TermSetupError(f"Canvas course id is not numeric: {raw_id}")
    existing = find_course_key_by_id(courses, course_id)
    if existing:
        raise TermSetupError(f"Canvas course {course_id} is already configured as {existing}.")

    identity = parse_course_identity(name)
    donor_pair = find_donor(courses, identity.subject)
    donor_key = donor_pair[0] if donor_pair else None
    donor = donor_pair[1] if donor_pair else None
    _reject_voice_mismatch(identity, donor_key, donor)

    weeks = map_weeks(modules, discussions)
    notes: list[str] = []
    start_note = _start_date_note(identity.start_date, canvas_course.get("start_at"))
    if start_note:
        notes.append(start_note)
    numbered = [week.week for week in weeks if week.week != 0]
    if numbered != list(range(1, 9)):
        shown = ", ".join(str(week) for week in numbered) if numbered else "none"
        notes.append(f"Numbered weeks are {shown}. An 8-week term usually has weeks 1-8.")

    course: dict[str, Any] = {
        "name": name,
        "course_id": course_id,
        "course_start_date": identity.start_date,
        "subject": identity.subject,
    }
    if identity.voice:
        course["voice"] = identity.voice
    donor_weeks = (donor or {}).get("weeks") or {}
    week_entries: dict[str, Any] = {}
    for week in weeks:
        entry: dict[str, Any] = {"topic_id": week.topic_id}
        if week.assignment_id:
            entry["speed_grader"] = {"assignment_id": week.assignment_id}
        else:
            notes.append(
                f"Week {week.week} has no assignment id, so SpeedGrader was not configured."
            )
        entry["discussion_prompt"] = week.prompt
        donor_week = donor_weeks.get(str(week.week)) or {}
        examples = donor_week.get("discussion_data") or []
        entry["discussion_data"] = copy.deepcopy(examples)
        week_entries[str(week.week)] = entry
        if week.html_stripped:
            notes.append(f"Week {week.week} prompt contained HTML and was stored as plain text.")
        if week.ignored_titles:
            extra = ", ".join(week.ignored_titles)
            notes.append(
                f"Week {week.week} module '{week.module_title}' also had other "
                f"discussions ({extra}); used the graded topic."
            )
    course["weeks"] = week_entries

    announcements = _copy_announcements(announcements_config, donor_key)
    if donor and donor.get("discussion_rubric"):
        course["discussion_rubric"] = copy.deepcopy(donor["discussion_rubric"])
    else:
        course["discussion_rubric"] = copy.deepcopy(build_discussion_rubric_config())
    if donor is None:
        notes.append(
            f"No earlier {identity.subject} course to copy examples, rubric, or "
            "announcements from. Using the built-in discussion rubric."
        )
    elif announcements is None:
        notes.append(
            f"No announcements found for course {donor_key}. Announcements were not copied."
        )

    return ImportPlan(
        key=next_course_key(courses),
        course=course,
        announcements=announcements,
        notes=notes,
        donor_key=donor_key,
        weeks=weeks,
    )


def apply_import(
    courses_config: dict[str, Any],
    announcements_config: dict[str, Any],
    plan: ImportPlan,
) -> None:
    """Insert a prepared course. Caller validates and writes."""
    courses = courses_config.setdefault("courses", {})
    if plan.key in courses:
        raise TermSetupError(f"Course key {plan.key} already exists.")
    existing = find_course_key_by_id(courses, plan.course["course_id"])
    if existing:
        raise TermSetupError(
            f"Canvas course {plan.course['course_id']} is already configured as {existing}."
        )
    courses[plan.key] = plan.course
    if plan.announcements is not None:
        announcements_config.setdefault("courses", {})[plan.key] = {
            "announcements": plan.announcements
        }


def mark_courses_inactive(courses_config: dict[str, Any], keys: list[str]) -> list[str]:
    """Set active false. Returns keys that changed. Does not write the file."""
    courses = courses_config.get("courses") or {}
    changed: list[str] = []
    for key in keys:
        if key not in courses:
            raise TermSetupError(f"Course '{key}' not found in courses.json")
        if courses[key].get("active") is False:
            continue
        courses[key]["active"] = False
        changed.append(key)
    return changed


def format_import_preview(plan: ImportPlan) -> str:
    course = plan.course
    lines = [
        f"Key {plan.key}",
        f"Name: {course['name']}",
        f"Id: {course['course_id']}",
        f"Subject: {course['subject']}",
        f"Voice: {course.get('voice') or 'VOICE.md'}",
        f"Start: {course['course_start_date']}",
        f"Examples from: {plan.donor_key or 'none'}",
    ]
    if plan.notes:
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in plan.notes)
    lines.append("")
    lines.append("Week  Topic       Assignment  Module")
    for week in plan.weeks:
        assignment = week.assignment_id or "-"
        lines.append(f"{week.week:<6}{week.topic_id:<12}{assignment:<12}{week.module_title}")
        preview = " ".join(week.prompt.split())
        if len(preview) > 120:
            preview = preview[:117] + "..."
        lines.append(f"       {preview}")
    return "\n".join(lines)


def format_favorites(favorites: list[dict[str, Any]], courses_config: dict[str, Any]) -> str:
    """Display line for each favorite. Nothing here is imported."""
    courses = courses_config.get("courses") or {}
    known = {str(course.get("course_id")): key for key, course in courses.items()}
    lines = ["Favorite courses (type an id to import; nothing is added automatically):"]
    if not favorites:
        lines.append("  none")
        return "\n".join(lines)
    for course in favorites:
        course_id = str(course.get("id"))
        name = course.get("name") or "Unnamed course"
        key = known.get(course_id)
        if key is None:
            lines.append(f"  {course_id}  {name}")
            continue
        state = "inactive" if courses[key].get("active") is False else "configured"
        lines.append(f"  {course_id}  {name}  ({state} as {key})")
    return "\n".join(lines)


def _reject_voice_mismatch(
    identity: CourseIdentity,
    donor_key: Optional[str],
    donor: Optional[dict[str, Any]],
) -> None:
    if not donor:
        return
    donor_voice = donor.get("voice") or "VOICE.md"
    inferred = identity.voice or "VOICE.md"
    if donor_voice != inferred:
        raise TermSetupError(f"Course name implies {inferred}, but {donor_key} uses {donor_voice}.")


def _start_date_note(name_date: str, start_at: Any) -> Optional[str]:
    if not start_at:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(start_at))
    if not match or match.group(1) == name_date:
        return None
    canvas_date = match.group(1)
    return (
        f"Canvas start_at {canvas_date} differs from the section code {name_date}. "
        f"Using {name_date}."
    )


def _copy_announcements(
    announcements_config: dict[str, Any], donor_key: Optional[str]
) -> Optional[list]:
    if not donor_key:
        return None
    course = (announcements_config.get("courses") or {}).get(donor_key) or {}
    announcements = course.get("announcements") or []
    if not announcements:
        return None
    return copy.deepcopy(announcements)


def _module_sort_key(index: int, module: dict[str, Any]) -> tuple[int, int, int]:
    position = module.get("position")
    if isinstance(position, int):
        return (0, position, index)
    return (1, index, index)


def _module_title(module: dict[str, Any]) -> str:
    return str(module.get("name") or module.get("title") or "Untitled module")


def _is_getting_started(title: str) -> bool:
    return "getting started" in title.lower()


def _discussion_items(module: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in module.get("items") or []:
        if str(item.get("type") or "") != "Discussion":
            continue
        if item.get("content_id") is None:
            continue
        items.append(item)
    return items


def _choose_discussion(
    module_title: str,
    items: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    if len(items) == 1:
        return items[0], []
    graded = []
    choices = []
    for item in items:
        topic_id = str(item.get("content_id"))
        topic = by_id.get(topic_id) or {}
        assignment_id = _assignment_id(topic) if topic else None
        title = str(item.get("title") or topic.get("title") or topic_id)
        choices.append(
            DiscussionChoice(title=title, topic_id=topic_id, assignment_id=assignment_id)
        )
        if assignment_id:
            graded.append(item)
    if len(graded) == 1:
        ignored = [
            str(item.get("title") or item.get("content_id"))
            for item in items
            if item is not graded[0]
        ]
        return graded[0], ignored
    raise AmbiguousModuleError(module_title, choices)


def _topic_id(topic: dict[str, Any]) -> str:
    raw = topic.get("id")
    if raw in (None, ""):
        return ""
    return str(raw)


def _assignment_id(topic: dict[str, Any]) -> Optional[str]:
    raw = topic.get("assignment_id")
    if raw in (None, ""):
        assignment = topic.get("assignment")
        if isinstance(assignment, dict):
            raw = assignment.get("id")
    if raw in (None, ""):
        return None
    text = str(raw)
    if not text.isdigit():
        topic_id = _topic_id(topic) or "?"
        raise TermSetupError(f"Discussion {topic_id} has a non-numeric assignment id: {text}")
    return text
