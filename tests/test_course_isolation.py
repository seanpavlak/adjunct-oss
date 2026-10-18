"""Course bindings stay inside one class, even when ALL runs the others."""

import os
from unittest.mock import MagicMock

import pytest

from chcp.canvas.service import CanvasService
from chcp.canvas.session import discard_session_file, url_needs_canvas_login
from chcp.core.course_binding import (
    CourseIsolationError,
    assert_worker_course,
    bind_course,
    chromium_launch_args,
    url_is_course,
)
from chcp.core.course_utils import load_courses_config
from chcp.core.parallel_courses import PrefixWriter, build_worker_commands
from chcp.llm.response_generator import ResponseGenerator
from chcp.rubric_grader import RubricGrader


class TestCourseBinding:
    def test_each_course_rejects_the_others_prompt_and_examples(self):
        config = load_courses_config()
        bindings = {key: bind_course(key, 1, config) for key in ("A", "B", "C")}

        assert bindings["A"].course_id == "98479"
        assert bindings["B"].course_id == "97094"
        assert bindings["C"].course_id == "98483"
        assert bindings["A"].subject == "physics"
        assert bindings["B"].subject == "critical_thinking"
        assert bindings["A"].discussion_prompt != bindings["B"].discussion_prompt
        assert bindings["B"].discussion_prompt == bindings["C"].discussion_prompt
        assert bindings["A"].voice_profile != bindings["B"].voice_profile
        assert bindings["B"].voice_profile == bindings["C"].voice_profile

        physics_examples = set(bindings["A"].course_examples)
        assert physics_examples
        assert not set(bindings["B"].course_examples) & physics_examples
        assert not set(bindings["C"].course_examples) & physics_examples

        for key, binding in bindings.items():
            others = [other for other_key, other in bindings.items() if other_key != key]
            for other in others:
                if other.discussion_prompt == binding.discussion_prompt:
                    continue
                with pytest.raises(CourseIsolationError):
                    binding.assert_outbound(
                        discussion_prompt=other.discussion_prompt,
                        voice_profile=binding.voice_profile,
                        subject=binding.subject,
                        few_shots=[],
                        outbound_text=binding.discussion_prompt,
                    )

    def test_own_material_is_not_flagged_as_foreign(self, monkeypatch):
        monkeypatch.setattr(
            "chcp.llm.response_generator.LLMManager.create_llm",
            lambda *args, **kwargs: MagicMock(),
        )
        config = load_courses_config()
        for key in ("A", "B", "C"):
            generator = ResponseGenerator(
                week=1,
                course_selector=key,
                provider="openai",
                openai_key="test-key",
            )
            few_shots = generator._select_few_shots(
                "the student wrote about evidence and units",
                generator._load_discussion_examples(),
            )
            examples_text = generator._format_examples(few_shots)
            messages = generator.prompt.format_messages(
                content="I measured the solution in milliliters and checked the claim.",
                examples=examples_text,
                anchors="metric system",
                student_name="Alex",
                follow_up_mode="OFF",
            )
            outbound = "\n".join(str(message.content) for message in messages)
            generator.binding.assert_outbound(
                discussion_prompt=generator.dq_prompt,
                voice_profile=generator.voice_profile,
                subject=generator.subject,
                few_shots=few_shots,
                outbound_text=outbound,
            )
            for other_key in ("A", "B", "C"):
                if other_key == key:
                    continue
                other = bind_course(other_key, 1, config)
                if other.discussion_prompt == generator.binding.discussion_prompt:
                    continue
                assert other.discussion_prompt not in outbound
                assert other.voice_profile not in outbound

    def test_injected_example_from_another_course_is_refused(self):
        config = load_courses_config()
        physics = bind_course("A", 1, config)
        stolen = physics.course_examples[0]
        critical = bind_course("B", 1, config)
        with pytest.raises(CourseIsolationError):
            critical.assert_outbound(
                discussion_prompt=critical.discussion_prompt,
                voice_profile=critical.voice_profile,
                subject=critical.subject,
                few_shots=[stolen],
                outbound_text=critical.discussion_prompt,
            )


