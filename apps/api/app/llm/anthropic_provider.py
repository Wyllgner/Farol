"""Provedor Anthropic — classificacao e geracao ancorada.

Secao 18: a IA faz exatamente tres coisas — entender linguagem natural informal,
recuperar o trecho que fundamenta a resposta, e descobrir agrupamentos de causa.
Toda decisao (quando escalar, o que e sensivel) e regra deterministica fora daqui.
"""

import json
import logging

from anthropic import APIError, AsyncAnthropic

from app.config import settings
from app.enums import Categoria
from app.llm.base import Classificacao, RespostaAncorada
from app.llm.fallback import FallbackProvider

logger = logging.getLogger(__name__)

_PROMPT_CLASSIFICACAO = """Voce classifica mensagens recebidas pela Escola da \
Magistratura de Rondonia (EMERON) em exatamente uma das 12 categorias abaixo.

{categorias}

Responda somente com o identificador da categoria, sem explicacao.

Mensagem do participante:
{texto}"""

_PROMPT_GERACAO = """Voce e o FAROL, assistente da Secao de Coordenacao de Educacao \
a Distancia (SECOEAD) da EMERON.

REGRAS INEGOCIAVEIS:
1. Responda EXCLUSIVAMENTE com base nos trechos oficiais fornecidos abaixo.
2. Se os trechos nao sustentarem a resposta, devolva exatamente NAO_SEI.
3. Nunca invente prazo, link, procedimento ou numero.
4. Maximo 3 frases. Linguagem de pessoa, nao de sistema.
5. Cite os ids das fontes que sustentam cada afirmacao.

Trechos oficiais:
{trechos}

Pergunta:
{pergunta}

Responda em JSON: {{"texto": "...", "fontes": ["chunk_id"], "nao_sei": false}}"""


class AnthropicProvider:
    """Classificacao e geracao. Degrada para o fallback deterministico em erro."""

    nome = "anthropic"

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)
        self._fallback = FallbackProvider()

    async def classificar(self, texto: str) -> Classificacao:
        catalogo = "\n".join(f"- {c.value}" for c in Categoria)
        try:
            resposta = await self._client.messages.create(
                model=settings.llm_model_classificacao,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                messages=[
                    {
                        "role": "user",
                        "content": _PROMPT_CLASSIFICACAO.format(
                            categorias=catalogo, texto=texto
                        ),
                    }
                ],
            )
        except APIError:
            logger.warning("LLM indisponivel na classificacao; assumindo fallback")
            return await self._fallback.classificar(texto)

        if resposta.stop_reason == "refusal":
            return await self._fallback.classificar(texto)

        bruto = _primeiro_texto(resposta).strip().lower()
        try:
            return Classificacao(categoria=Categoria(bruto), confianca=0.85)
        except ValueError:
            # Modelo devolveu algo fora do vocabulario controlado. Nao adivinhamos.
            logger.warning("Categoria desconhecida do LLM: %r", bruto)
            return await self._fallback.classificar(texto)

    async def gerar_ancorado(self, pergunta: str, trechos: list[dict]) -> RespostaAncorada:
        if not trechos:
            # Secao 7.2: sem fonte valida e vigente, o FAROL escala.
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        contexto = "\n\n".join(f"[{t['id']}] {t['texto']}" for t in trechos)
        try:
            resposta = await self._client.messages.create(
                model=settings.llm_model_geracao,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "texto": {"type": "string"},
                                "fontes": {"type": "array", "items": {"type": "string"}},
                                "nao_sei": {"type": "boolean"},
                            },
                            "required": ["texto", "fontes", "nao_sei"],
                            "additionalProperties": False,
                        },
                    },
                },
                messages=[
                    {
                        "role": "user",
                        "content": _PROMPT_GERACAO.format(
                            trechos=contexto, pergunta=pergunta
                        ),
                    }
                ],
            )
        except APIError:
            logger.warning("LLM indisponivel na geracao; preferimos o silencio ao erro")
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        if resposta.stop_reason == "refusal":
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        dados = json.loads(_primeiro_texto(resposta))
        return RespostaAncorada(
            texto=dados["texto"],
            fontes=dados["fontes"],
            nao_sei=dados["nao_sei"] or not dados["fontes"],
        )

    async def embutir(self, textos: list[str]) -> list[list[float]]:
        from app.llm.embeddings import embutir

        return await embutir(textos)


def _primeiro_texto(resposta) -> str:
    for bloco in resposta.content:
        if bloco.type == "text":
            return bloco.text
    return ""
