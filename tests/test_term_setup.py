"""Term setup mapping, soft-drop, and Canvas JSON reads. No live Canvas."""

import json

import pytest

from chcp.actions.term import _import_loop, run_term_drop
from chcp.canvas.term_api import (
    course_url,
    discussions_url,
    fetch_term_payload,
    modules_url,
    next_link,
    topic_url,
)
from chcp.core.course_binding import bind_course
from chcp.core.course_utils import (
    active_course_keys,
    course_is_active,
    load_courses_config,
    resolve_course,
)
from chcp.core.parallel_courses import course_keys
from chcp.core.schemas import validate_courses_config
from chcp.core.term_setup import (
    AmbiguousModuleError,
    TermSetupError,
    apply_import,
    format_favorites,
    mark_courses_inactive,
    message_to_prompt,
    next_course_key,
    normalize_course_id,
    parse_course_identity,
    prepare_import,
)

PHYS_OLD = "OL PHYS 100 General Physics-C260908AHybridPavlak"
PHYS_NEW = "OL PHYS 100 General Physics-C261102AHybridPavlak"
CRT_NEW = "OL CRT 100 Critical Thinking-C261102AHybridPavlak"


def _topic(topic_id, message, assignment_id=None, due_at=None):
    topic = {"id": topic_id, "message": message, "title": f"Topic {topic_id}"}
    if assignment_id is not None:
        topic["assignment_id"] = assignment_id
    if due_at is not None:
        topic["due_at"] = due_at
    return topic


def _module(position, name, discussions):
    """discussions is a list of (content_id, title) or content ids."""
    items = []
    for entry in discussions:
        if isinstance(entry, tuple):
            content_id, title = entry
        else:
            content_id, title = entry, f"Discussion {entry}"
        items.append(
            {"type": "Discussion", "content_id": content_id, "title": title, "position": 1}
        )
    return {"name": name, "position": position, "items": items}


def _page_module(position, name="Resources"):
    return {
        "name": name,
        "position": position,
        "items": [{"type": "Page", "content_id": 1, "title": "Readings"}],
    }


def _week(prompt="Prompt text", topic_id="11", examples=None, assignment_id="500"):
    week = {
        "topic_id": topic_id,
        "discussion_prompt": prompt,
        "discussion_data": examples or [],
    }
    if assignment_id:
        week["speed_grader"] = {"assignment_id": assignment_id}
    return week


def _course(name, course_id, start, weeks, **extra):
    course = {
        "name": name,
        "course_id": course_id,
        "course_start_date": start,
        "weeks": weeks,
    }
    course.update(extra)
    return course


def _announcement():
    return {"week": 1, "title": "Welcome", "content": "<p>Hello</p>"}


