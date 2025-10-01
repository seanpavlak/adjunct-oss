"""
Unit tests for llm_manager module
"""

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from llm_manager import LLMManager


class TestLLMManager:
    """Tests for LLMManager class"""

    def test_create_openai_llm(self):
        """Test creating OpenAI LLM"""
        llm = LLMManager.create_llm(provider="openai", api_key="sk-test", verbose=False)
        assert isinstance(llm, ChatOpenAI)

    def test_create_anthropic_llm(self):
        """Test creating Anthropic LLM"""
        llm = LLMManager.create_llm(provider="anthropic", api_key="sk-ant-test", verbose=False)
        assert isinstance(llm, ChatAnthropic)

    def test_create_deepseek_llm(self):
        """Test creating DeepSeek LLM"""
        llm = LLMManager.create_llm(provider="deepseek", api_key="sk-test", verbose=False)
        # DeepSeek uses OpenAI-compatible API
        assert isinstance(llm, ChatOpenAI)

    def test_unsupported_provider(self):
        """Test error for unsupported provider"""
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMManager.create_llm(provider="invalid", api_key="test")  # type: ignore

    def test_missing_api_key(self):
        """Test error when API key is missing"""
        with pytest.raises(ValueError, match="API key is required"):
            LLMManager.create_llm(provider="openai", api_key="")

    def test_detect_provider_single(self):
        """Test detecting single provider"""
        provider = LLMManager.detect_provider(openai_key="sk-test")
        assert provider == "openai"

    def test_detect_provider_multiple(self):
        """Test detecting provider when multiple available"""
        provider = LLMManager.detect_provider(openai_key="sk-test", anthropic_key="sk-ant-test")
        # Should return first available (openai)
        assert provider == "openai"

    def test_detect_provider_none(self):
        """Test error when no providers available"""
        with pytest.raises(ValueError, match="No LLM API keys found"):
            LLMManager.detect_provider()
