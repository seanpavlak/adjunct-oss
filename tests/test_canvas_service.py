"""
Unit tests for Canvas service helpers (no browser)
"""

from canvas_service import (
    parse_days_late_value,
    parse_rubric_total_points,
    parse_student_index,
)


class TestParseStudentIndex:
    def test_simple_fraction(self):
        assert parse_student_index("3/10") == (3, 10)

    def test_with_label(self):
        assert parse_student_index("3 / 10 Students") == (3, 10)


class TestParseDaysLateValue:
    def test_numeric(self):
        assert parse_days_late_value("2") == 2

    def test_empty_defaults_one(self):
        assert parse_days_late_value("") == 1

    def test_whitespace_number(self):
        assert parse_days_late_value("  1  ") == 1


class TestParseRubricTotalPoints:
    def test_plain_number(self):
        assert parse_rubric_total_points("91") == "91"

    def test_out_of_total(self):
        assert parse_rubric_total_points("91 / 100") == "91"

    def test_decimal(self):
        assert parse_rubric_total_points("85.5") == "85.5"

    def test_empty(self):
        assert parse_rubric_total_points("") is None
