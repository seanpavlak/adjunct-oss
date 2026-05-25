"""
Unit tests for Speed Grader helpers
"""

from chcp.canvas.parsers import parse_student_index


class TestParseStudentIndex:
    """Tests for parse_student_index"""

    def test_parse_with_students_label(self):
        assert parse_student_index("3/10 Students") == (3, 10)

    def test_parse_simple_fraction(self):
        assert parse_student_index("10/10") == (10, 10)

    def test_parse_with_spaces(self):
        assert parse_student_index("1 / 8 Students") == (1, 8)

    def test_parse_invalid_text(self):
        assert parse_student_index("Student 3 of 10") is None
        assert parse_student_index("") is None