class _Response:
    def __init__(self, payload, status=200, link=None):
        self._payload = payload
        self.status = status
        self.headers = {"link": link} if link else {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Request:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append(url)
        if url not in self.routes:
            raise AssertionError(f"unexpected URL {url}")
        return self.routes[url]


class TestCourseIdentity:
    def test_physics_name_sets_date_and_default_voice(self):
        identity = parse_course_identity(PHYS_OLD)
        assert identity.subject == "physics"
        assert identity.voice is None
        assert identity.start_date == "2026-09-08"

    def test_critical_thinking_name(self):
        identity = parse_course_identity(CRT_NEW)
        assert identity.subject == "critical_thinking"
        assert identity.voice == "VOICE_CRT.md"
        assert identity.start_date == "2026-11-02"

    def test_unknown_subject_stops(self):
        with pytest.raises(TermSetupError, match="PHYS or CRT"):
            parse_course_identity("OL BIO 100 Biology-C260908AHybridPavlak")

    def test_both_codes_stop(self):
        with pytest.raises(TermSetupError, match="PHYS, CRT"):
            parse_course_identity("OL PHYS CRT 100 Mixed-C260908AHybridPavlak")

    def test_missing_section_code(self):
        with pytest.raises(TermSetupError, match="section code"):
            parse_course_identity("OL PHYS 100 General Physics")

    def test_impossible_date(self):
        with pytest.raises(TermSetupError, match="not a real date"):
            parse_course_identity("OL PHYS 100 General Physics-C261332AHybridPavlak")

    def test_course_id_from_url(self):
        assert normalize_course_id("100352") == "100352"
        assert (
            normalize_course_id("https://chcp.instructure.com/courses/100352/modules") == "100352"
        )
        with pytest.raises(TermSetupError, match="numeric"):
            normalize_course_id("physics")


class TestWeekMapping:
    def test_module_order_beats_due_dates_and_skips_empty_modules(self):
        modules = [
            _module(2, "Week Two", [200]),
            _page_module(3),
            _module(1, "Getting Started", [50]),
            _module(4, "Week One", [100]),
        ]
        discussions = [
            _topic(200, "Later prompt", assignment_id=2, due_at="2026-10-01T00:00:00Z"),
            _topic(50, "Intro prompt", assignment_id=5, due_at="2026-12-01T00:00:00Z"),
            _topic(100, "Earlier prompt", assignment_id=1, due_at="2026-09-01T00:00:00Z"),
        ]
        plan = prepare_import(
            {"courses": {}},
            {"courses": {}},
            {"id": 100352, "name": PHYS_NEW, "start_at": "2026-11-02T05:00:00Z"},
            modules,
            discussions,
        )
        assert [(week.week, week.topic_id) for week in plan.weeks] == [
            (0, "50"),
            (1, "200"),
            (2, "100"),
        ]
        assert plan.course["weeks"]["0"]["discussion_prompt"] == "Intro prompt"
        assert plan.course["weeks"]["1"]["speed_grader"]["assignment_id"] == "2"
        assert plan.course["course_start_date"] == "2026-11-02"
        assert "voice" not in plan.course
        assert plan.course["subject"] == "physics"

    def test_single_graded_discussion_wins(self):
        modules = [
            _module(
                1,
                "Week 1",
                [(10, "Ungraded chat"), (11, "Graded discussion")],
            )
        ]
        discussions = [
            _topic(10, "Skip me"),
            _topic(11, "Use me", assignment_id=4054699),
        ]
        plan = prepare_import(
            {"courses": {}},
            {"courses": {}},
            {"id": 100352, "name": PHYS_NEW},
            modules,
            discussions,
        )
        assert plan.course["weeks"]["1"]["topic_id"] == "11"
        assert plan.course["weeks"]["1"]["speed_grader"]["assignment_id"] == "4054699"
        assert any("Ungraded chat" in note for note in plan.notes)

    def test_ambiguous_module_stops(self):
        modules = [_module(1, "Week 1", [(10, "One"), (11, "Two")])]
        discussions = [
            _topic(10, "A", assignment_id=1),
            _topic(11, "B", assignment_id=2),
        ]
        with pytest.raises(AmbiguousModuleError, match="topic_id=10") as caught:
            prepare_import(
                {"courses": {}},
                {"courses": {}},
                {"id": 100352, "name": PHYS_NEW},
                modules,
                discussions,
            )
        assert "topic_id=11" in str(caught.value)

    def test_html_prompt_is_stored_as_text(self):
        plain, stripped = message_to_prompt("<p>Alpha</p><p>Beta</p>")
        assert stripped is True
        assert plain == "Alpha\n\nBeta"
        modules = [_module(1, "Week 1", [11])]
        plan = prepare_import(
            {"courses": {}},
            {"courses": {}},
            {"id": 100352, "name": PHYS_NEW},
            modules,
            [_topic(11, "<p>Alpha</p><p>Beta</p>", assignment_id=9)],
        )
        assert plan.course["weeks"]["1"]["discussion_prompt"] == "Alpha\n\nBeta"
        assert any("HTML" in note for note in plan.notes)

    def test_section_code_wins_when_canvas_start_differs(self):
        plan = prepare_import(
            {"courses": {}},
            {"courses": {}},
            {"id": 100352, "name": PHYS_OLD, "start_at": "2026-09-01T06:00:00Z"},
            [_module(1, "Week 1", [11])],
            [_topic(11, "Prompt", assignment_id=9)],
        )
        assert plan.course["course_start_date"] == "2026-09-08"
        assert any("2026-09-01" in note and "2026-09-08" in note for note in plan.notes)

    def test_missing_discussion_stops(self):
        with pytest.raises(TermSetupError, match="was not in the Canvas topics"):
            prepare_import(
                {"courses": {}},
                {"courses": {}},
                {"id": 100352, "name": PHYS_NEW},
                [_module(1, "Week 1", [11])],
                [],
            )


class TestDonorCopy:
    def _configs(self):
        examples = [{"post": "A student post", "response": "A teacher reply"}]
        older = _course(
            PHYS_OLD,
            "111",
            "2026-01-05",
            {"1": _week(examples=[{"post": "old post", "response": "old reply"}])},
            discussion_rubric={"name": "Old", "rubric_ratings": ["old-rating"]},
        )
        newer = _course(
            PHYS_OLD,
            "222",
            "2026-09-08",
            {
                "1": _week(examples=examples),
                "0": _week(prompt="Intro", topic_id="9", examples=[], assignment_id="8"),
            },
            active=False,
            discussion_rubric={"name": "Donor rubric", "rubric_ratings": ["donor-rating"]},
        )
        courses = {
            "courses": {
                "A": older,
                "B": newer,
                "C": _course(
                    "OL CRT 100 Critical Thinking-C260908BHybridPavlak",
                    "333",
                    "2026-09-08",
                    {"1": _week(prompt="Think", topic_id="3")},
                    subject="critical_thinking",
                    voice="VOICE_CRT.md",
                ),
            }
        }
        announcements = {
            "courses": {
                "B": {"announcements": [_announcement()]},
                "C": {
                    "announcements": [
                        _announcement(),
                        {"week": 2, "title": "Next", "content": "<p>N</p>"},
                    ]
                },
            }
        }
        return courses, announcements, examples

    def test_copies_latest_same_subject_even_when_inactive(self):
        courses, announcements, examples = self._configs()
        modules = [
            _module(1, "Getting Started", [50]),
            _module(2, "Week 1", [11]),
        ]
        discussions = [
            _topic(50, "Hello", assignment_id=5),
            _topic(11, "Metric system", assignment_id=6),
        ]
        plan = prepare_import(
            courses,
            announcements,
            {"id": 100352, "name": PHYS_NEW},
            modules,
            discussions,
        )
        assert plan.key == "D"
        assert plan.donor_key == "B"
        assert plan.course["discussion_rubric"]["rubric_ratings"] == ["donor-rating"]
        assert plan.course["weeks"]["1"]["discussion_data"] == examples
        assert plan.course["weeks"]["1"]["discussion_data"] is not examples
        assert plan.course["weeks"]["0"]["discussion_data"] == []
        assert plan.announcements == [_announcement()]
        assert plan.announcements is not announcements["courses"]["B"]["announcements"]
        assert "voice" not in plan.course

        apply_import(courses, announcements, plan)
        validate_courses_config(courses)
        assert courses["courses"]["D"]["course_id"] == "100352"
        assert courses["courses"]["B"]["active"] is False

    def test_week_zero_examples_copy_when_the_donor_has_them(self):
        courses, announcements, _examples = self._configs()
        courses["courses"]["B"]["weeks"]["0"]["discussion_data"] = [
            {"post": "intro post", "response": "intro reply"}
        ]
        plan = prepare_import(
            courses,
            announcements,
            {"id": 100352, "name": PHYS_NEW},
            [_module(1, "Getting Started", [50])],
            [_topic(50, "Hello", assignment_id=5)],
        )
        assert plan.course["weeks"]["0"]["discussion_data"][0]["post"] == "intro post"

    def test_critical_thinking_voice_and_announcements(self):
        courses, announcements, _examples = self._configs()
        plan = prepare_import(
            courses,
            announcements,
            {"id": 100353, "name": CRT_NEW},
            [_module(1, "Week 1", [70])],
            [_topic(70, "What is a claim?", assignment_id=70)],
        )
        assert plan.donor_key == "C"
        assert plan.course["subject"] == "critical_thinking"
        assert plan.course["voice"] == "VOICE_CRT.md"
        assert len(plan.announcements) == 2

    def test_no_donor_uses_builtin_rubric_and_warns(self):
        plan = prepare_import(
            {"courses": {}},
            {"courses": {}},
            {"id": 100352, "name": PHYS_NEW},
            [_module(1, "Week 1", [11])],
            [_topic(11, "Prompt", assignment_id=9)],
        )
        assert plan.donor_key is None
        assert plan.announcements is None
        assert plan.course["discussion_rubric"]["name"] == "Discussion Rubric (2021)"
        assert plan.course["weeks"]["1"]["discussion_data"] == []
        assert any("built-in discussion rubric" in note for note in plan.notes)

    def test_duplicate_course_id_is_refused(self):
        courses = {
            "courses": {
                "A": _course(PHYS_OLD, "100352", "2026-09-08", {"1": _week()}, active=False)
            }
        }
        with pytest.raises(TermSetupError, match="already configured as A"):
            prepare_import(
                courses,
                {"courses": {}},
                {"id": "100352", "name": PHYS_NEW},
                [_module(1, "Week 1", [11])],
                [_topic(11, "Prompt", assignment_id=9)],
            )

    def test_voice_mismatch_stops(self):
        donor = _course(
            CRT_NEW,
            "1",
            "2026-09-08",
            {"1": _week()},
            subject="critical_thinking",
            voice="VOICE.md",
        )
        with pytest.raises(TermSetupError, match="VOICE_CRT.md"):
            prepare_import(
                {"courses": {"A": donor}},
                {"courses": {}},
                {"id": 9, "name": "OL CRT 100 Critical Thinking-C261102BHybridPavlak"},
                [_module(1, "Week 1", [11])],
                [_topic(11, "Prompt", assignment_id=9)],
            )

    def test_next_key_uses_the_first_gap(self):
        assert next_course_key({"A": {}, "C": {}}) == "B"
        assert next_course_key({"A": {}, "B": {}, "C": {}}) == "D"


class TestSoftDrop:
    def test_inactive_courses_stay_resolvable_but_leave_menus(self):
        config = {
            "courses": {
                "A": {"course_id": "1", "active": True},
                "B": {"course_id": "2", "active": False, "name": "Old"},
            }
        }
        assert course_is_active(config["courses"]["A"]) is True
        assert course_is_active({"name": "missing flag"}) is True
        assert active_course_keys(config) == ["A"]
        assert course_keys(config) == ["A"]
        assert resolve_course("B", config)["name"] == "Old"
        with pytest.raises(ValueError, match="No active courses"):
            course_keys({"courses": {"B": {"active": False}}})

    def test_mark_inactive_keeps_the_rest_of_the_course(self):
        config = {
            "courses": {
                "A": _course(
                    PHYS_OLD,
                    "1",
                    "2026-09-08",
                    {"1": _week(examples=[{"post": "keep", "response": "keep"}])},
                )
            }
        }
        changed = mark_courses_inactive(config, ["A"])
        assert changed == ["A"]
        assert config["courses"]["A"]["active"] is False
        assert config["courses"]["A"]["weeks"]["1"]["discussion_data"][0]["post"] == "keep"
        assert mark_courses_inactive(config, ["A"]) == []

    def test_drop_command_writes_active_false(self, tmp_path, monkeypatch):
        path = tmp_path / "courses.json"
        config = {"courses": {"A": _course(PHYS_OLD, "1", "2026-09-08", {"1": _week()})}}
        path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _prompt: "y")
        run_term_drop(["A"], config_path=str(path))
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["courses"]["A"]["active"] is False
        assert saved["courses"]["A"]["course_id"] == "1"
        assert load_courses_config(str(path))["courses"]["A"]["weeks"]["1"]["topic_id"] == "11"

    def test_drop_can_be_cancelled(self, tmp_path, monkeypatch):
        path = tmp_path / "courses.json"
        original = json.dumps(
            {"courses": {"A": _course(PHYS_OLD, "1", "2026-09-08", {"1": _week()})}}
        )
        path.write_text(original, encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _prompt: "n")
        run_term_drop(["A"], config_path=str(path))
        assert path.read_text(encoding="utf-8") == original

    def test_inactive_prompt_is_still_foreign(self):
        own = "Physics week one prompt about the metric system and measurement."
        other = "Critical thinking week one prompt about claims evidence and logic."
        config = {
            "courses": {
                "A": _course(PHYS_OLD, "1", "2026-09-08", {"1": _week(prompt=own, examples=[])}),
                "B": _course(
                    "OL CRT 100 Critical Thinking-C260908AHybridPavlak",
                    "2",
                    "2026-09-08",
                    {"1": _week(prompt=other, topic_id="2", examples=[])},
                    active=False,
                    subject="critical_thinking",
                    voice="VOICE_CRT.md",
                ),
            }
        }
        binding = bind_course("A", 1, config)
        marker = " ".join(other.split())[:120]
        assert marker in binding.foreign_markers


