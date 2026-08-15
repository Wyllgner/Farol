"""Politica de Triagem (secao 5.3).

Explicita, deterministica e auditavel — NAO e IA que decide quando escalar.
Toda a logica aqui e codigo puro sobre valores do vocabulario controlado;
nenhuma chamada de modelo acontece neste modulo, por design.

A tela "Como o FAROL decide" (secao 7.3) publica exatamente esta tabela.
"""

from dataclasses import dataclass

from app.enums import CATEGORIAS_SENSIVEIS, Categoria, DecisaoTriagem

# Limiares da tabela da secao 5.3.
CONFIANCA_ALTA = 0.70
CONFIANCA_MEDIA = 0.45

# A recusa e institucional e digna. Nao pede desculpas por existir nem
# finge que o sistema falhou: delimita competencia.
TEXTO_RECUSA = (
    "Essa situacao exige analise de um servidor da SECOEAD e eu nao posso "
    "decidir por eles. Ja encaminhei seu caso com todo o contexto e voce "
    "recebera retorno por este mesmo canal."
)


@dataclass(slots=True)
class Decisao:
    decisao: DecisaoTriagem
    motivo: str
    # Sempre preenchido: a transparencia da decisao nao depende do caminho.
    confianca: float
    sensivel: bool

    @property
    def escala(self) -> bool:
        return self.decisao is DecisaoTriagem.ESCALA


def eh_sensivel(categoria: Categoria) -> bool:
    return categoria in CATEGORIAS_SENSIVEIS


def decidir(
    categoria: Categoria,
    confianca: float,
    tem_fonte: bool,
    nao_sei: bool,
) -> Decisao:
    """Aplica a tabela da secao 5.3, na ordem em que ela e escrita.

    A ordem importa: a sensibilidade e avaliada ANTES da confianca, porque
    categoria sensivel escala sempre, independentemente da confianca. Uma
    resposta muito confiante sobre dado pessoal e exatamente o caso que
    nao pode passar.
    """
    sensivel = eh_sensivel(categoria)

    if sensivel:
        return Decisao(
            decisao=DecisaoTriagem.ESCALA,
            motivo="categoria sensivel: escala sempre, independentemente da confianca",
            confianca=confianca,
            sensivel=True,
        )

    if nao_sei or not tem_fonte:
        return Decisao(
            decisao=DecisaoTriagem.ESCALA,
            motivo="sem fonte oficial que sustente a resposta",
            confianca=confianca,
            sensivel=False,
        )

    if confianca < CONFIANCA_MEDIA:
        return Decisao(
            decisao=DecisaoTriagem.ESCALA,
            motivo=f"confianca baixa ({confianca:.2f} < {CONFIANCA_MEDIA})",
            confianca=confianca,
            sensivel=False,
        )

    if confianca < CONFIANCA_ALTA:
        return Decisao(
            decisao=DecisaoTriagem.RESPONDE_COM_OFERTA_HUMANA,
            motivo=f"confianca media ({confianca:.2f}): responde e oferece humano",
            confianca=confianca,
            sensivel=False,
        )

    return Decisao(
        decisao=DecisaoTriagem.RESPONDE,
        motivo=f"confianca alta ({confianca:.2f}) e assunto nao sensivel",
        confianca=confianca,
        sensivel=False,
    )


def calcular_confianca(
    confianca_classificacao: float,
    melhor_score_fonte: float,
    ancoragem_intacta: bool,
    degradado: bool,
) -> float:
    """Combina os sinais em um numero unico, explicavel.

    Nao e probabilidade calibrada e nao finge ser: e um score de decisao
    cujos componentes ficam registrados no log de auditoria, para que a
    escolha possa ser reconstruida depois.
    """
    if not ancoragem_intacta:
        # Afirmacao sem fonte derruba a confianca a zero, nao a reduz um
        # pouco. A resposta ja foi bloqueada; o score precisa refletir isso.
        return 0.0

    # A qualidade da fonte pesa mais que a certeza da classificacao:
    # errar a categoria costuma ser recuperavel, responder sem base nao.
    score = 0.35 * confianca_classificacao + 0.65 * melhor_score_fonte

    if degradado:
        # Operando sem LLM, casamento lexico nao e compreensao. O sistema
        # rebaixa a propria confianca em vez de esconder a degradacao.
        score *= 0.6

    return round(min(max(score, 0.0), 1.0), 4)
