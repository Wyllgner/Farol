"""Provedor OpenAI — classificacao e geracao ancorada com gpt-5-nano.

Secao 18: a IA faz exatamente tres coisas — entender linguagem natural informal,
recuperar o trecho que fundamenta a resposta, e descobrir agrupamentos de causa.
Toda decisao (quando escalar, o que e sensivel) e regra deterministica fora daqui.
"""

import json
import logging
import re

from openai import APIError, AsyncOpenAI

from app.config import settings
from app.enums import Categoria
from app.llm.base import Classificacao, RespostaAncorada
from app.llm.fallback import FallbackProvider

logger = logging.getLogger(__name__)

_SISTEMA_CLASSIFICACAO = """Voce classifica mensagens recebidas pela Escola da \
Magistratura de Rondonia (EMERON) em exatamente uma das categorias listadas.
Responda apenas com o identificador da categoria."""

_SISTEMA_GERACAO = """Voce e o FAROL, assistente da Secao de Coordenacao de \
Educacao a Distancia (SECOEAD) da EMERON.

REGRAS INEGOCIAVEIS:
1. Responda EXCLUSIVAMENTE com base nos trechos oficiais fornecidos.
2. Se os trechos nao sustentarem a resposta, devolva nao_sei = true.
3. Nunca invente prazo, link, procedimento ou numero.
4. Maximo 3 frases. Linguagem de pessoa, nao de sistema.
5. Em "fontes", liste apenas ids de trechos realmente usados.
6. NUNCA escreva o id do trecho dentro do texto da resposta. A pessoa do
   outro lado nao sabe o que e um id, e citar isso quebra a leitura."""

# Schema estrito: garante que toda resposta chegue com o campo de fontes,
# que e o que a verificacao de ancoragem (F11) confere na Fase 2.
_SCHEMA_RESPOSTA = {
    "type": "object",
    "properties": {
        "texto": {"type": "string"},
        "fontes": {"type": "array", "items": {"type": "string"}},
        "nao_sei": {"type": "boolean"},
    },
    "required": ["texto", "fontes", "nao_sei"],
    "additionalProperties": False,
}


class OpenAIProvider:
    """Classificacao e geracao. Degrada para o fallback deterministico em erro."""

    nome = "openai"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key or None)
        self._fallback = FallbackProvider()

    async def classificar(self, texto: str) -> Classificacao:
        catalogo = [c.value for c in Categoria]
        try:
            resposta = await self._client.chat.completions.create(
                model=settings.llm_model_classificacao,
                reasoning_effort="low",
                messages=[
                    {"role": "system", "content": _SISTEMA_CLASSIFICACAO},
                    {"role": "user", "content": texto},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "classificacao",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "categoria": {"type": "string", "enum": catalogo}
                            },
                            "required": ["categoria"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
        except APIError:
            logger.warning("LLM indisponivel na classificacao; assumindo fallback")
            return await self._fallback.classificar(texto)

        conteudo = resposta.choices[0].message.content
        if not conteudo:
            # Resposta vazia (recusa ou corte). Nao adivinhamos a categoria.
            return await self._fallback.classificar(texto)

        bruto = json.loads(conteudo)["categoria"]
        try:
            return Classificacao(categoria=Categoria(bruto), confianca=0.85)
        except ValueError:
            logger.warning("Categoria fora do vocabulario controlado: %r", bruto)
            return await self._fallback.classificar(texto)

    async def gerar_ancorado(self, pergunta: str, trechos: list[dict]) -> RespostaAncorada:
        if not trechos:
            # Secao 7.2: sem fonte valida e vigente, o FAROL escala.
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        contexto = "\n\n".join(f"[{t['id']}] {t['texto']}" for t in trechos)
        try:
            resposta = await self._client.chat.completions.create(
                model=settings.llm_model_geracao,
                reasoning_effort="medium",
                messages=[
                    {"role": "system", "content": _SISTEMA_GERACAO},
                    {
                        "role": "user",
                        "content": f"Trechos oficiais:\n{contexto}\n\nPergunta:\n{pergunta}",
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "resposta_ancorada",
                        "strict": True,
                        "schema": _SCHEMA_RESPOSTA,
                    },
                },
            )
        except APIError:
            logger.warning("LLM indisponivel na geracao; preferimos o silencio ao erro")
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        conteudo = resposta.choices[0].message.content
        if not conteudo:
            return RespostaAncorada(texto="", fontes=[], nao_sei=True)

        dados = json.loads(conteudo)
        ids_validos = {t["id"] for t in trechos}
        # Cinto e suspensorio: mesmo instruido, o modelo as vezes cita o id
        # no meio da frase. A citacao vive no campo de fontes; o texto que
        # a pessoa le nao deve conter identificador nenhum.
        texto = _limpar_citacoes(dados["texto"], ids_validos)
        # O modelo pode citar um id que nao existe. Uma fonte inventada e
        # exatamente o que a ancoragem existe para impedir, entao ela cai aqui.
        fontes = [f for f in dados["fontes"] if f in ids_validos]

        return RespostaAncorada(
            texto=texto,
            fontes=fontes,
            nao_sei=dados["nao_sei"] or not fontes,
        )

    async def embutir(self, textos: list[str]) -> list[list[float]]:
        from app.llm.embeddings import embutir

        return await embutir(textos)


def _limpar_citacoes(texto: str, ids: set[str]) -> str:
    """Remove ids de trecho que tenham escapado para o texto visivel."""
    for identificador in ids:
        texto = texto.replace(f"[{identificador}]", "").replace(identificador, "")
    # Sobras tipicas: "Conforme o trecho , ..." e espacos duplicados.
    texto = re.sub(r"\s*\[\s*\]", "", texto)
    texto = re.sub(r"(?i)\bconforme o trecho\s*[,:]?\s*", "", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()
