"""
Unit tests for Canvas service helpers (no browser)
"""

from chcp.canvas.parsers import (
    is_usable_student_post,
    normalize_discussion_content,
    parse_days_late_value,
    parse_rubric_total_points,
    parse_student_index,
)


class TestNormalizeDiscussionContent:
    def test_joins_and_collapses_whitespace(self):
        assert (
            normalize_discussion_content(["  Hello  world  ", "More\ntext"])
            == "Hello world More text"
        )

    def test_empty_inputs(self):
        assert normalize_discussion_content([]) == ""
        assert normalize_discussion_content(["", "  ", None]) == ""  # type: ignore[list-item]

    def test_single_paragraph_without_p_tags(self):
        assert normalize_discussion_content(["My takeaway is Newton's laws."]) == (
            "My takeaway is Newton's laws."
        )


class TestIsUsableStudentPost:
    def test_rejects_empty_and_sentinel(self):
        assert not is_usable_student_post("")
        assert not is_usable_student_post(None)
        assert not is_usable_student_post("Content not found or not loaded.")
        assert not is_usable_student_post("   content not found  ")

    def test_rejects_too_short(self):
        assert not is_usable_student_post("Too short.")

    def test_accepts_real_post(self):
        post = (
            "My most valuable takeaway was instantaneous speed versus average speed, "
            "especially how that connects to ultrasound wave propagation."
        )
        assert is_usable_student_post(post)


class TestParseStudentIndex:
    def test_simple_fraction(self):
        assert parse_student_index("3/10") == (3, 10)

    def test_with_label(self):
        assert parse_student_index("3 / 10 Students") == (3, 10)


class TestParseDaysLateValue:
    def test_numeric(self):
        assert parse_days_late_value("2") == 2.0

    def test_fractional_days(self):
        assert parse_days_late_value("0.98") == 0.98

    def test_empty_defaults_one(self):
        assert parse_days_late_value("") == 1.0

    def test_whitespace_number(self):
        assert parse_days_late_value("  1  ") == 1.0


class TestTimelinessFromDaysLate:
    def test_standard_round_to_whole_days(self):
        from chcp.grading.parse import timeliness_level_from_days_late

        assert timeliness_level_from_days_late(0) == "meets"
        assert timeliness_level_from_days_late(0.1) == "meets"
        assert timeliness_level_from_days_late(0.49) == "meets"
        assert timeliness_level_from_days_late(0.51) == "needs"
        assert timeliness_level_from_days_late(0.98) == "needs"
        assert timeliness_level_from_days_late(1) == "needs"
        assert timeliness_level_from_days_late(2) == "below"


class TestParseRubricTotalPoints:
    def test_plain_number(self):
        assert parse_rubric_total_points("91") == "91"

    def test_out_of_total(self):
        assert parse_rubric_total_points("91 / 100") == "91"

    def test_decimal(self):
        assert parse_rubric_total_points("85.5") == "85.5"

    def test_empty(self):
        assert parse_rubric_total_points("") is None
