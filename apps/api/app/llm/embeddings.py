"""Embeddings para a busca semantica (pgvector).

Isolado num modulo so de proposito: trocar de provedor de embeddings nao
deve tocar o resto do motor, e a dimensao do vetor e uma decisao de schema
(muda-la exige regerar a migration do chunk).

Provedores:
  openai: text-embedding-3-small, mesma chave do LLM. 1536 dimensoes.
  local: sentence-transformers offline, sem chave e sem custo. 768 dimensoes.
"""

from app.config import settings


async def embutir(textos: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "local":
        return _embutir_local(textos)
    return await _embutir_openai(textos)


async def _embutir_openai(textos: list[str]) -> list[list[float]]:
    from openai import AsyncOpenAI, AuthenticationError

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY ausente. Defina a chave ou use EMBEDDING_PROVIDER=local."
        )
    cliente = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resposta = await cliente.embeddings.create(
            model=settings.embedding_model, input=textos
        )
    except AuthenticationError as erro:
        # O rastro de pilha da biblioteca nao diz a unica coisa que
        # importa aqui: a chave configurada nao vale. E a falha mais comum
        # de um deploy novo, e merece ser dita em uma linha.
        from app.seguranca import mascarar

        raise RuntimeError(
            f"A chave da OpenAI foi recusada (401). Chave em uso: "
            f"{mascarar(settings.openai_api_key)}. Confira se ela esta ativa, "
            f"se pertence ao projeto certo e se foi colada inteira, sem espacos."
        ) from erro
    # A API nao garante ordem; reordenamos pelo indice devolvido.
    return [item.embedding for item in sorted(resposta.data, key=lambda d: d.index)]


_modelo_local = None


def _embutir_local(textos: list[str]) -> list[list[float]]:
    global _modelo_local
    if _modelo_local is None:
        from sentence_transformers import SentenceTransformer

        _modelo_local = SentenceTransformer(settings.embedding_model_local)
    return _modelo_local.encode(textos, normalize_embeddings=True).tolist()
