"""
Unit tests for env_validator module
"""

import pytest

from env_validator import Settings


class TestSettings:
    """Tests for Settings validation"""

    def test_get_available_providers_all(self, tmp_path, monkeypatch):
        """Test getting all available providers"""
        # Change to tmp directory to avoid loading .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        settings = Settings(
            CANVAS_USERNAME="test@example.com",
            CANVAS_PASSWORD="password",
            OPENAI_API_KEY="sk-test",
            ANTHROPIC_API_KEY="sk-ant-test",
            DEEPSEEK_API_KEY="sk-test",
        )
        providers = settings.get_available_providers()
        assert len(providers) == 3
        assert ("openai", "OpenAI") in providers
        assert ("anthropic", "Anthropic") in providers
        assert ("deepseek", "DeepSeek") in providers

    def test_get_available_providers_single(self, tmp_path, monkeypatch):
        """Test getting single available provider"""
        # Change to tmp directory to avoid loading .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        settings = Settings(
            CANVAS_USERNAME="test@example.com", CANVAS_PASSWORD="password", OPENAI_API_KEY="sk-test"
        )
        providers = settings.get_available_providers()
        assert len(providers) == 1
        assert providers[0] == ("openai", "OpenAI")

    def test_validate_llm_keys_success(self, tmp_path, monkeypatch):
        """Test successful LLM key validation"""
        # Change to tmp directory to avoid loading .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        settings = Settings(
            CANVAS_USERNAME="test@example.com", CANVAS_PASSWORD="password", OPENAI_API_KEY="sk-test"
        )
        # Should not raise
        settings.validate_llm_keys()

    def test_validate_llm_keys_failure(self, tmp_path, monkeypatch):
        """Test LLM key validation failure"""
        # Change to tmp directory to avoid loading .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        settings = Settings(CANVAS_USERNAME="test@example.com", CANVAS_PASSWORD="password")
        with pytest.raises(ValueError, match="At least one LLM API key"):
            settings.validate_llm_keys()
