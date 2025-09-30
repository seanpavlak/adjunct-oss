"""
Utility functions for Canvas automation and course management
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple


def load_courses_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load course configuration from courses.json"""
    base_dir = os.path.dirname(__file__)
    path = config_path or os.path.join(base_dir, 'courses.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_announcements_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load announcements configuration from announcements.json"""
    base_dir = os.path.dirname(__file__)
    path = config_path or os.path.join(base_dir, 'announcements.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_course(course_selector: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve course selector to course configuration"""
    courses = config.get('courses', {})
    if course_selector in courses:
        course = courses[course_selector]
    else:
        course = next((c for c in courses.values() if c.get('course_id') == str(course_selector)), None)
    if not course:
        raise ValueError(f"Course '{course_selector}' not found in courses.json")
    return course


def calculate_current_week(course_start_date: str) -> int:
    """Calculate the current week number based on course start date.
    Week boundaries are Monday-Sunday, so any day within a week counts as that week."""
    start_date = datetime.strptime(course_start_date, '%Y-%m-%d')
    current_date = datetime.now()
    
    start_monday = start_date - timedelta(days=start_date.weekday())
    
    if current_date.weekday() == 6:
        current_week_monday = current_date - timedelta(days=6)
    else:
        current_week_monday = current_date - timedelta(days=current_date.weekday())
    
    weeks_elapsed = (current_week_monday - start_monday).days // 7
    
    current_week = weeks_elapsed + 1
    
    current_week = max(1, min(current_week, 8))
    
    return current_week


def calculate_announcement_dates(course_start_date: str, announcements: list) -> Dict[int, str]:
    """Calculate specific dates for each announcement based on course start date, rounded to nearest Monday"""
    start_date = datetime.strptime(course_start_date, '%Y-%m-%d')
    announcement_dates = {}
    
    for announcement in announcements:
        week = announcement['week']
        announcement_date = start_date + timedelta(weeks=week-1)
        
        days_until_monday = (7 - announcement_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 0
        elif announcement_date.weekday() <= 3:
            days_until_monday = -announcement_date.weekday()
        else:
            days_until_monday = 7 - announcement_date.weekday()
        
        announcement_date = announcement_date + timedelta(days=days_until_monday)
        announcement_dates[week] = announcement_date.strftime('%B %d %Y')
    
    return announcement_dates


def resolve_course_and_topic(course_selector: str, week_id: int, config: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve course selector and week to get course_id and topic_id"""
    course = resolve_course(course_selector, config)
    course_id = course.get('course_id')
    weeks = course.get('weeks', {})
    week_data = weeks.get(str(week_id))
    if not week_data:
        raise ValueError(f"Missing week {week_id} data in course {course_selector}")
    topic_id = week_data.get('topic_id')
    if not topic_id or topic_id == 'FILL_ME':
        raise ValueError(f"Missing topic_id for week {week_id} in course {course_selector}")
    return course_id, topic_id


def get_week_prompt(course_selector: str, week_id: int, config: Dict[str, Any]) -> str:
    """Get the discussion prompt for a specific week"""
    try:
        weeks = config.get('courses', {}).get(course_selector, {}).get('weeks', {})
        week_data = weeks.get(str(week_id))
        if week_data:
            return week_data.get('discussion_prompt', 'No prompt available')
        else:
            return f"No week {week_id} data found"
    except Exception as e:
        return f"<Prompt not available: {e}>"
