"""Embeddings para a busca semantica (pgvector).

Isolado num modulo so de proposito: trocar de provedor de embeddings nao
deve tocar o resto do motor, e a dimensao do vetor e uma decisao de schema
(muda-la exige regerar a migration do chunk).

Provedores:
  openai — text-embedding-3-small, mesma chave do LLM. 1536 dimensoes.
  local  — sentence-transformers offline, sem chave e sem custo. 768 dimensoes.
"""

from app.config import settings


async def embutir(textos: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "local":
        return _embutir_local(textos)
    return await _embutir_openai(textos)


async def _embutir_openai(textos: list[str]) -> list[list[float]]:
    from openai import AsyncOpenAI

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY ausente. Defina a chave ou use EMBEDDING_PROVIDER=local."
        )
    cliente = AsyncOpenAI(api_key=settings.openai_api_key)
    resposta = await cliente.embeddings.create(
        model=settings.embedding_model, input=textos
    )
    # A API nao garante ordem; reordenamos pelo indice devolvido.
    return [item.embedding for item in sorted(resposta.data, key=lambda d: d.index)]


_modelo_local = None


def _embutir_local(textos: list[str]) -> list[list[float]]:
    global _modelo_local
    if _modelo_local is None:
        from sentence_transformers import SentenceTransformer

        _modelo_local = SentenceTransformer(settings.embedding_model_local)
    return _modelo_local.encode(textos, normalize_embeddings=True).tolist()
