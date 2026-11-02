"""Soft-drop courses and add a course from a Canvas course id."""

from __future__ import annotations

from typing import Optional

from chcp.canvas.service import CanvasService
from chcp.canvas.term_api import fetch_favorites, fetch_term_payload
from chcp.core.course_utils import (
    load_announcements_config,
    load_courses_config,
    save_announcements_config,
    save_courses_config,
)
from chcp.core.schemas import validate_announcements_config, validate_courses_config
from chcp.core.term_setup import (
    TermSetupError,
    apply_import,
    format_favorites,
    format_import_preview,
    mark_courses_inactive,
    normalize_course_id,
    prepare_import,
)


def confirm(message: str) -> bool:
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_term_drop(
    keys: list[str],
    *,
    confirmed: bool = False,
    config_path: Optional[str] = None,
) -> None:
    """Hide courses from menus and ALL. The JSON entries stay."""
    if not keys:
        print("No courses to drop.")
        return
    config = load_courses_config(config_path)
    courses = config.get("courses") or {}
    missing = [key for key in keys if key not in courses]
    if missing:
        print("Not in courses.json: " + ", ".join(missing))
        return
    pending = [key for key in keys if courses[key].get("active") is not False]
    if not pending:
        print("Those courses are already hidden.")
        return
    names = [f"{key} ({courses[key].get('name', 'unknown')})" for key in pending]
    print("Soft-drop: " + ", ".join(names))
    print("They stay in courses.json and disappear from the menu and ALL.")
    if not confirmed and not confirm("Soft-drop these courses"):
        print("Cancelled.")
        return
    changed = mark_courses_inactive(config, pending)
    save_courses_config(config, config_path)
    print("Hidden: " + ", ".join(changed))


def run_term_add(
    email: str,
    password: str,
    *,
    course_id: Optional[str] = None,
    dry_run: bool = False,
    otp_provider=None,
    courses_path: Optional[str] = None,
    announcements_path: Optional[str] = None,
) -> None:
    """Log in once, then import one or more course ids after a preview."""
    if not email or not password:
        print("Email and password must be provided")
        return
    courses_config = load_courses_config(courses_path)
    announcements_config = load_announcements_config(announcements_path)
    with CanvasService(headless=False) as canvas:
        canvas.login(email, password, otp_provider=otp_provider)
        request = canvas.context.request
        try:
            favorites = fetch_favorites(request)
            print(format_favorites(favorites, courses_config))
        except TermSetupError as exc:
            print(f"Could not list favorite courses: {exc}")
        print()
        _import_loop(
            request,
            courses_config,
            announcements_config,
            course_id=course_id,
            dry_run=dry_run,
            courses_path=courses_path,
            announcements_path=announcements_path,
        )


def _import_loop(
    request,
    courses_config: dict,
    announcements_config: dict,
    *,
    course_id: Optional[str],
    dry_run: bool,
    courses_path: Optional[str],
    announcements_path: Optional[str],
) -> None:
    pending = course_id
    while True:
        if pending:
            raw_id = pending
            pending = None
        else:
            raw_id = input("Canvas course id (blank to finish): ").strip()
            if not raw_id:
                break
        try:
            normalized = normalize_course_id(raw_id)
            payload = fetch_term_payload(request, normalized)
            plan = prepare_import(
                courses_config,
                announcements_config,
                payload["course"],
                payload["modules"],
                payload["discussions"],
            )
        except TermSetupError as exc:
            print(exc)
            if dry_run or not confirm("Try another course id"):
                return
            continue
        print(format_import_preview(plan))
        print()
        if dry_run:
            print("Dry run. Nothing was written.")
            return
        if confirm(f"Write course {plan.key} to courses.json"):
            apply_import(courses_config, announcements_config, plan)
            validate_courses_config(courses_config)
            if plan.announcements is not None:
                validate_announcements_config(announcements_config)
            save_courses_config(courses_config, courses_path)
            if plan.announcements is not None:
                save_announcements_config(announcements_config, announcements_path)
                print(f"Added course {plan.key} and copied its announcements.")
            else:
                print(f"Added course {plan.key}. Announcements were not copied.")
        if not confirm("Add another course id"):
            break
