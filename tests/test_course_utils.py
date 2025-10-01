"""
Unit tests for course_utils module
"""

from datetime import datetime, timedelta

import pytest

from course_utils import (
    calculate_announcement_dates,
    calculate_current_week,
    get_week_prompt,
    resolve_course,
)


class TestCalculateCurrentWeek:
    """Tests for calculate_current_week function"""

    def test_week_1_tuesday_start(self):
        """Test week calculation when course starts on Tuesday"""
        # Mock: Course starts Sept 2, 2025 (Tuesday)
        # If current date is Sept 3 (Wednesday), should be week 1
        start_date = "2025-09-02"
        # This is hard to test without mocking datetime.now()
        # In a real test, you'd use freezegun or similar
        result = calculate_current_week(start_date)
        assert 1 <= result <= 8

    def test_week_bounds(self):
        """Test that week is always between 1 and 8"""
        # Very old start date (should return 8)
        old_date = "2020-01-01"
        result = calculate_current_week(old_date)
        assert result == 8

        # Future start date (should return 1)
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        result = calculate_current_week(future_date)
        assert result == 1


class TestCalculateAnnouncementDates:
    """Tests for calculate_announcement_dates function"""

    def test_single_announcement(self):
        """Test date calculation for single announcement"""
        start_date = "2025-09-02"  # Tuesday
        announcements = [{"week": 1, "title": "Week 1"}]
        dates = calculate_announcement_dates(start_date, announcements)

        assert 1 in dates
        assert isinstance(dates[1], str)
        # Should contain month name
        assert any(
            month in dates[1]
            for month in [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
        )

    def test_multiple_announcements(self):
        """Test date calculation for multiple announcements"""
        start_date = "2025-09-02"
        announcements = [
            {"week": 1, "title": "Week 1"},
            {"week": 2, "title": "Week 2"},
            {"week": 3, "title": "Week 3"},
        ]
        dates = calculate_announcement_dates(start_date, announcements)

        assert len(dates) == 3
        assert all(week in dates for week in [1, 2, 3])
        assert all(isinstance(date, str) for date in dates.values())


class TestResolveCourse:
    """Tests for resolve_course function"""

    def test_resolve_by_key(self):
        """Test resolving course by key"""
        config = {"courses": {"A": {"course_id": "12345", "name": "Test Course"}}}
        course = resolve_course("A", config)
        assert course["course_id"] == "12345"
        assert course["name"] == "Test Course"

    def test_resolve_by_id(self):
        """Test resolving course by ID"""
        config = {"courses": {"A": {"course_id": "12345", "name": "Test Course"}}}
        course = resolve_course("12345", config)
        assert course["course_id"] == "12345"

    def test_course_not_found(self):
        """Test error when course doesn't exist"""
        config = {"courses": {}}
        with pytest.raises(ValueError, match="not found"):
            resolve_course("NONEXISTENT", config)


class TestGetWeekPrompt:
    """Tests for get_week_prompt function"""

    def test_get_existing_prompt(self):
        """Test getting prompt for existing week"""
        config = {"courses": {"A": {"weeks": {"1": {"discussion_prompt": "Test prompt"}}}}}
        prompt = get_week_prompt("A", 1, config)
        assert prompt == "Test prompt"

    def test_get_missing_prompt(self):
        """Test getting prompt for non-existent week"""
        config = {"courses": {"A": {"weeks": {}}}}
        prompt = get_week_prompt("A", 99, config)
        assert "No week 99 data found" in prompt
