"""
Canvas Discussion Handler - Manages discussion scraping and response generation
"""

import os
import time

from dotenv import load_dotenv

from chcp.canvas.service import CanvasService
from chcp.canvas.session import discard_session_file, establish_canvas_session
from chcp.core.course_binding import (
    CourseIsolationError,
    assert_worker_course,
    bind_course,
    is_all_courses,
    resolve_window_slot,
)
from chcp.core.course_utils import calculate_current_week, load_courses_config, resolve_course
from chcp.core.parallel_courses import install_parallel_log_prefix, run_courses_in_parallel
from chcp.core.pause_control import get_pause_controller

# Load environment variables
load_dotenv()


def _detect_llm_provider(openai_key: str, anthropic_key: str, deepseek_key: str) -> str:
    """Auto-detect which LLM provider to use based on available API keys"""
    available_providers = []

    if openai_key:
        available_providers.append(("openai", "OpenAI"))
    if anthropic_key:
        available_providers.append(("anthropic", "Anthropic"))
    if deepseek_key:
        available_providers.append(("deepseek", "DeepSeek"))

    if not available_providers:
        raise ValueError(
            "No LLM API keys found. Please set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY"
        )

    if len(available_providers) > 1:
        provider_names = [name for _, name in available_providers]
        print(f"Multiple LLM providers available: {', '.join(provider_names)}")
        print(
            f"Using {available_providers[0][1]} (first available). "
            f"Use llm_provider parameter to specify a different one."
        )

    return available_providers[0][0]


def run_discussion_action(
    email: str = None,
    password: str = None,
    course_selector: str = None,
    week_id: int = None,
    llm_provider: str = None,
    otp_provider=None,
    window_slot: int = None,
) -> None:
    """Main function to run discussion scraping and response generation"""
    install_parallel_log_prefix()
    if is_all_courses(course_selector):
        if os.environ.get("CHCP_PARALLEL") == "1":
            raise CourseIsolationError(
                "A course worker cannot fan out to ALL. "
                "ALL is only allowed in the parent process."
            )
        if not email or not password:
            print("Email and password must be provided")
            return
        print(
            "Signing in once. Canvas accepts the MFA code a single time, "
            "and each course window reuses that session."
        )
        session_path = establish_canvas_session(email, password, otp_provider)
        try:
            run_courses_in_parallel(
                "discussion",
                week=week_id,
                provider=llm_provider,
                storage_state_path=session_path,
            )
        finally:
            discard_session_file(session_path)
        return
    if not email or not password:
        print("Email and password must be provided")
        return
    if not course_selector:
        print("Course selector (course key or course_id) must be provided")
        return

    assert_worker_course(course_selector)
    window_slot = resolve_window_slot(window_slot)
    config = load_courses_config()
    course = resolve_course(course_selector, config)

    if week_id is None:
        course_start_date = course.get("course_start_date")
        if not course_start_date:
            raise ValueError(f"Course start date not found for course {course_selector}")
        week_id = calculate_current_week(course_start_date)
        print(
            f"Auto-calculated current week: {week_id} "
            f"(based on course start date: {course_start_date})"
        )
    else:
        print(f"Using manually specified week: {week_id}")

    binding = bind_course(course_selector, week_id, config)
    course_id = binding.course_id
    topic_id = binding.topic_id
    if not topic_id:
        raise ValueError(f"Missing topic_id for week {week_id} in course {binding.course_key}")
    print(
        f"\nCourse {binding.course_key} ({binding.course_name}) "
        f"id={binding.course_id} week={binding.week_id}"
    )
    print(f"Week {week_id} prompt:\n{binding.discussion_prompt}\n")

    # Get and validate API keys
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")

    # Auto-detect provider if not specified
    if llm_provider is None:
        llm_provider = _detect_llm_provider(openai_key, anthropic_key, deepseek_key)

    # Validate that the selected provider has the required API key
    if llm_provider == "openai" and not openai_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required when using OpenAI provider"
        )
    elif llm_provider == "anthropic" and not anthropic_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required when using Anthropic provider"
        )
    elif llm_provider == "deepseek" and not deepseek_key:
        raise ValueError(
            "DEEPSEEK_API_KEY environment variable is required when using DeepSeek provider"
        )

    print(f"Using LLM provider: {llm_provider}")

    # Prepare LLM configuration
    llm_config = {
        "provider": llm_provider,
        "openai_key": openai_key,
        "anthropic_key": anthropic_key,
        "deepseek_key": deepseek_key,
    }

    parallel = os.environ.get("CHCP_PARALLEL") == "1"
    storage_state_path = os.environ.get("CHCP_STORAGE_STATE") or None
    pause = get_pause_controller()
    if not parallel:
        pause.enable()
    try:
        with CanvasService(
            headless=False,
            window_slot=window_slot,
            course_label=binding.course_key,
            storage_state_path=storage_state_path,
        ) as canvas:
            canvas.bound_course_id = binding.course_id
            canvas.course_binding = binding
            canvas.ensure_logged_in(email, password, otp_provider=otp_provider)
            canvas.navigate_to_discussion(course_id, topic_id)
            # Collapse nested peer replies so we only reply to top-level posts.
            canvas.collapse_discussion_if_needed()
            canvas.run_discussion_loop(
                week_id,
                llm_config,
                binding.course_key,
                interactive=not parallel,
            )
    finally:
        if not parallel:
            pause.disable()


def main():
    """Main entry point for discussion action"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Canvas Discussion Handler",
        epilog="💡 Find this helpful? https://buymeacoffee.com/seanpavlak",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "deepseek"],
        help="LLM provider to use (auto-detected if not specified)",
    )
    parser.add_argument(
        "--course",
        default="A",
        help="Course key, Canvas course id, or ALL (default: A)",
    )
    parser.add_argument("--week", type=int, help="Week ID (auto-calculated if not specified)")
    parser.add_argument(
        "--window-slot",
        type=int,
        help="Chromium window slot when running one course of an ALL batch",
    )

    args = parser.parse_args()

    from chcp.core.credentials import resolve_canvas_credentials

    creds = resolve_canvas_credentials()
    run_discussion_action(
        email=creds.username,
        password=creds.password,
        course_selector=args.course,
        week_id=args.week,
        llm_provider=args.provider,
        otp_provider=creds.get_otp if creds.has_otp_provider else None,
        window_slot=args.window_slot,
    )


if __name__ == "__main__":
    main()
