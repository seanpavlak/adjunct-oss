"""
Canvas Announcement Scheduler - Automates scheduling of course announcements
"""

import argparse
import os

from dotenv import load_dotenv

from canvas_service import CanvasService
from course_utils import (
    calculate_announcement_dates,
    load_announcements_config,
    load_courses_config,
    resolve_course,
)

# Load environment variables
load_dotenv()


def schedule_announcements(email: str, password: str, course_selector: str) -> None:
    """Main function to schedule all announcements for a course"""
    # Load configurations
    courses_config = load_courses_config()
    announcements_config = load_announcements_config()

    # Resolve course
    course = resolve_course(course_selector, courses_config)
    course_id = course.get("course_id")
    course_start_date = course.get("course_start_date")

    if not course_start_date:
        raise ValueError(f"Course start date not found for course {course_selector}")

    print(f"Course ID: {course_id}")
    print(f"Course Start Date: {course_start_date}")

    # Calculate announcement dates
    announcements = announcements_config.get("announcements", [])
    announcement_dates = calculate_announcement_dates(course_start_date, announcements)

    # Use CanvasService for browser automation
    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)

        # Schedule announcements
        successful_announcements, failed_announcements = canvas.schedule_announcements(
            course_id, announcements, announcement_dates
        )

        # Summary
        print("\n=== Summary ===")
        print(f"Successful announcements: {successful_announcements}")
        print(f"Failed announcements: {failed_announcements}")
        print(f"Total announcements: {len(announcements)}")


def main():
    """Main entry point with CLI argument support"""
    parser = argparse.ArgumentParser(
        description="Canvas Announcement Scheduler",
        epilog="💡 Find this helpful? https://buymeacoffee.com/seanpavlak",
    )
    parser.add_argument("--course", default="A", help="Course selector (default: A)")

    args = parser.parse_args()

    username = os.getenv("CANVAS_USERNAME")
    password = os.getenv("CANVAS_PASSWORD")

    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")

    print("=== Canvas Announcement Scheduler ===")
    print(f"Course: {args.course}")
    print(f"Username: {username}")

    try:
        schedule_announcements(username, password, args.course)
        print("\n💡 Saved you time? Consider supporting: https://buymeacoffee.com/seanpavlak")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
