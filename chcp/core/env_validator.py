"""
Environment variable validation using Pydantic
"""

from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with validation

    Automatically loads from .env file if present
    """

    # 1Password Login item (required for Canvas auth + MFA OTP)
    CANVAS_OP_ITEM: str = Field(
        ..., description="1Password Login item name/ID for Canvas credentials + OTP"
    )
    CANVAS_OP_VAULT: Optional[str] = Field(
        None, description="Optional 1Password vault containing CANVAS_OP_ITEM"
    )

    # Optional LLM API keys (at least one required)
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API key")
    DEEPSEEK_API_KEY: Optional[str] = Field(None, description="DeepSeek API key")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra environment variables
    }

    @model_validator(mode="after")
    def validate_credentials(self) -> "Settings":
        """Require a 1Password Login item reference."""
        item = (self.CANVAS_OP_ITEM or "").strip()
        if not item:
            raise ValueError(
                "Set CANVAS_OP_ITEM to your 1Password Login item UUID or name"
            )
        self.CANVAS_OP_ITEM = item
        return self

    def validate_llm_keys(self) -> None:
        """Ensure at least one LLM API key is set"""
        if not any([self.OPENAI_API_KEY, self.ANTHROPIC_API_KEY, self.DEEPSEEK_API_KEY]):
            raise ValueError(
                "At least one LLM API key must be set: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY"
            )

    def get_available_providers(self) -> list[tuple[str, str]]:
        """Get list of available LLM providers based on API keys"""
        providers = []
        if self.OPENAI_API_KEY:
            providers.append(("openai", "OpenAI"))
        if self.ANTHROPIC_API_KEY:
            providers.append(("anthropic", "Anthropic"))
        if self.DEEPSEEK_API_KEY:
            providers.append(("deepseek", "DeepSeek"))
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
