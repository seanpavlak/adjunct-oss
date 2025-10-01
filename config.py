"""
Configuration constants for Canvas CLI
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class CanvasConfig:
    """Canvas LMS configuration constants"""

    BASE_URL: Final[str] = "https://chcp.instructure.com"
    LOGIN_URL: Final[str] = f"{BASE_URL}/login/canvas"

    # Timeouts in milliseconds
    DEFAULT_TIMEOUT: Final[int] = 30000
    PAGE_LOAD_TIMEOUT: Final[int] = 30000

    # Wait times in seconds
    LOGIN_WAIT_TIME: Final[int] = 3
    NAVIGATION_WAIT_TIME: Final[int] = 2
    REPLY_CLICK_WAIT_TIME: Final[int] = 2

    # Selectors
    USERNAME_SELECTOR: Final[str] = "input#pseudonym_session_unique_id"
    PASSWORD_SELECTOR: Final[str] = 'input[name="pseudonym_session[password]"]'
    AUTHOR_SELECTOR: Final[str] = "[data-authorid]"
    AUTHOR_NAME_SELECTOR: Final[str] = '[data-testid="author_name"]'
    REPLY_BUTTON_SELECTOR: Final[str] = '[data-testid="threading-toolbar-reply"]'
    CONTENT_SELECTOR: Final[str] = "span.user_content.enhanced"

    # Announcement selectors
    ANNOUNCEMENT_TITLE_SELECTOR: Final[str] = "discussion-topic-title"
    ANNOUNCEMENT_HTML_EDITOR_BUTTON: Final[str] = "Switch to the html editor"
    ANNOUNCEMENT_CONTENT_SELECTOR: Final[str] = "html code editor91"
    ANNOUNCEMENT_DATE_SELECTOR: Final[str] = "announcement-available-from-date"
    ANNOUNCEMENT_SUBMIT_SELECTOR: Final[str] = "announcement-submit-button"


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration constants"""

    # Model names
    OPENAI_MODEL: Final[str] = "gpt-4o"
    ANTHROPIC_MODEL: Final[str] = "claude-3-5-sonnet-20241022"
    DEEPSEEK_MODEL: Final[str] = "deepseek-chat"
    DEEPSEEK_BASE_URL: Final[str] = "https://api.deepseek.com/v1"

    # Generation parameters
    TEMPERATURE: Final[float] = 0.8
    MAX_RESPONSE_WORDS: Final[int] = 80
    FEW_SHOT_K: Final[int] = 3
    FOLLOW_UP_QUESTION_PROBABILITY: Final[float] = 0.05
    PHRASE_SELECTION_PROBABILITY: Final[float] = 0.3


@dataclass(frozen=True)
class CourseConfig:
    """Course configuration constants"""

    MIN_WEEK: Final[int] = 1
    MAX_WEEK: Final[int] = 8
    DATE_FORMAT: Final[str] = "%Y-%m-%d"
    ANNOUNCEMENT_DATE_FORMAT: Final[str] = "%B %d %Y"


# Create singleton instances
canvas_config = CanvasConfig()
llm_config = LLMConfig()
course_config = CourseConfig()
