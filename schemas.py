"""
Pydantic schemas for configuration validation
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DiscussionData(BaseModel):
    """Schema for discussion post and response examples"""

    post: str = Field(..., min_length=1)
    response: str = Field(..., min_length=1)


class RubricCriterionSchema(BaseModel):
    """One criterion from the Discussion Rubric (2021)"""

    name: str = Field(..., min_length=1)
    max_points: int = Field(..., ge=0)
    rating: str = Field(..., min_length=1, description="Rating level selected for auto-grading")
    description: Optional[str] = Field(default=None)


class GradingRequirementsSchema(BaseModel):
    """Verification rules applied before selecting rubric ratings"""

    min_peer_replies: int = Field(default=2, ge=0)
    require_on_time: bool = Field(default=True)
    min_citations: int = Field(default=1, ge=0)
    require_citation: bool = Field(default=True)
    min_initial_post_chars: int = Field(default=100, ge=0)
    min_peer_reply_chars: int = Field(default=40, ge=0)


class DiscussionRubricSchema(BaseModel):
    """Course-level discussion rubric shared by all weekly discussion assignments"""

    name: str = Field(default="Discussion Rubric (2021)")
    grade: str = Field(default="100")
    use_rubric: bool = Field(default=True)
    criteria: List[RubricCriterionSchema] = Field(default_factory=list)
    rubric_ratings: List[str] = Field(
        default_factory=list,
        description="Canvas data-testid values for each criterion rating button (full credit)",
    )
    grading_requirements: Optional[GradingRequirementsSchema] = Field(
        default=None,
        description="Rules: peer replies, on-time, citations",
    )
    rubric_rating_levels: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        description="Per-criterion Canvas test IDs for exceeds/meets/needs/below",
    )


class SpeedGraderConfig(BaseModel):
    """Schema for Speed Grader automation on a discussion assignment"""

    assignment_id: str = Field(..., min_length=1, description="Canvas assignment ID for Speed Grader")
    grade: str = Field(default="100", description="Points to assign each submission")
    rubric_ratings: List[str] = Field(
        default_factory=list,
        description="data-testid values for rubric rating buttons (top rating per criterion)",
    )
    use_rubric: bool = Field(
        default=True,
        description="Open rubric and apply rubric_ratings before saving grade",
    )

    @field_validator("assignment_id")
    @classmethod
    def validate_assignment_id(cls, v: str) -> str:
        """Validate assignment_id is not a placeholder"""
        if v.upper() in ["FILL_ME", "TODO", "TBD"]:
            raise ValueError(f"assignment_id must be filled in, found: {v}")
        if not v.isdigit():
            raise ValueError(f"assignment_id must be numeric, got: {v}")
        return v


class WeekConfig(BaseModel):
    """Schema for weekly course configuration"""

    topic_id: str = Field(..., min_length=1, description="Canvas discussion topic ID")
    discussion_prompt: str = Field(..., min_length=1, description="Discussion prompt text")
    discussion_data: List[DiscussionData] = Field(
        default_factory=list, description="Example posts and responses for LLM training"
    )
    speed_grader: Optional[SpeedGraderConfig] = Field(
        default=None, description="Speed Grader settings for discussion assignment grading"
    )

    @field_validator("topic_id")
    @classmethod
    def validate_topic_id(cls, v: str) -> str:
        """Validate topic_id is not a placeholder"""
        if v.upper() in ["FILL_ME", "TODO", "TBD"]:
            raise ValueError(f"topic_id must be filled in, found: {v}")
        return v


class CourseSchema(BaseModel):
    """Schema for course configuration"""

    course_id: str = Field(..., min_length=1, description="Canvas course ID")
    course_start_date: str = Field(..., description="Course start date in YYYY-MM-DD format")
    name: Optional[str] = Field(default="Unnamed Course", description="Course display name")
    discussion_rubric: Optional[DiscussionRubricSchema] = Field(
        default=None,
        description="Shared Discussion Rubric (2021) for all weekly discussion assignments",
    )
    weeks: Dict[str, WeekConfig] = Field(..., description="Weekly course data keyed by week number")

    @field_validator("course_start_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in correct format"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")

    @field_validator("course_id")
    @classmethod
    def validate_course_id(cls, v: str) -> str:
        """Validate course_id is numeric string"""
        if not v.isdigit():
            raise ValueError(f"course_id must be numeric, got: {v}")
        return v


class CoursesConfig(BaseModel):
    """Schema for courses.json configuration file"""

    courses: Dict[str, CourseSchema] = Field(
        ..., description="Dictionary of courses keyed by course selector"
    )

    @field_validator("courses")
    @classmethod
    def validate_courses_not_empty(cls, v: Dict) -> Dict:
        """Validate at least one course exists"""
        if not v:
            raise ValueError("At least one course must be defined")
        return v


class AnnouncementSchema(BaseModel):
    """Schema for individual announcement"""

    week: int = Field(..., ge=1, le=8, description="Week number (1-8)")
    title: str = Field(..., min_length=1, description="Announcement title")
    content: str = Field(..., min_length=1, description="Announcement HTML content")


class AnnouncementsConfig(BaseModel):
    """Schema for announcements.json configuration file"""

    announcements: List[AnnouncementSchema] = Field(
        ..., min_length=1, description="List of course announcements"
    )


def validate_courses_config(config: dict) -> CoursesConfig:
    """
    Validate courses configuration

    Args:
        config: Raw configuration dictionary

    Returns:
        Validated CoursesConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    return CoursesConfig(**config)


def validate_announcements_config(config: dict) -> AnnouncementsConfig:
    """
    Validate announcements configuration

    Args:
        config: Raw configuration dictionary

    Returns:
        Validated AnnouncementsConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    return AnnouncementsConfig(**config)
