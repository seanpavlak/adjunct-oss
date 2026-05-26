"""
Canvas discussion plagiarism check — scrape posts and compare all students.
"""

import os
import time

from dotenv import load_dotenv

from chcp.canvas.service import CanvasService
from chcp.core.course_utils import (
    calculate_current_week,
    get_week_prompt,
    load_courses_config,
    resolve_course_and_topic,
)
from chcp.plagiarism.checker import (
    DEFAULT_MIN_MATCHING_FRACTION,
    DEFAULT_MIN_WORDS,
    DEFAULT_SIMILARITY_THRESHOLD,
    find_plagiarism_pairs,
    format_match_report,
)

load_dotenv()


def run_plagiarism_action(
    email: str = None,
    password: str = None,
    course_selector: str = None,
    week_id: int = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_words: int = DEFAULT_MIN_WORDS,
    min_matching_fraction: float = DEFAULT_MIN_MATCHING_FRACTION,
) -> None:
    """Log in, scrape discussion posts, and print suspected plagiarism pairs."""
    if not email or not password:
        print("Email and password must be provided")
        return
    if not course_selector:
        print("Course selector (course key or course_id) must be provided")
        return

    config = load_courses_config()
    courses = config.get("courses", {})
    if course_selector in courses:
        course = courses[course_selector]
    else:
        course = next(
            (c for c in courses.values() if c.get("course_id") == str(course_selector)),
            None,
        )

    if not course:
        raise ValueError(f"Course '{course_selector}' not found in courses.json")

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

    course_id, topic_id = resolve_course_and_topic(course_selector, week_id, config)
    dq_prompt = get_week_prompt(course_selector, week_id, config)
    print(f"\nWeek {week_id} prompt (stripped from comparisons when possible):\n{dq_prompt}\n")

    print(
        "Plagiarism settings (lenient — high bar to flag):\n"
        f"  Similarity threshold: {similarity_threshold:.0%}\n"
        f"  Minimum words per post: {min_words}\n"
        f"  Minimum matching text fraction: {min_matching_fraction:.0%}\n"
    )

    with CanvasService(headless=False) as canvas:
        canvas.login(email, password)
        canvas.navigate_to_discussion(course_id, topic_id)
        canvas.expand_discussion_if_needed()

        posts = canvas.scrape_discussion_posts()
        print(f"\nScraped {len(posts)} student post(s) from discussion.\n")

        if len(posts) < 2:
            print("Need at least two student posts to compare. Nothing to report.")
            return

        matches = find_plagiarism_pairs(
            posts,
            prompt=dq_prompt,
            similarity_threshold=similarity_threshold,
            min_words=min_words,
            min_matching_fraction=min_matching_fraction,
        )

        if not matches:
            print(
                "No plagiarism pairs exceeded the threshold. "
                "(Lenient settings — only near-duplicate posts are flagged.)"
            )
            return

        print(f"\n*** {len(matches)} PAIR(S) ABOVE THRESHOLD — REVIEW BEFORE ACCUSING ***\n")
        for match in matches:
            print(format_match_report(match))

        print(
            "\nReview the previews above manually before contacting students. "
            "Shared topic language alone should not appear here."
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare discussion posts for plagiarism (many-to-many)",
        epilog="💡 Find this helpful? https://buymeacoffee.com/seanpavlak",
    )
    parser.add_argument("--course", default="A", help="Course selector (default: A)")
    parser.add_argument(
        "--week",
        type=int,
        help="Week ID override (default: current calendar week from course start)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Similarity ratio to flag (default: {DEFAULT_SIMILARITY_THRESHOLD})",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=DEFAULT_MIN_WORDS,
        help=f"Minimum words per post to include (default: {DEFAULT_MIN_WORDS})",
    )
    args = parser.parse_args()

    username = os.getenv("CANVAS_USERNAME")
    password = os.getenv("CANVAS_PASSWORD")
    if not username or not password:
        raise ValueError("CANVAS_USERNAME and CANVAS_PASSWORD environment variables must be set")

    run_plagiarism_action(
        email=username,
        password=password,
        course_selector=args.course,
        week_id=args.week,
        similarity_threshold=args.threshold,
        min_words=args.min_words,
    )


if __name__ == "__main__":
    main()
