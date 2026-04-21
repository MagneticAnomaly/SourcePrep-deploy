"""LLM provider bridge for LangGraph/CrewAI adapters.

Reads AI Gateway config and constructs a LangChain-compatible LLM instance.
Only imported when langgraph or crewai extras are installed.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_langchain_llm(
    provider: str = "ollama",
    model: str = "",
    endpoint_url: str = "http://localhost:11434",
    api_key: Optional[str] = None,
    temperature: float = 0.1,
) -> Any:
    """Construct a LangChain LLM instance from provider settings.

    Args:
        provider: One of "ollama", "anthropic", "openai", "openai-compatible".
        model: Model name/ID.
        endpoint_url: Base URL for the provider.
        api_key: API key for cloud providers.
        temperature: Sampling temperature.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ImportError: If the required langchain provider package is not installed.
        ValueError: If the provider is not supported.
    """
    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "langchain-ollama is required for Ollama LangGraph adapters. "
                "Install with: pip install prep[langgraph]"
            )
        return ChatOllama(
            model=model,
            base_url=endpoint_url,
            temperature=temperature,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is required for Anthropic LangGraph adapters. "
                "Install with: pip install prep[langgraph]"
            )
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    if provider in ("openai", "openai-compatible"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for OpenAI LangGraph adapters. "
                "Install with: pip install prep[langgraph]"
            )
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=endpoint_url if provider == "openai-compatible" else None,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported LLM provider for LangChain bridge: {provider}")


def build_llm_from_settings() -> Any:
    """Build a LangChain LLM from the Prep AI Gateway settings.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ValueError: If no LLM is configured.
    """
    from prep.services.settings_store import settings

    config = settings.get("pipeline_config") or {}
    model = config.get("model_thinking", "")
    if not model:
        raise ValueError("No LLM model configured in AI Gateway settings.")

    provider = config.get("llm_provider", "ollama")
    endpoint_url = config.get("ollama_url", "http://localhost:11434")
    api_key = config.get("anthropic_api_key") or config.get("openai_api_key")

    if provider == "anthropic":
        endpoint_url = "https://api.anthropic.com"
    elif provider == "openai":
        endpoint_url = config.get("openai_url", "https://api.openai.com")

    return build_langchain_llm(
        provider=provider,
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
    )
