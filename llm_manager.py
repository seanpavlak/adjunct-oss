"""
LLM provider management and initialization
"""

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config import llm_config
from logger import logger


class LLMManager:
    """Centralized LLM provider management"""

    @staticmethod
    def create_llm(
        provider: Literal["openai", "anthropic", "deepseek"],
        api_key: str,
        temperature: float = None,
        verbose: bool = True,
    ) -> BaseChatModel:
        """
        Factory method for creating LLM instances

        Args:
            provider: LLM provider name
            api_key: API key for the provider
            temperature: Sampling temperature (uses default from config if None)
            verbose: Enable verbose logging

        Returns:
            Initialized LLM instance

        Raises:
            ValueError: If provider is unsupported or API key is missing
        """
        if temperature is None:
            temperature = llm_config.TEMPERATURE

        if provider == "openai":
            if not api_key:
                raise ValueError("OpenAI API key is required when using OpenAI provider")

            logger.info(f"Initializing OpenAI LLM (model: {llm_config.OPENAI_MODEL})")
            return ChatOpenAI(
                model=llm_config.OPENAI_MODEL,
                temperature=temperature,
                openai_api_key=api_key,
                verbose=verbose,
            )

        elif provider == "anthropic":
            if not api_key:
                raise ValueError("Anthropic API key is required when using Anthropic provider")

            logger.info(f"Initializing Anthropic LLM (model: {llm_config.ANTHROPIC_MODEL})")
            return ChatAnthropic(
                model=llm_config.ANTHROPIC_MODEL,
                temperature=temperature,
                anthropic_api_key=api_key,
                verbose=verbose,
            )

        elif provider == "deepseek":
            if not api_key:
                raise ValueError("DeepSeek API key is required when using DeepSeek provider")

            logger.info(f"Initializing DeepSeek LLM (model: {llm_config.DEEPSEEK_MODEL})")
            # DeepSeek uses OpenAI-compatible API
            return ChatOpenAI(
                model=llm_config.DEEPSEEK_MODEL,
                temperature=temperature,
                openai_api_key=api_key,
                base_url=llm_config.DEEPSEEK_BASE_URL,
                verbose=verbose,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def detect_provider(
        openai_key: str = "", anthropic_key: str = "", deepseek_key: str = ""
    ) -> str:
        """
        Auto-detect which LLM provider to use based on available API keys

        Args:
            openai_key: OpenAI API key
            anthropic_key: Anthropic API key
            deepseek_key: DeepSeek API key

        Returns:
            Provider name string

        Raises:
            ValueError: If no API keys are provided
        """
        available_providers = []

        if openai_key:
            available_providers.append(("openai", "OpenAI"))
        if anthropic_key:
            available_providers.append(("anthropic", "Anthropic"))
        if deepseek_key:
            available_providers.append(("deepseek", "DeepSeek"))

        if not available_providers:
            raise ValueError(
                "No LLM API keys found. Please set at least one of: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY"
            )

        if len(available_providers) > 1:
            provider_names = [name for _, name in available_providers]
            logger.info(f"Multiple LLM providers available: {', '.join(provider_names)}")
            logger.info(f"Using {available_providers[0][1]} (first available)")

        return available_providers[0][0]
