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


class WeekConfig(BaseModel):
    """Schema for weekly course configuration"""
    topic_id: str = Field(..., min_length=1, description="Canvas discussion topic ID")
    discussion_prompt: str = Field(..., min_length=1, description="Discussion prompt text")
    discussion_data: List[DiscussionData] = Field(
        default_factory=list, 
        description="Example posts and responses for LLM training"
    )
    
    @field_validator('topic_id')
    @classmethod
    def validate_topic_id(cls, v: str) -> str:
        """Validate topic_id is not a placeholder"""
        if v.upper() in ['FILL_ME', 'TODO', 'TBD']:
            raise ValueError(f"topic_id must be filled in, found: {v}")
        return v


class CourseSchema(BaseModel):
    """Schema for course configuration"""
    course_id: str = Field(..., min_length=1, description="Canvas course ID")
    course_start_date: str = Field(..., description="Course start date in YYYY-MM-DD format")
    name: Optional[str] = Field(default="Unnamed Course", description="Course display name")
    weeks: Dict[str, WeekConfig] = Field(..., description="Weekly course data keyed by week number")
    
    @field_validator('course_start_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in correct format"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f'Date must be in YYYY-MM-DD format, got: {v}')
    
    @field_validator('course_id')
    @classmethod
    def validate_course_id(cls, v: str) -> str:
        """Validate course_id is numeric string"""
        if not v.isdigit():
            raise ValueError(f'course_id must be numeric, got: {v}')
        return v


class CoursesConfig(BaseModel):
    """Schema for courses.json configuration file"""
    courses: Dict[str, CourseSchema] = Field(
        ..., 
        description="Dictionary of courses keyed by course selector"
    )
    
    @field_validator('courses')
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
        ..., 
        min_length=1,
        description="List of course announcements"
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

