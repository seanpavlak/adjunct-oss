"""
Canvas Discussion Scraper - Refactored to use utils and service classes
"""

import os
import time
from dotenv import load_dotenv
from utils import (
    load_courses_config, 
    calculate_current_week, 
    resolve_course_and_topic, 
    get_week_prompt
)
from canvas_service import CanvasService

# Load environment variables
load_dotenv()


def scrape(email: str = None, password: str = None, course_selector: str = None, week_id: int = None) -> None:
    """Main scraping function for Canvas discussions"""
    if not email or not password:
        print("Email and password must be provided")
        return
    if not course_selector:
        print("Course selector (course key or course_id) must be provided")
        return

    config = load_courses_config()
    
    courses = config.get('courses', {})
    if course_selector in courses:
        course = courses[course_selector]
    else:
        course = next((c for c in courses.values() if c.get('course_id') == str(course_selector)), None)
    
    if not course:
        raise ValueError(f"Course '{course_selector}' not found in courses.json")
    
    if week_id is None:
        course_start_date = course.get('course_start_date')
        if not course_start_date:
            raise ValueError(f"Course start date not found for course {course_selector}")
        week_id = calculate_current_week(course_start_date)
        print(f"Auto-calculated current week: {week_id} (based on course start date: {course_start_date})")
    else:
        print(f"Using manually specified week: {week_id}")
    
    course_id, topic_id = resolve_course_and_topic(course_selector, week_id, config)
    
    dq_prompt = get_week_prompt(course_selector, week_id, config)
    print(f"\nWeek {week_id} prompt:\n{dq_prompt}\n")
    
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)
        canvas.navigate_to_discussion(course_id, topic_id)
        
        canvas.run_discussion_loop(week_id, openai_api_key, course_selector)
        
        canvas.page.locator('button[type="button"][tabindex="0"].css-jbies6-view--inlineBlock-baseButton').click()
        time.sleep(2)
        canvas.run_discussion_loop(week_id, openai_api_key, course_selector)


def main():
    """Main entry point"""
    username = os.getenv('CANVAS_USERNAME')
    password = os.getenv('CANVAS_PASSWORD')
    course_selector = 'A'
    
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")
    
    scrape(email=username, password=password, course_selector=course_selector)


if __name__ == "__main__":
    main()