"""
Canvas Discussion Handler - Manages discussion scraping and response generation
"""

import os
import time
from dotenv import load_dotenv
from course_utils import (
    load_courses_config, 
    calculate_current_week, 
    resolve_course_and_topic, 
    get_week_prompt
)
from canvas_service import CanvasService

# Load environment variables
load_dotenv()


def _detect_llm_provider(openai_key: str, anthropic_key: str, deepseek_key: str) -> str:
    """Auto-detect which LLM provider to use based on available API keys"""
    available_providers = []
    
    if openai_key:
        available_providers.append(('openai', 'OpenAI'))
    if anthropic_key:
        available_providers.append(('anthropic', 'Anthropic'))
    if deepseek_key:
        available_providers.append(('deepseek', 'DeepSeek'))
    
    if not available_providers:
        raise ValueError(
            "No LLM API keys found. Please set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY"
        )
    
    if len(available_providers) > 1:
        provider_names = [name for _, name in available_providers]
        print(f"Multiple LLM providers available: {', '.join(provider_names)}")
        print(f"Using {available_providers[0][1]} (first available). Use llm_provider parameter to specify a different one.")
    
    return available_providers[0][0]


def run_discussion_action(email: str = None, password: str = None, course_selector: str = None, week_id: int = None, llm_provider: str = None) -> None:
    """Main function to run discussion scraping and response generation"""
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
    
    # Get and validate API keys
    openai_key = os.getenv('OPENAI_API_KEY', '')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY', '')
    
    # Auto-detect provider if not specified
    if llm_provider is None:
        llm_provider = _detect_llm_provider(openai_key, anthropic_key, deepseek_key)
    
    # Validate that the selected provider has the required API key
    if llm_provider == 'openai' and not openai_key:
        raise ValueError("OPENAI_API_KEY environment variable is required when using OpenAI provider")
    elif llm_provider == 'anthropic' and not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required when using Anthropic provider")
    elif llm_provider == 'deepseek' and not deepseek_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is required when using DeepSeek provider")
    
    print(f"Using LLM provider: {llm_provider}")
    
    # Prepare LLM configuration
    llm_config = {
        'provider': llm_provider,
        'openai_key': openai_key,
        'anthropic_key': anthropic_key,
        'deepseek_key': deepseek_key
    }
    
    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)
        canvas.navigate_to_discussion(course_id, topic_id)
        
        canvas.run_discussion_loop(week_id, llm_config, course_selector)
        
        canvas.page.locator('button[type="button"][tabindex="0"].css-jbies6-view--inlineBlock-baseButton').click()
        time.sleep(2)
        canvas.run_discussion_loop(week_id, llm_config, course_selector)


def main():
    """Main entry point for discussion action"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Canvas Discussion Handler',
        epilog='💡 Find this helpful? https://buymeacoffee.com/seanpavlak'
    )
    parser.add_argument('--provider', choices=['openai', 'anthropic', 'deepseek'], 
                       help='LLM provider to use (auto-detected if not specified)')
    parser.add_argument('--course', default='A', 
                       help='Course selector (default: A)')
    parser.add_argument('--week', type=int, 
                       help='Week ID (auto-calculated if not specified)')
    
    args = parser.parse_args()
    
    username = os.getenv('CANVAS_USERNAME')
    password = os.getenv('CANVAS_PASSWORD')
    
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")
    
    run_discussion_action(
        email=username, 
        password=password, 
        course_selector=args.course,
        week_id=args.week,
        llm_provider=args.provider
    )


if __name__ == "__main__":
    main()

