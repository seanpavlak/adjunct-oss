"""
Canvas Service for browser automation and Canvas LMS operations
"""

import re
import time
from typing import Any, List, Optional, Tuple

from playwright.sync_api import sync_playwright

from config import canvas_config
from response_generator import ResponseGenerator
from submission_evaluator import detect_late_submission, parse_discussion_submission
from submission_models import DiscussionSubmission, SubmissionEvaluation

STUDENT_INDEX_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")
# First number in rubric-total label (e.g. "91", "91 / 100", "91 out of 100")
RUBRIC_TOTAL_POINTS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")


def parse_student_index(text: str) -> Optional[Tuple[int, int]]:
    """Parse '3/10' or '3/10 Students' from Speed Grader progress text."""
    if not text:
        return None
    match = STUDENT_INDEX_PATTERN.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_rubric_total_points(text: str) -> Optional[str]:
    """Extract the numeric rubric sum from Canvas rubric-total element text."""
    if not text:
        return None
    match = RUBRIC_TOTAL_POINTS_PATTERN.search(text.strip())
    if not match:
        return None
    value = match.group(1)
    if value.endswith(".0"):
        return str(int(float(value)))
    return value


class CanvasService:
    """Service class for Canvas LMS operations"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self, email: str, password: str) -> None:
        """Login to Canvas with provided credentials"""
        self.page.goto("https://chcp.instructure.com/login/canvas")
        self.page.wait_for_selector("input#pseudonym_session_unique_id", state="attached")
        self.page.fill("input#pseudonym_session_unique_id", email)
        self.page.fill('input[name="pseudonym_session[password]"]', password)
        self.page.press('input[name="pseudonym_session[password]"]', "Enter")
        time.sleep(3)  # Wait for login to complete

    def extract_content(self, author) -> str:
        """Extract content from a discussion author element"""
        content = ""
        content_containers = author.query_selector_all("span.user_content.enhanced")
        for container in content_containers:
            paragraphs = container.query_selector_all("p")
            for p in paragraphs:
                content += p.text_content().strip() + " "
        return content if content else "Content not found or not loaded."

    def _extract_first_name(self, full_name: str) -> str:
        """Extract first name from 'Last Name, First Name' format"""
        if not full_name or not full_name.strip():
            return ""
        
        # Split by comma and get the second part (first name)
        parts = full_name.strip().split(',')
        if len(parts) >= 2:
            # Get the second part (first name) and strip whitespace
            first_name = parts[1].strip()
            return first_name
        else:
            # If no comma found, assume it's already just the first name
            return full_name.strip()

    def _is_browser_alive(self) -> bool:
        """Check if the browser/page is still accessible"""
        try:
            # Try to access a simple property to test if browser is alive
            self.page.url
            return True
        except Exception:
            return False

    def process_discussion_authors(
        self, authors: List, week_id: int, llm_config: dict, course_selector: str = "A"
    ) -> bool:
        """Process discussion authors and generate responses

        Returns:
            bool: True if processing completed successfully, False if browser was closed
        """
        generator = ResponseGenerator(
            week=week_id,
            course_selector=course_selector,
            provider=llm_config["provider"],
            openai_key=llm_config.get("openai_key", ""),
            anthropic_key=llm_config.get("anthropic_key", ""),
            deepseek_key=llm_config.get("deepseek_key", ""),
        )

        for author in authors:
            try:
                author_id = author.get_attribute("data-authorid")
                full_name = author.query_selector('[data-testid="author_name"]').text_content()
                content = self.extract_content(author)

                # Extract first name from "Last Name, First Name" format
                first_name = self._extract_first_name(full_name)

                print(f"Author ID: {author_id}, Full Name: {full_name}, First Name: {first_name}, Content: {content}")

                reply_button = author.query_selector('[data-testid="threading-toolbar-reply"]')
                if reply_button:
                    reply_button.click()
                    time.sleep(2)

                    # Generate and type response
                    response = generator.reply(content, student_name=first_name)
                    self.page.keyboard.type(response)
                else:
                    print("Reply button not found for this author.")
            except Exception as e:
                if "Target page, context or browser has been closed" in str(e):
                    # Browser was closed, return False to signal this
                    return False
                else:
                    print("Error: ", e)

        return True

    def run_discussion_loop(
        self, week_id: int, llm_config: dict, course_selector: str = "A"
    ) -> None:
        """Run the main discussion processing loop"""
        while True:
            try:
                authors = self.page.query_selector_all("[data-authorid]")
                success = self.process_discussion_authors(
                    authors, week_id, llm_config, course_selector
                )

                # Only show the browser closed message at the natural stopping point
                if not success or not self._is_browser_alive():
                    print("Browser window closed, stopping processing...")
                    return

                stop = input("Press 'y' to stop or any other key to continue: ").lower()
                if stop == "y":
                    break
            except Exception as e:
                if "Target page, context or browser has been closed" in str(e):
                    print("Browser window closed, stopping processing...")
                    return
                else:
                    print(f"Error in discussion loop: {e}")
                    break

    def navigate_to_discussion(self, course_id: str, topic_id: str) -> None:
        """Navigate to a specific discussion topic"""
        discussion_url = (
            f"https://chcp.instructure.com/courses/{course_id}/discussion_topics/{topic_id}"
        )
        self.page.goto(discussion_url)
        time.sleep(2)

    def create_announcement(
        self, course_id: str, title: str, content: str, scheduled_date: str
    ) -> bool:
        """Create a single announcement with the given details"""
        # Navigate to new announcement page
        announcement_url = f"https://chcp.instructure.com/courses/{course_id}/discussion_topics/new?is_announcement=true"
        self.page.goto(announcement_url)
        time.sleep(2)

        try:
            # Fill in the title
            self.page.get_by_test_id("discussion-topic-title").click()
            self.page.get_by_test_id("discussion-topic-title").fill(title)

            # Switch to HTML editor and fill in the content
            self.page.get_by_role("button", name="Switch to the html editor").click()
            self.page.get_by_label("html code editor91", exact=True).click()
            self.page.get_by_label("html code editor91", exact=True).fill(content)

            # Set the scheduled date
            self.page.get_by_test_id("announcement-available-from-date").fill(scheduled_date)
            self.page.get_by_test_id("announcement-available-from-date").press("Enter")

            # Submit the announcement
            self.page.get_by_test_id("announcement-submit-button").click()
            time.sleep(2)

            print(f"✓ Created announcement: '{title}' scheduled for {scheduled_date}")
            return True

        except Exception as e:
            print(f"✗ Failed to create announcement '{title}': {e}")
            return False

    def schedule_announcements(
        self, course_id: str, announcements: List[dict], announcement_dates: dict
    ) -> Tuple[int, int]:
        """Schedule multiple announcements for a course"""
        successful_announcements = 0
        failed_announcements = 0

        for announcement in announcements:
            week = announcement["week"]
            title = announcement["title"]
            content = announcement["content"]
            scheduled_date = announcement_dates.get(week)

            if scheduled_date:
                print(f"\nCreating Week {week} announcement...")
                if self.create_announcement(course_id, title, content, scheduled_date):
                    successful_announcements += 1
                else:
                    failed_announcements += 1
            else:
                print(f"✗ No date calculated for week {week}")
                failed_announcements += 1

        return successful_announcements, failed_announcements

    def navigate_to_speed_grader(self, course_id: str, assignment_id: str) -> None:
        """Navigate to Speed Grader for a discussion assignment"""
        url = (
            f"{canvas_config.BASE_URL}/courses/{course_id}/gradebook/speed_grader"
            f"?assignment_id={assignment_id}"
        )
        self.page.goto(url)
        time.sleep(canvas_config.SPEED_GRADER_WAIT_TIME)
        self._wait_for_speed_grader_ready()

    def _wait_for_speed_grader_ready(self) -> None:
        """Wait for Speed Grader UI (submission preview or no-submission state)."""
        ready_selector = (
            f'[data-testid="{canvas_config.GRADE_INPUT}"], '
            f'[data-testid="{canvas_config.NO_SUBMISSION_IFRAME}"]'
        )
        self.page.locator(ready_selector).first.wait_for(
            state="visible", timeout=canvas_config.DEFAULT_TIMEOUT
        )

    def has_no_submission(self) -> bool:
        """True when the student has no submission in Speed Grader."""
        try:
            return self.page.get_by_test_id(canvas_config.NO_SUBMISSION_IFRAME).is_visible(
                timeout=3000
            )
        except Exception:
            return False

    def skip_no_submission_student(self) -> bool:
        """Click the no-submission view and advance to the next student."""
        try:
            self.page.get_by_test_id(canvas_config.NO_SUBMISSION_IFRAME).click()
            time.sleep(canvas_config.GRADE_INPUT_WAIT)
            return self.advance_to_next_student()
        except Exception as e:
            print(f"Failed to skip no-submission student: {e}")
            return False

    def _submission_preview_frame(self):
        """Frame locator for the Speed Grader submission preview iframe."""
        return self.page.frame_locator(
            f'[data-testid="{canvas_config.SUBMISSION_PREVIEW_IFRAME}"]'
        )

    def _focus_submission_preview(self) -> None:
        """Click submission preview so the iframe content is active"""
        try:
            frame = self._submission_preview_frame()
            frame.locator("body").click(timeout=5000)
            time.sleep(0.5)
        except Exception:
            pass

    def extract_discussion_submission(self) -> DiscussionSubmission:
        """
        Extract initial post and peer replies from the submission preview iframe.

        Reads #content in the iframe (including the initial post body and each
        classmate follow-up), matching the Speed Grader discussion layout.
        """
        frame = self._submission_preview_frame()
        content = frame.locator("#content")
        content.wait_for(state="attached", timeout=canvas_config.DEFAULT_TIMEOUT)

        raw_text = content.inner_text()
        is_late = detect_late_submission(raw_text)

        # Focus initial post region (header area about submissions for this assignment)
        try:
            content.locator("motion.fs-mask p, .discussion-entry-content p, p").first.wait_for(
                state="attached", timeout=5000
            )
        except Exception:
            pass

        submission = parse_discussion_submission(raw_text, is_late=is_late)

        # Fallback: collect paragraph texts directly from iframe if split failed
        if not submission.initial_post:
            paragraphs = [
                t.strip()
                for t in frame.locator("#content p").all_inner_texts()
                if t and len(t.strip()) >= 20
            ]
            if paragraphs:
                submission = parse_discussion_submission(
                    "\n".join(paragraphs), is_late=is_late
                )

        return submission

    def read_rubric_total_points(self) -> Optional[str]:
        """
        Read the summed rubric score from Canvas (data-testid=rubric-total).

        Clicks the total display so Canvas exposes the current rubric sum, then
        parses the visible points value.
        """
        try:
            total_el = self.page.get_by_test_id(canvas_config.RUBRIC_TOTAL)
            total_el.wait_for(state="visible", timeout=5000)
            total_el.click()
            time.sleep(0.3)
            raw = total_el.inner_text()
            points = parse_rubric_total_points(raw)
            if points is not None:
                print(f"  Rubric total from Canvas (rubric-total): {points} (raw: {raw!r})")
            return points
        except Exception as e:
            print(f"  Could not read rubric-total: {e}")
            return None

    def apply_rubric_and_grade(
        self,
        rubric_ratings: List[str],
        grade: str,
        use_rubric: bool = True,
    ) -> bool:
        """Apply rubric selections, read Canvas rubric total, and set grade-input."""
        try:
            self._focus_submission_preview()
            time.sleep(canvas_config.GRADE_INPUT_WAIT)

            grade_to_enter = grade

            if use_rubric and rubric_ratings:
                self.page.get_by_test_id(canvas_config.VIEW_RUBRIC_BUTTON).click()
                time.sleep(canvas_config.RUBRIC_PANEL_OPEN_WAIT)
                for i, rating_id in enumerate(rubric_ratings, start=1):
                    print(f"  Applying rubric rating {i}/{len(rubric_ratings)}: {rating_id}")
                    self.page.get_by_test_id(rating_id).click()
                    time.sleep(canvas_config.RUBRIC_RATING_CLICK_WAIT)
                save_btn = self.page.get_by_test_id(canvas_config.SAVE_RUBRIC_BUTTON)
                save_btn.click()
                time.sleep(canvas_config.RUBRIC_SAVE_WAIT)

                rubric_total = self.read_rubric_total_points()
                if rubric_total is not None:
                    grade_to_enter = rubric_total
                else:
                    print(
                        f"  Falling back to calculated grade {grade} "
                        "(rubric-total not readable)"
                    )

            grade_input = self.page.get_by_test_id(canvas_config.GRADE_INPUT)
            grade_input.click()
            time.sleep(0.5)
            grade_input.fill(grade_to_enter)
            time.sleep(0.5)
            grade_input.press("Enter")
            time.sleep(canvas_config.AFTER_GRADE_SAVE_WAIT)
            return True
        except Exception as e:
            print(f"Failed to grade submission: {e}")
            return False

    def get_student_index_counts(self) -> Optional[Tuple[int, int]]:
        """Read current/total student counts from the Speed Grader progress indicator."""
        try:
            index_el = self.page.get_by_test_id(canvas_config.CURRENT_STUDENT_INDEX)
            index_el.wait_for(state="visible", timeout=5000)
            index_el.click()
            time.sleep(1)
            return parse_student_index(index_el.inner_text())
        except Exception:
            return None

    def is_speed_grader_complete(
        self, counts: Optional[Tuple[int, int]] = None
    ) -> bool:
        """True when progress shows X/X (e.g. last student on the final submission)."""
        if counts is None:
            counts = self.get_student_index_counts()
        if counts is None:
            return False
        current, total = counts
        return total > 0 and current >= total

    def has_next_student(self, counts: Optional[Tuple[int, int]] = None) -> bool:
        """Check if Speed Grader can advance to another student"""
        if self.is_speed_grader_complete(counts):
            return False
        try:
            button = self.page.get_by_test_id(canvas_config.NEXT_STUDENT_BUTTON)
            return button.is_visible() and button.is_enabled()
        except Exception:
            return False

    def advance_to_next_student(self) -> bool:
        """Move to the next student in Speed Grader"""
        try:
            self.page.get_by_test_id(canvas_config.NEXT_STUDENT_BUTTON).click()
            time.sleep(canvas_config.SPEED_GRADER_WAIT_TIME)
            self._wait_for_speed_grader_ready()
            return True
        except Exception as e:
            print(f"Failed to advance to next student: {e}")
            return False

    def run_speed_grader_loop(
        self,
        rubric_ratings: List[str],
        grade: str,
        use_rubric: bool = True,
        max_students: Optional[int] = None,
        dry_run: bool = False,
        grading_requirements: Optional[dict] = None,
        rubric_rating_levels: Optional[dict] = None,
        llm_grader: Optional[Any] = None,
        discussion_prompt: str = "",
    ) -> Tuple[int, int]:
        """Grade each student submission in Speed Grader"""
        from submission_evaluator import evaluate_submission
        from submission_models import grading_requirements_from_config

        requirements = grading_requirements or grading_requirements_from_config({})
        if llm_grader:
            print("  Using LLM rubric grading (lenient)")
        if dry_run:
            print("\n*** DRY RUN — current student on screen only; nothing saved to Canvas ***\n")

        graded_count = 0
        failed_count = 0
        skipped_count = 0
        student_index = 0
        counts = None

        while True:
            if not self._is_browser_alive():
                print("Browser window closed, stopping speed grader...")
                break

            if not dry_run:
                student_index += 1
                if max_students is not None and student_index > max_students:
                    print(f"Reached max students limit ({max_students}).")
                    break

            counts = self.get_student_index_counts()
            if counts:
                current, total = counts
                print(f"\nStudent on screen: {current}/{total}")
            elif not dry_run:
                print(f"\nProcessing student {student_index}...")

            if self.has_no_submission():
                print("  No submission — skipping to next student")
                skipped_count += 1
                if dry_run:
                    print("\n*** DRY RUN complete (no submission on screen) ***\n")
                    break
                if self.is_speed_grader_complete(counts):
                    print("Speed Grader complete.")
                    break
                if not self.has_next_student(counts):
                    print("No more students in Speed Grader.")
                    break
                if not self.skip_no_submission_student():
                    break
                continue

            submission = self.extract_discussion_submission()

            if dry_run and submission.raw_text:
                print("\n--- Raw text from submission preview iframe ---")
                print(submission.raw_text)
                print("--- End raw iframe text ---\n")

            print("  Parsed submission:")
            print(f"    Initial post ({len(submission.initial_post)} chars):")
            print(submission.initial_post or "(empty)")
            for i, reply in enumerate(submission.peer_replies, start=1):
                print(f"    Peer reply {i} ({len(reply)} chars):")
                print(reply)

            evaluation: SubmissionEvaluation = evaluate_submission(
                submission,
                requirements,
                rubric_rating_levels=rubric_rating_levels,
                discussion_prompt=discussion_prompt,
                llm_grader=llm_grader,
                dry_run=dry_run,
            )
            for line in evaluation.summary_lines():
                print(line)

            if dry_run:
                print("\n*** DRY RUN complete — no grades or rubric saved ***\n")
                break

            student_rubric = evaluation.rubric_ratings or rubric_ratings
            student_grade = evaluation.grade
            if self.apply_rubric_and_grade(student_rubric, student_grade, use_rubric):
                graded_count += 1
                print(f"✓ Graded student {student_index} with {student_grade} points")
            else:
                failed_count += 1
                print(f"✗ Failed to grade student {student_index}")

            if self.is_speed_grader_complete(counts):
                done_counts = counts or self.get_student_index_counts()
                if done_counts:
                    current, total = done_counts
                    print(f"Speed Grader complete: {current}/{total} students.")
                else:
                    print("Speed Grader complete.")
                break

            if not self.has_next_student(counts):
                print("No more students in Speed Grader.")
                break

            if not self.advance_to_next_student():
                break

        if skipped_count:
            print(f"\nSkipped {skipped_count} student(s) with no submission.")
        return graded_count, failed_count
