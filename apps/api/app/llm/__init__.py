"""Fabrica de provedor de LLM."""

from functools import lru_cache

from app.config import settings
from app.llm.base import Classificacao, LLMProvider, RespostaAncorada
from app.llm.fallback import FallbackProvider

__all__ = ["Classificacao", "LLMProvider", "RespostaAncorada", "obter_provider"]


@lru_cache(maxsize=1)
def obter_provider() -> LLMProvider:
    """Sem chave, o motor cai no fallback deterministico em vez de quebrar."""
    if settings.llm_provider == "openai" and settings.openai_api_key:
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    return FallbackProvider()
