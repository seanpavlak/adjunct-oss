"""
Canvas Announcement Scheduler - Refactored to use utils and service classes
"""

import os
from dotenv import load_dotenv
from utils import (
    load_courses_config, 
    load_announcements_config, 
    resolve_course, 
    calculate_announcement_dates
)
from canvas_service import CanvasService

# Load environment variables
load_dotenv()


def schedule_announcements(email: str, password: str, course_selector: str) -> None:
    """Main function to schedule all announcements for a course"""
    # Load configurations
    courses_config = load_courses_config()
    announcements_config = load_announcements_config()
    
    # Resolve course
    course = resolve_course(course_selector, courses_config)
    course_id = course.get('course_id')
    course_start_date = course.get('course_start_date')
    
    if not course_start_date:
        raise ValueError(f"Course start date not found for course {course_selector}")
    
    print(f"Course ID: {course_id}")
    print(f"Course Start Date: {course_start_date}")
    
    # Calculate announcement dates
    announcements = announcements_config.get('announcements', [])
    announcement_dates = calculate_announcement_dates(course_start_date, announcements)
    
    # Use CanvasService for browser automation
    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)
        
        # Schedule announcements
        successful_announcements, failed_announcements = canvas.schedule_announcements(
            course_id, announcements, announcement_dates
        )
        
        # Summary
        print(f"\n=== Summary ===")
        print(f"Successful announcements: {successful_announcements}")
        print(f"Failed announcements: {failed_announcements}")
        print(f"Total announcements: {len(announcements)}")


def main():
    """Main entry point"""
    # Configuration - update these values as needed
    username = os.getenv('CANVAS_USERNAME')
    password = os.getenv('CANVAS_PASSWORD')
    course_selector = 'A'  # Use course key from courses.json
    
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")
    
    print("=== Canvas Announcement Scheduler ===")
    print(f"Course: {course_selector}")
    print(f"Username: {username}")
        
    try:
        schedule_announcements(username, password, course_selector)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()