class TestFavoritesAndFetch:
    def test_favorites_are_labeled_and_not_imported(self):
        config = {
            "courses": {
                "A": {"course_id": "10", "name": "Live"},
                "B": {"course_id": "20", "name": "Old", "active": False},
            }
        }
        text = format_favorites(
            [
                {"id": 10, "name": "Live course"},
                {"id": 20, "name": "Old course"},
                {"id": 30, "name": "New course"},
            ],
            config,
        )
        assert "configured as A" in text
        assert "inactive as B" in text
        assert "30  New course" in text
        assert "automatically" in text

    def test_next_link(self):
        header = (
            "<https://chcp.instructure.com/api/v1/courses/1/modules?page=2&per_page=100>; "
            'rel="next", '
            '<https://chcp.instructure.com/api/v1/courses/1/modules?page=1>; rel="first"'
        )
        assert next_link(header).endswith("page=2&per_page=100")
        assert next_link(None) is None
        assert next_link('<https://example.com/x>; rel="last"') is None

    def test_fetch_follows_pages_and_fills_missing_topics(self):
        course_id = "100352"
        page_two = "https://chcp.instructure.com/api/v1/courses/100352/discussion_topics?page=2"
        request = _Request(
            {
                course_url(course_id): _Response({"id": 100352, "name": PHYS_NEW}),
                modules_url(course_id): _Response(
                    [
                        _module(1, "Getting Started", [50]),
                        _module(2, "Week 1", [11]),
                    ]
                ),
                discussions_url(course_id): _Response(
                    [_topic(50, "Hello", assignment_id=5)],
                    link=f'<{page_two}>; rel="next"',
                ),
                page_two: _Response([_topic(11, "Metric", assignment_id=6)]),
                topic_url(course_id, "77"): _Response(_topic(77, "Filled", assignment_id=7)),
            }
        )
        request.routes[modules_url(course_id)]._payload.append(_module(3, "Week 2", [77]))
        payload = fetch_term_payload(request, course_id)
        ids = {str(topic["id"]) for topic in payload["discussions"]}
        assert ids == {"50", "11", "77"}
        assert topic_url(course_id, "77") in request.calls
        assert page_two in request.calls

    def test_refused_session_is_an_error(self):
        request = _Request({course_url("1"): _Response({"errors": []}, status=401)})
        with pytest.raises(TermSetupError, match="refused"):
            fetch_term_payload(request, "1")

    def test_html_body_is_an_error(self):
        request = _Request({course_url("1"): _Response(ValueError("not json"))})
        with pytest.raises(TermSetupError, match="not JSON"):
            fetch_term_payload(request, "1")


