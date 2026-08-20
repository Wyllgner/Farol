"""Fabrica de provedor de LLM."""

from functools import lru_cache

from app.config import settings
from app.llm.base import Classificacao, LLMProvider, RespostaAncorada
from app.llm.fallback import FallbackProvider

__all__ = [
    "Classificacao",
    "LLMProvider",
    "RespostaAncorada",
    "obter_provider",
    "provider_ativo",
]


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


def provider_ativo() -> LLMProvider:
    """O provedor para uma chamada real, ja passado pelo teto de gasto.

    `obter_provider` e a fabrica; esta e a porta por onde o motor passa toda
    vez que vai gastar credito. Estourado o orcamento do dia, devolve o
    fallback deterministico: o FAROL responde pior, mas responde, e o
    `/health` conta a verdade sobre o modo degradado.
    """
    from app.seguranca import teto_llm

    provider = obter_provider()
    if provider.nome == "fallback":
        return provider

    if not teto_llm.consumir():
        import logging

        logging.getLogger(__name__).error(
            "teto diario de chamadas ao provedor atingido (%s): operando em fallback",
            teto_llm.teto,
        )
        return FallbackProvider()

    return provider
