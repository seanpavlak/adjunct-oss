"""
Course and date utilities for Canvas automation
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from logger import logger
from config import course_config
from schemas import validate_courses_config, validate_announcements_config


def load_courses_config(config_path: Optional[str] = None, validate: bool = True) -> Dict[str, Any]:
    """
    Load and optionally validate course configuration from courses.json
    
    Args:
        config_path: Optional path to courses.json (defaults to ./courses.json)
        validate: Whether to validate configuration with Pydantic schemas
        
    Returns:
        Course configuration dictionary
        
    Raises:
        FileNotFoundError: If courses.json doesn't exist
        ValidationError: If validation is enabled and config is invalid
    """
    base_dir = os.path.dirname(__file__)
    path = config_path or os.path.join(base_dir, 'courses.json')
    
    logger.debug(f"Loading courses config from: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if validate:
        logger.debug("Validating courses configuration")
        validate_courses_config(config)
    
    logger.info(f"Loaded {len(config.get('courses', {}))} course(s)")
    return config


def load_announcements_config(config_path: Optional[str] = None, validate: bool = True) -> Dict[str, Any]:
    """
    Load and optionally validate announcements configuration
    
    Args:
        config_path: Optional path to announcements.json
        validate: Whether to validate configuration with Pydantic schemas
        
    Returns:
        Announcements configuration dictionary
        
    Raises:
        FileNotFoundError: If announcements.json doesn't exist
        ValidationError: If validation is enabled and config is invalid
    """
    base_dir = os.path.dirname(__file__)
    path = config_path or os.path.join(base_dir, 'announcements.json')
    
    logger.debug(f"Loading announcements config from: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if validate:
        logger.debug("Validating announcements configuration")
        validate_announcements_config(config)
    
    logger.info(f"Loaded {len(config.get('announcements', []))} announcement(s)")
    return config


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
    """
    Calculate the current week number based on course start date.
    Week boundaries are Monday-Sunday, so any day within a week counts as that week.
    
    Args:
        course_start_date: Course start date in YYYY-MM-DD format
        
    Returns:
        Current week number (1-8)
    """
    start_date = datetime.strptime(course_start_date, course_config.DATE_FORMAT)
    current_date = datetime.now()
    
    start_monday = start_date - timedelta(days=start_date.weekday())
    
    if current_date.weekday() == 6:
        current_week_monday = current_date - timedelta(days=6)
    else:
        current_week_monday = current_date - timedelta(days=current_date.weekday())
    
    weeks_elapsed = (current_week_monday - start_monday).days // 7
    
    current_week = weeks_elapsed + 1
    
    # Clamp to valid range
    current_week = max(course_config.MIN_WEEK, min(current_week, course_config.MAX_WEEK))
    
    logger.debug(f"Calculated week {current_week} from start date {course_start_date}")
    
    return current_week


def calculate_announcement_dates(course_start_date: str, announcements: list) -> Dict[int, str]:
    """
    Calculate specific dates for each announcement based on course start date.
    Rounds to nearest Monday for each week.
    
    Args:
        course_start_date: Course start date in YYYY-MM-DD format
        announcements: List of announcement dictionaries with 'week' field
        
    Returns:
        Dictionary mapping week numbers to formatted date strings
    """
    start_date = datetime.strptime(course_start_date, course_config.DATE_FORMAT)
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
        formatted_date = announcement_date.strftime(course_config.ANNOUNCEMENT_DATE_FORMAT)
        announcement_dates[week] = formatted_date
        
        logger.debug(f"Week {week} announcement scheduled for {formatted_date}")
    
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