class TestImportLoop:
    def _routes(self, course_id="100352"):
        return {
            course_url(course_id): _Response({"id": int(course_id), "name": PHYS_NEW}),
            modules_url(course_id): _Response([_module(1, "Week 1", [11])]),
            discussions_url(course_id): _Response(
                [_topic(11, "What do you know about physics?", assignment_id=9)]
            ),
        }

    def _store(self):
        courses = {
            "courses": {
                "A": _course(
                    PHYS_OLD,
                    "111",
                    "2026-09-08",
                    {"1": _week(examples=[{"post": "student", "response": "teacher"}])},
                )
            }
        }
        announcements = {"courses": {"A": {"announcements": [_announcement()]}}}
        return courses, announcements

    def test_dry_run_does_not_write_or_prompt(self, monkeypatch):
        def boom(_prompt):
            raise AssertionError("dry run should not prompt")

        monkeypatch.setattr("builtins.input", boom)
        courses, announcements = self._store()
        _import_loop(
            _Request(self._routes()),
            courses,
            announcements,
            course_id="100352",
            dry_run=True,
            courses_path="unused-courses.json",
            announcements_path="unused-announcements.json",
        )
        assert "B" not in courses["courses"]

    def test_confirmed_write_updates_both_files(self, tmp_path, monkeypatch):
        answers = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
        courses, announcements = self._store()
        courses_path = tmp_path / "courses.json"
        announcements_path = tmp_path / "announcements.json"
        _import_loop(
            _Request(self._routes()),
            courses,
            announcements,
            course_id="https://chcp.instructure.com/courses/100352",
            dry_run=False,
            courses_path=str(courses_path),
            announcements_path=str(announcements_path),
        )
        saved = json.loads(courses_path.read_text(encoding="utf-8"))
        assert saved["courses"]["B"]["course_id"] == "100352"
        assert saved["courses"]["B"]["course_start_date"] == "2026-11-02"
        assert saved["courses"]["B"]["weeks"]["1"]["discussion_data"][0]["response"] == "teacher"
        assert saved["courses"]["A"]["course_id"] == "111"
        copied = json.loads(announcements_path.read_text(encoding="utf-8"))
        assert copied["courses"]["B"]["announcements"][0]["title"] == "Welcome"

    def test_declining_the_preview_does_not_write(self, tmp_path, monkeypatch):
        answers = iter(["n", "n"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
        courses, announcements = self._store()
        courses_path = tmp_path / "courses.json"
        _import_loop(
            _Request(self._routes()),
            courses,
            announcements,
            course_id="100352",
            dry_run=False,
            courses_path=str(courses_path),
            announcements_path=str(tmp_path / "announcements.json"),
        )
        assert not courses_path.exists()
        assert "B" not in courses["courses"]


def test_current_courses_file_stays_active():
    config = load_courses_config()
    assert active_course_keys(config) == ["A", "B", "C"]
