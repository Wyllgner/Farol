"""Fallback deterministico por palavras-chave.

Secao 10: "se a chamada ao modelo falhar, classificacao deterministica por
palavras-chave assume. O sistema degrada com elegancia; nunca quebra."

Este modulo nao e um stub descartavel: ele roda em producao toda vez que a
API de LLM estiver indisponivel, e e a resposta a uma pergunta previsivel da
banca sobre dependencia de terceiros.
"""

import unicodedata

from app.enums import Categoria
from app.llm.base import Classificacao, RespostaAncorada

# Ordem importa: a primeira categoria com match vence. As mais especificas
# vem antes das genericas para que "esqueci a senha do 2FA" caia em 2FA.
PALAVRAS: list[tuple[Categoria, tuple[str, ...]]] = [
    (Categoria.DOIS_FATORES, ("2fa", "dois fatores", "duplo fator", "autenticacao", "qr code",
                              "codigo do aplicativo", "google authenticator", "verificacao em duas")),
    (Categoria.CERTIFICADO, ("certificado", "certificacao", "diploma", "declaracao de conclusao")),
    (Categoria.WEBCONFERENCIA, ("webconferencia", "web conferencia", "sala virtual", "aula ao vivo",
                                "transmissao", "link da aula", "zoom", "meet")),
    (Categoria.SENHA, ("senha", "redefinir", "recuperar acesso", "esqueci minha senha", "resetar")),
    (Categoria.PRAZO, ("prazo", "data limite", "vence", "vencimento", "ate quando", "atraso")),
    (Categoria.INSCRICAO, ("inscricao", "me inscrever", "matricula", "vaga", "edital")),
    (Categoria.LOCALIZACAO_CURSO, ("onde fica", "nao encontro", "nao acho", "localizar",
                                   "cade o curso", "onde esta o curso")),
    (Categoria.ACESSO, ("acessar", "acesso", "entrar", "login", "logar", "nao consigo entrar",
                        "primeiro acesso", "plataforma")),
    (Categoria.CONTEUDO, ("modulo", "videoaula", "material", "apostila", "conteudo", "atividade")),
    (Categoria.RECLAMACAO, ("reclamacao", "absurdo", "pessimo", "descaso", "ninguem responde",
                            "ouvidoria", "insatisfeito")),
    (Categoria.SENSIVEL, ("cpf", "dados pessoais", "atestado", "medico", "saude", "pagamento",
                          "reembolso", "financeiro", "processo", "judicial", "urgente")),
]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


class FallbackProvider:
    """Provedor sem rede. Classifica por palavra-chave e nunca gera texto livre."""

    nome = "fallback"

    async def classificar(self, texto: str) -> Classificacao:
        alvo = _normalizar(texto)
        for categoria, termos in PALAVRAS:
            if any(_normalizar(t) in alvo for t in termos):
                # Confianca deliberadamente media: casamento lexico nao e
                # compreensao. Na Politica de Triagem isso leva a resposta
                # com oferta de humano, nunca a resposta seca.
                return Classificacao(categoria=categoria, confianca=0.55, degradado=True)
        # no_escopo fica True sempre: sem modelo nao ha como julgar assunto,
        # e recusar por escopo com base em ausencia de palavra-chave
        # dispensaria gente com duvida legitima escrita de outro jeito.
        # Degradado escala demais; nunca recusa demais.
        return Classificacao(categoria=Categoria.OUTROS, confianca=0.20, degradado=True)

    async def gerar_ancorado(self, pergunta: str, trechos: list[dict]) -> RespostaAncorada:
        # Sem LLM nao existe geracao ancorada confiavel. Preferimos o silencio
        # ao erro (secao 18): devolve NAO_SEI e deixa a triagem escalar.
        return RespostaAncorada(texto="", fontes=[], nao_sei=True)

    async def embutir(self, textos: list[str]) -> list[list[float]]:
        raise RuntimeError(
            "Embeddings exigem provedor real; o fallback nao substitui a indexacao."
        )
