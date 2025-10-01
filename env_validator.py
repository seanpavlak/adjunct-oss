"""
Environment variable validation using Pydantic
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with validation
    
    Automatically loads from .env file if present
    """
    # Required credentials
    CANVAS_USERNAME: str = Field(..., description="Canvas LMS username/email")
    CANVAS_PASSWORD: str = Field(..., description="Canvas LMS password")
    
    # Optional LLM API keys (at least one required)
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API key")
    DEEPSEEK_API_KEY: Optional[str] = Field(None, description="DeepSeek API key")
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': True,
        'extra': 'ignore'  # Ignore extra environment variables
    }
    
    @field_validator('CANVAS_USERNAME')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is not empty"""
        if not v or not v.strip():
            raise ValueError("CANVAS_USERNAME cannot be empty")
        return v.strip()
    
    @field_validator('CANVAS_PASSWORD')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password is not empty"""
        if not v or not v.strip():
            raise ValueError("CANVAS_PASSWORD cannot be empty")
        return v
    
    def validate_llm_keys(self) -> None:
        """Ensure at least one LLM API key is set"""
        if not any([
            self.OPENAI_API_KEY, 
            self.ANTHROPIC_API_KEY, 
            self.DEEPSEEK_API_KEY
        ]):
            raise ValueError(
                "At least one LLM API key must be set: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY"
            )
    
    def get_available_providers(self) -> list[tuple[str, str]]:
        """Get list of available LLM providers based on API keys"""
        providers = []
        if self.OPENAI_API_KEY:
            providers.append(('openai', 'OpenAI'))
        if self.ANTHROPIC_API_KEY:
            providers.append(('anthropic', 'Anthropic'))
        if self.DEEPSEEK_API_KEY:
            providers.append(('deepseek', 'DeepSeek'))
        return providers


def load_and_validate_settings() -> Settings:
    """
    Load and validate settings from environment
    
    Returns:
        Validated Settings instance
        
    Raises:
        ValidationError: If required settings are missing or invalid
    """
    settings = Settings()
    settings.validate_llm_keys()
    return settings