class TestWorkerSeal:
    def test_worker_cannot_switch_courses(self, monkeypatch):
        monkeypatch.setenv("CHCP_COURSE_KEY", "A")
        assert_worker_course("A")
        with pytest.raises(CourseIsolationError):
            assert_worker_course("B")
        with pytest.raises(CourseIsolationError):
            assert_worker_course("ALL")

    def test_url_must_match_the_sealed_course(self):
        assert url_is_course(
            "https://chcp.instructure.com/courses/98479/discussion_topics/1231823",
            "98479",
        )
        assert not url_is_course(
            "https://chcp.instructure.com/courses/97094/discussion_topics/1225713",
            "98479",
        )
        assert not url_is_course(
            "https://chcp.instructure.com/courses/984791/discussion_topics/1",
            "98479",
        )
        assert not url_is_course("https://chcp.instructure.com/login/canvas", "98479")

    def test_windows_land_in_different_slots(self):
        first = chromium_launch_args(0)
        second = chromium_launch_args(1)
        third = chromium_launch_args(2)
        assert first != second != third
        assert "--window-position=0,0" in first
        assert "--window-position=80,56" in second
        assert "--window-position=160,112" in third
        assert chromium_launch_args(None) == []

    def test_all_builds_one_sealed_process_per_course(self):
        workers = build_worker_commands(
            "discussion",
            ["A", "B", "C"],
            week=4,
            provider="openai",
            extra_args=["--dry-run"],
            python="python",
            main_py="main.py",
        )
        assert len(workers) == 3
        seen = set()
        for slot, (cmd, env) in enumerate(workers):
            key = cmd[cmd.index("--course") + 1]
            seen.add(key)
            assert env["CHCP_COURSE_KEY"] == key
            assert env["CHCP_PARALLEL"] == "1"
            assert env["CHCP_WINDOW_SLOT"] == str(slot)
            assert cmd[cmd.index("--window-slot") + 1] == str(slot)
            assert "--week" in cmd and "4" in cmd
            assert "--provider" in cmd and "openai" in cmd
            assert "--dry-run" in cmd
            assert "CHCP_STORAGE_STATE" not in env
        assert seen == {"A", "B", "C"}

    def test_all_windows_share_one_session_and_keep_course_keys(self):
        workers = build_worker_commands(
            "discussion",
            ["A", "B", "C"],
            storage_state_path="/tmp/chcp-canvas-session-test.json",
            python="python",
            main_py="main.py",
        )
        sessions = {env["CHCP_STORAGE_STATE"] for _, env in workers}
        keys = {env["CHCP_COURSE_KEY"] for _, env in workers}
        assert sessions == {"/tmp/chcp-canvas-session-test.json"}
        assert keys == {"A", "B", "C"}

    def test_log_prefix_does_not_mix_lines(self):
        class Buffer:
            def __init__(self):
                self.chunks = []

            def write(self, data):
                self.chunks.append(data)

            def flush(self):
                pass

        buf = Buffer()
        writer = PrefixWriter(buf, "[B] ")
        writer.write("hello ")
        writer.write("there\nnext")
        writer.flush()
        assert "".join(buf.chunks) == "[B] hello there\n[B] next"


class TestGradeSeal:
    def test_grader_refuses_another_courses_prompt(self, monkeypatch):
        monkeypatch.setattr(
            "chcp.rubric_grader.ChatOpenAI",
            lambda **kwargs: MagicMock(),
        )
        config = load_courses_config()
        physics = bind_course("A", 1, config)
        critical = bind_course("B", 1, config)
        grader = RubricGrader(
            provider="openai",
            openai_key="test-key",
            sealed_course_key=physics.course_key,
            sealed_discussion_prompt=physics.discussion_prompt,
        )
        with pytest.raises(CourseIsolationError):
            grader._assert_sealed_prompt(critical.discussion_prompt)
        grader._assert_sealed_prompt(physics.discussion_prompt)


class TestSharedSession:
    def test_login_urls_still_need_mfa(self):
        assert url_needs_canvas_login("https://chcp.instructure.com/login/canvas")
        assert url_needs_canvas_login("https://chcp.instructure.com/login/otp")
        assert not url_needs_canvas_login("https://chcp.instructure.com/")
        assert not url_needs_canvas_login(
            "https://chcp.instructure.com/courses/98479/discussion_topics/1"
        )

    def test_shared_session_does_not_request_another_code(self):
        canvas = CanvasService(storage_state_path="/tmp/chcp-canvas-session-test.json")
        canvas.restore_shared_session = lambda: True
        canvas.login = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("login should not run")
        )
        calls = []
        canvas.ensure_logged_in("user", "pass", otp_provider=lambda: calls.append("otp"))
        assert calls == []

    def test_rejected_session_does_not_submit_another_code(self):
        canvas = CanvasService(storage_state_path="/tmp/chcp-canvas-session-test.json")
        canvas.restore_shared_session = lambda: False

        def otp():
            raise AssertionError("otp should not be requested")

        with pytest.raises(RuntimeError, match="will not submit another MFA code"):
            canvas.ensure_logged_in("user", "pass", otp_provider=otp)

    def test_discard_removes_the_session_file(self, tmp_path):
        path = tmp_path / "session.json"
        path.write_text('{"cookies": []}', encoding="utf-8")
        discard_session_file(str(path))
        assert not path.exists()
        discard_session_file(str(path))


def test_unsealed_process_can_still_run_one_course(monkeypatch):
    monkeypatch.delenv("CHCP_COURSE_KEY", raising=False)
    assert os.environ.get("CHCP_COURSE_KEY") is None
    assert_worker_course("C")
