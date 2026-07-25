"""Tests for discussion reply craft helpers (no LLM)."""

from chcp.llm.reply_craft import (
    analyze_student_post,
    assemble_reply,
    format_display_name,
    strip_trailing_questions,
)


class TestFormatDisplayName:
    def test_title_case(self):
        assert format_display_name("natalie") == "Natalie"
        assert format_display_name("MARY-JANE") == "Mary-Jane"
        assert format_display_name("o'brien") == "O'Brien"

    def test_blank(self):
        assert format_display_name("") == ""
        assert format_display_name(None) == ""


class TestAnalyzeStudentPost:
    def test_finds_physics_and_career(self):
        post = (
            "I learned speed versus velocity and how gravity accelerates objects. "
            "As a cardiac sonographer, Doppler helps measure blood velocity."
        )
        anchors = analyze_student_post(post)
        assert any("velocity" in c.lower() or "speed" in c.lower() for c in anchors.concepts)
        assert any(
            "sonograph" in h.lower() or "ultrasound" in h.lower() for h in anchors.career_hooks
        )
        assert anchors.key_sentences


class TestAssembleReply:
    def test_leads_with_capitalized_name(self):
        out = assemble_reply(
            student_name="natalie",
            body="the metric point about medication dosing is the key one here",
            include_follow_up=False,
        )
        assert out.startswith("Natalie, the metric")
        assert "?" not in out

    def test_lowercases_body_after_name(self):
        out = assemble_reply(
            student_name="sean",
            body="Your post on Doppler is the right ultrasound link",
            include_follow_up=False,
        )
        assert out.startswith("Sean, your post")

    def test_strips_padded_opener_and_adds_question(self):
        out = assemble_reply(
            student_name="Thomas",
            body="Exactly, Thomas, Doppler shift is the right link to vascular flow",
            follow_up_question="how would a stenosis change the measured frequency shift",
            include_follow_up=True,
        )
        assert out.startswith("Thomas, doppler shift") or out.startswith("Thomas, Doppler shift")
        # After stripping name lead from body, first letter is lowercased
        assert out.startswith("Thomas, ")
        assert out[len("Thomas, ")].islower()
        assert "Exactly" not in out
        assert out.endswith("?")

    def test_strips_questions_when_follow_up_off(self):
        out = assemble_reply(
            student_name="Dalaynee",
            body="Gravity sets the acceleration near Earth. What else affects fall time?",
            include_follow_up=False,
        )
        assert out.startswith("Dalaynee, gravity")
        assert "?" not in out


class TestStripTrailingQuestions:
    def test_keeps_statements(self):
        assert "Earth" in strip_trailing_questions("Gravity pulls toward Earth. Why though?")
