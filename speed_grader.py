"""
Canvas Speed Grader - Auto-grade discussion post submissions
"""

import argparse
import os

from dotenv import load_dotenv

from canvas_service import CanvasService
from course_utils import (
    calculate_current_week,
    calculate_grading_week,
    get_speed_grader_config,
    get_week_prompt,
    load_courses_config,
    resolve_course,
    resolve_course_and_assignment,
)

load_dotenv()


def run_speed_grader_action(
    email: str = None,
    password: str = None,
    course_selector: str = None,
    week_id: int = None,
    grade_override: str = None,
    max_students: int = None,
    dry_run: bool = False,
    llm_provider: str = None,
) -> None:
    """Log in to Canvas and auto-grade discussion submissions in Speed Grader"""
    if not email or not password:
        print("Email and password must be provided")
        return
    if not course_selector:
        print("Course selector must be provided")
        return

    config = load_courses_config()
    course = resolve_course(course_selector, config)
    course_start_date = course.get("course_start_date")
    if not course_start_date:
        raise ValueError(f"Course start date not found for course {course_selector}")

    course_id = course.get("course_id")

    if week_id is None:
        calendar_week = calculate_current_week(course_start_date)
        week_id = calculate_grading_week(course_start_date)
        print(
            f"Auto-selected grading week: {week_id} "
            f"(calendar week {calendar_week} minus 1, start {course_start_date})"
        )
    else:
        print(f"Using manually specified week: {week_id}")

    course_id, assignment_id = resolve_course_and_assignment(
        course_selector, week_id, config
    )
    speed_grader_config = get_speed_grader_config(course_selector, week_id, config)

    grade = grade_override or speed_grader_config.get("grade", "100")
    rubric_ratings = speed_grader_config.get("rubric_ratings", [])
    use_rubric = speed_grader_config.get("use_rubric", True)

    rubric_name = speed_grader_config.get("rubric_name", "Discussion Rubric (2021)")
    rubric_criteria = speed_grader_config.get("rubric_criteria", [])

    print(f"\nSpeed Grader setup:")
    print(f"  Course ID: {course_id}")
    print(f"  Week: {week_id}")
    print(f"  Assignment ID: {assignment_id}")
    print(f"  Rubric: {rubric_name}")
    print(f"  Grade: {grade}")
    if rubric_criteria:
        print("  Criteria (auto-selected ratings):")
        for criterion in rubric_criteria:
            print(
                f"    - {criterion['name']} ({criterion['max_points']} pts): "
                f"{criterion['rating']}"
            )
    grading_requirements = speed_grader_config.get("grading_requirements", {})
    rubric_rating_levels = speed_grader_config.get("rubric_rating_levels")

    print(f"  Rubric button clicks (full credit): {len(rubric_ratings)}")
    print("  Verification (grading/analysis checklist):")
    print(f"    - Min peer replies: {grading_requirements.get('min_peer_replies', 2)}")
    print(f"    - Min substantive peer replies: {grading_requirements.get('min_peer_replies', 2)}")
    print(f"    - Comprehension richness signals: {grading_requirements.get('min_comprehension_richness_signals', 3)}")
    print(f"    - On time required: {grading_requirements.get('require_on_time', True)}")
    print(f"    - Min citations: {grading_requirements.get('min_citations', 1)}")
    if dry_run:
        print("  Mode: dry-run (logs full LLM I/O for student on screen; no saves)")

    discussion_prompt = get_week_prompt(course_selector, week_id, config)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")

    if llm_provider is None:
        from discussions import _detect_llm_provider

        llm_provider = _detect_llm_provider(openai_key, anthropic_key, deepseek_key)

    from rubric_grader import RubricGrader

    llm_grader = RubricGrader(
        provider=llm_provider,
        openai_key=openai_key,
        anthropic_key=anthropic_key,
        deepseek_key=deepseek_key,
        lenient=grading_requirements.get("lenient", True),
        rubric_criteria=rubric_criteria,
        grading_defaults=speed_grader_config.get("grading_defaults"),
        rubric_name=speed_grader_config.get("rubric_name"),
        rubric_grading_config=speed_grader_config.get("rubric_grading_config"),
    )
    print(f"  LLM provider: {llm_provider} (lenient rubric grading)")

    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)
        canvas.navigate_to_speed_grader(course_id, assignment_id)

        graded, failed = canvas.run_speed_grader_loop(
            rubric_ratings=rubric_ratings,
            grade=grade,
            use_rubric=use_rubric,
            max_students=max_students,
            dry_run=dry_run,
            grading_requirements=grading_requirements,
            rubric_rating_levels=rubric_rating_levels,
            llm_grader=llm_grader,
            discussion_prompt=discussion_prompt,
        )

    print(f"\nSpeed Grader complete: {graded} graded, {failed} failed")


def main():
    """CLI entry point for speed grader"""
    parser = argparse.ArgumentParser(
        description="Canvas Speed Grader - Auto-grade discussion submissions",
        epilog="💡 Find this helpful? https://buymeacoffee.com/seanpavlak",
    )
    parser.add_argument("--course", default="A", help="Course selector (default: A)")
    parser.add_argument(
        "--week",
        type=int,
        help="Week ID (default: calendar week minus 1)",
    )
    parser.add_argument("--grade", help="Override grade points from courses.json")
    parser.add_argument(
        "--max-students",
        type=int,
        help="Maximum number of students to grade (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log full LLM prompt/response for the student on screen; no Canvas saves",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "deepseek"],
        help="LLM provider for rubric grading (auto-detected if not specified)",
    )
    args = parser.parse_args()

    username = os.getenv("CANVAS_USERNAME")
    password = os.getenv("CANVAS_PASSWORD")

    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")

    run_speed_grader_action(
        email=username,
        password=password,
        course_selector=args.course,
        week_id=args.week,
        grade_override=args.grade,
        max_students=args.max_students,
        dry_run=args.dry_run,
        llm_provider=args.provider,
    )


if __name__ == "__main__":
    main()
