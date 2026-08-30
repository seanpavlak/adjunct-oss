"""Tests for discussion-reply humanize helpers (no live LLM)."""

from unittest.mock import MagicMock

from chcp.llm.humanize import (
    humanize_body,
    is_authentic_example,
    load_voice_profile,
    needs_rewrite,
    prefer_authentic_examples,
    slop_score,
)
from chcp.llm.reply_craft import assemble_reply, strip_ai_filler

AUTHENTIC = (
    "Yeah, it would be a major government achievement to agree on a bill to switch "
    "everything over, this would likely be a decades-long project and would cost "
    "billions of tax dollars to achieve."
)
SLOP = (
    "Great job identifying the three main components of a battery. You've correctly "
    "explained the anode, cathode, and electrolyte. This understanding is crucial "
    "for your field."
)


class TestSlopScore:
    def test_authentic_reply_is_clean(self):
        assert slop_score(AUTHENTIC) == 0
        assert is_authentic_example(AUTHENTIC)
        assert not needs_rewrite(AUTHENTIC)

    def test_grading_speak_is_slop(self):
        assert slop_score(SLOP) >= 2
        assert not is_authentic_example(SLOP)
        assert needs_rewrite(SLOP)

    def test_also_important_to_note_is_slop(self):
        text = (
            "Absolutely true that ambient lighting matters. It's also important to note "
            "that additive and subtractive color systems differ."
        )
        assert needs_rewrite(text)

    def test_your_note_on_is_slop(self):
        assert needs_rewrite("your note on Doppler is the right ultrasound link")
        assert needs_rewrite("Good note on metric conversions in dosing")
        assert needs_rewrite("Note that buoyancy depends on displaced volume")
        assert needs_rewrite("Worth noting that technique matters as much as strength")

    def test_taking_notes_is_not_slop(self):
        text = "Taking notes on the formulas first makes the later weeks a lot easier."
        assert slop_score(text) == 0
        assert not needs_rewrite(text)

    def test_voice_phrases_are_not_slop(self):
        text = "Spot on with the Doppler link. I dig that you tied it to vascular flow."
        assert slop_score(text) == 0
        assert is_authentic_example(text)

    def test_short_garbage_is_not_a_few_shot(self):
        assert not is_authentic_example(" in any system")


class TestPreferAuthenticExamples:
    def test_skips_slop_and_fills_from_extras(self):
        week = [("battery post about anodes", SLOP)]
        extras = [("metric post about mg/mL dosing", AUTHENTIC)]
        picked = prefer_authentic_examples(week, extras=extras, k=1)
        assert picked == extras


class TestVoiceProfile:
    def test_loads_instructor_voice_file(self):
        voice = load_voice_profile()
        assert "I dig that" in voice
        assert "grading-speak" in voice.lower() or "Great job identifying" in voice


class TestStripAndAssemble:
    def test_strips_grading_speak_leftovers(self):
        cleaned = strip_ai_filler(
            "Great job identifying the units. It's important to note that metric scales by tens."
        )
        assert "Great job identifying" not in cleaned
        assert "important to note" not in cleaned.lower()

    def test_strips_note_that_filler(self):
        cleaned = strip_ai_filler("Note that buoyancy depends on displaced volume.")
        assert "note that" not in cleaned.lower()
        assert "buoyancy" in cleaned.lower()

    def test_keeps_spot_on_and_name_lead(self):
        out = assemble_reply(
            student_name="natalie",
            body="Spot on with the Doppler link to vascular flow",
            include_follow_up=False,
        )
        assert out.startswith("Natalie, spot on")
        assert "Doppler" in out or "doppler" in out


class TestHumanizeBodySkip:
    def test_skips_llm_when_draft_is_already_human(self):
        llm = MagicMock()
        out = humanize_body(llm, AUTHENTIC, voice="casual professor")
        assert out == AUTHENTIC
        llm.invoke.assert_not_called()
