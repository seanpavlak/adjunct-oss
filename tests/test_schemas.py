"""
Unit tests for schemas module
"""

import pytest
from pydantic import ValidationError
from schemas import (
    WeekConfig,
    CourseSchema,
    CoursesConfig,
    AnnouncementSchema,
    AnnouncementsConfig
)


class TestWeekConfig:
    """Tests for WeekConfig schema"""
    
    def test_valid_week_config(self):
        """Test valid week configuration"""
        data = {
            "topic_id": "12345",
            "discussion_prompt": "Test prompt",
            "discussion_data": []
        }
        week = WeekConfig(**data)
        assert week.topic_id == "12345"
        assert week.discussion_prompt == "Test prompt"
    
    def test_reject_placeholder_topic_id(self):
        """Test rejection of placeholder topic IDs"""
        data = {
            "topic_id": "FILL_ME",
            "discussion_prompt": "Test prompt"
        }
        with pytest.raises(ValidationError):
            WeekConfig(**data)


class TestCourseSchema:
    """Tests for CourseSchema validation"""
    
    def test_valid_course(self):
        """Test valid course configuration"""
        data = {
            "course_id": "12345",
            "course_start_date": "2025-09-02",
            "name": "Test Course",
            "weeks": {
                "1": {
                    "topic_id": "67890",
                    "discussion_prompt": "Test",
                    "discussion_data": []
                }
            }
        }
        course = CourseSchema(**data)
        assert course.course_id == "12345"
        assert course.name == "Test Course"
    
    def test_invalid_date_format(self):
        """Test rejection of invalid date format"""
        data = {
            "course_id": "12345",
            "course_start_date": "09/02/2025",  # Wrong format
            "weeks": {}
        }
        with pytest.raises(ValidationError):
            CourseSchema(**data)
    
    def test_non_numeric_course_id(self):
        """Test rejection of non-numeric course ID"""
        data = {
            "course_id": "ABC123",  # Should be numeric
            "course_start_date": "2025-09-02",
            "weeks": {}
        }
        with pytest.raises(ValidationError):
            CourseSchema(**data)


class TestAnnouncementSchema:
    """Tests for AnnouncementSchema validation"""
    
    def test_valid_announcement(self):
        """Test valid announcement"""
        data = {
            "week": 1,
            "title": "Week 1 Announcement",
            "content": "<p>Test content</p>"
        }
        announcement = AnnouncementSchema(**data)
        assert announcement.week == 1
        assert announcement.title == "Week 1 Announcement"
    
    def test_week_out_of_range(self):
        """Test rejection of week outside 1-8 range"""
        data = {
            "week": 9,  # Out of range
            "title": "Test",
            "content": "Test"
        }
        with pytest.raises(ValidationError):
            AnnouncementSchema(**data)
    
    def test_empty_title(self):
        """Test rejection of empty title"""
        data = {
            "week": 1,
            "title": "",  # Empty
            "content": "Test"
        }
        with pytest.raises(ValidationError):
            AnnouncementSchema(**data)


class TestCoursesConfig:
    """Tests for CoursesConfig validation"""
    
    def test_empty_courses(self):
        """Test rejection of empty courses"""
        data = {"courses": {}}
        with pytest.raises(ValidationError):
            CoursesConfig(**data)
    
    def test_valid_courses_config(self):
        """Test valid courses configuration"""
        data = {
            "courses": {
                "A": {
                    "course_id": "12345",
                    "course_start_date": "2025-09-02",
                    "weeks": {}
                }
            }
        }
        config = CoursesConfig(**data)
        assert "A" in config.courses

