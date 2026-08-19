"""Orcamento de Atencao e Verificacao de Efeito (secoes 4.3 e 4.4).

Mensagem nao solicitada de um Tribunal e uma faca de dois gumes. Por isso
o FAROL nao usa regra ingenua de frequencia: cada pessoa tem saldo
limitado de interrupcoes, e o saldo so e gasto nas mensagens de maior
valor esperado.

E toda mensagem proativa gera uma hipotese verificavel. Gatilho que nao
funciona e desativado automaticamente: o banner falhou porque ninguem
mediu o efeito dele.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import Categoria, EfeitoAntecipacao
from app.models import Caso, EventoProativo, Participante
from app.services import auditoria
from app.services.gatilhos import Gatilho, carregar


@dataclass(slots=True)
class Efetividade:
    chave: str
    confirmados: int
    refutados: int
    pendentes: int

    @property
    def amostra(self) -> int:
        return self.confirmados + self.refutados

    @property
    def taxa(self) -> float | None:
        """Antecipacao efetiva: atendimentos comprovadamente evitados.

        None enquanto nao ha amostra, nao inventamos numero para
        preencher painel.
        """
        if self.amostra == 0:
            return None
        return round(self.confirmados / self.amostra, 4)


# --------------------------------------------------------------------------
# Orcamento
# --------------------------------------------------------------------------


def valor_esperado(gatilho: Gatilho, taxa_medida: float | None) -> float:
    """probabilidade de evitar x custo do atendimento evitado.

    A taxa medida substitui a estimativa assim que existir amostra: a
    estimativa do YAML e chute inicial, o dado observado nao e.
    """
    probabilidade = (
        taxa_medida if taxa_medida is not None else gatilho.probabilidade_evitar
    )
    return round(probabilidade * gatilho.custo_atendimento_min, 3)


def pode_interromper(
    db: Session, participante: Participante, gatilho: Gatilho, valor: float
) -> tuple[bool, str]:
    """Decide se esta mensagem merece o saldo desta pessoa."""
    regras = carregar()

    if not participante.aceita_avisos:
        return False, "participante optou por nao receber avisos"

    if participante.saldo_atencao <= 0:
        return False, "saldo de atencao esgotado"

    if valor < regras.valor_esperado_minimo:
        return False, (
            f"valor esperado {valor} abaixo do minimo {regras.valor_esperado_minimo}"
        )

    if _ja_enviado(db, participante, gatilho):
        return False, "gatilho ja disparado para este participante"

    if _ignora_sistematicamente(db, participante):
        return False, "participante vem ignorando os avisos"

    return True, "dentro do orcamento"


def _ja_enviado(db: Session, participante: Participante, gatilho: Gatilho) -> bool:
    """O mesmo gatilho nao dispara duas vezes para a mesma pessoa."""
    return db.scalar(
        select(EventoProativo.id)
        .where(EventoProativo.participante_id == participante.id)
        .where(EventoProativo.gatilho == gatilho.chave)
        .limit(1)
    ) is not None


def _ignora_sistematicamente(db: Session, participante: Participante) -> bool:
    """Quem ignora recebe menos; quem interage recebe mais."""
    regras = carregar()
    refutados = db.scalar(
        select(func.count(EventoProativo.id))
        .where(EventoProativo.participante_id == participante.id)
        .where(EventoProativo.efeito == EfeitoAntecipacao.REFUTADO)
    )
    return (refutados or 0) >= regras.ignoradas_para_reduzir


def debitar(db: Session, participante: Participante) -> None:
    participante.saldo_atencao = max(0, participante.saldo_atencao - 1)
    db.flush()


PALAVRAS_OPTOUT = {"parar", "pare", "nao quero avisos", "sair"}


def eh_optout(texto: str) -> bool:
    """Opt-out reconhecido em qualquer canal, sem menu e sem link."""
    return texto.strip().lower() in PALAVRAS_OPTOUT


def desativar_avisos(db: Session, participante: Participante) -> None:
    """Opt-out. Uma palavra basta, e vale para sempre."""
    participante.aceita_avisos = False
    db.flush()
    auditoria.registrar(db, "optout_avisos", {"participante": str(participante.id)})


# --------------------------------------------------------------------------
# Verificacao de efeito
# --------------------------------------------------------------------------


def registrar_hipotese(
    db: Session,
    participante: Participante,
    gatilho: Gatilho,
    valor: float,
) -> EventoProativo:
    """Toda mensagem proativa nasce com uma hipotese verificavel.

    Ela nasce SEM relogio: `enviado_em` e `verificar_em` ficam nulos ate a
    entrega. Uma hipotese sobre uma mensagem que ninguem viu nao pode ser
    verificada, e muito menos confirmada.
    """
    regras = carregar()
    evento = EventoProativo(
        gatilho=gatilho.chave,
        participante_id=participante.id,
        valor_esperado=valor,
        hipotese=(
            f"Esta pessoa nao abrira atendimento sobre {gatilho.categoria} "
            f"nos proximos {regras.janela_dias} dias."
        ),
        efeito=EfeitoAntecipacao.PENDENTE,
    )
    db.add(evento)
    db.flush()
    return evento


def verificar_hipoteses(db: Session, agora: datetime | None = None) -> dict:
    """Confere as hipoteses vencidas e registra o resultado.

    Confirmada = a pessoa nao abriu atendimento sobre o assunto: o
    atendimento foi evitado. Refutada = abriu mesmo assim.
    """
    agora = agora or datetime.now(UTC)
    regras = carregar()

    vencidas = db.scalars(
        select(EventoProativo)
        .where(EventoProativo.efeito == EfeitoAntecipacao.PENDENTE)
        .where(EventoProativo.verificar_em <= agora)
    ).all()

    confirmados = refutados = 0
    for evento in vencidas:
        gatilho = regras.por_chave(evento.gatilho)
        if gatilho is None:
            continue

        abriu = _abriu_atendimento(db, evento, gatilho.categoria)
        evento.efeito = (
            EfeitoAntecipacao.REFUTADO if abriu else EfeitoAntecipacao.CONFIRMADO
        )
        if abriu:
            refutados += 1
        else:
            confirmados += 1

        auditoria.registrar(
            db,
            "hipotese_verificada",
            {
                "gatilho": evento.gatilho,
                "hipotese": evento.hipotese,
                "efeito": str(evento.efeito),
            },
        )

    db.flush()
    return {"confirmadas": confirmados, "refutadas": refutados}


def _abriu_atendimento(db: Session, evento: EventoProativo, categoria: str) -> bool:
    """A pessoa procurou o setor sobre este assunto depois do aviso?"""
    try:
        alvo = Categoria(categoria)
    except ValueError:
        return False

    return db.scalar(
        select(Caso.id)
        .where(Caso.participante_id == evento.participante_id)
        .where(Caso.categoria == alvo)
        .where(Caso.criado_em >= evento.enviado_em)
        .where(Caso.criado_em <= evento.verificar_em)
        .limit(1)
    ) is not None


def efetividade(db: Session, chave: str) -> Efetividade:
    contagem = dict(
        db.execute(
            select(EventoProativo.efeito, func.count(EventoProativo.id))
            .where(EventoProativo.gatilho == chave)
            # So entra na conta o que chegou a alguem. Mensagem na fila
            # nao mede nada: creditar efeito a ela seria dizer que o
            # gatilho evitou um atendimento sem ter falado com ninguem.
            .where(EventoProativo.enviado_em.is_not(None))
            .group_by(EventoProativo.efeito)
        ).all()
    )
    return Efetividade(
        chave=chave,
        confirmados=contagem.get(EfeitoAntecipacao.CONFIRMADO, 0),
        refutados=contagem.get(EfeitoAntecipacao.REFUTADO, 0),
        pendentes=contagem.get(EfeitoAntecipacao.PENDENTE, 0),
    )


def esta_ativo(db: Session, gatilho: Gatilho) -> tuple[bool, str]:
    """Gatilho inefetivo e desativado automaticamente (secao 4.4).

    A desativacao e DERIVADA da medicao, nao um estado guardado: nao ha
    como o painel discordar do que o motor faz, e um gatilho que volte a
    funcionar volta a rodar sozinho.
    """
    if not gatilho.ativo:
        return False, "desativado manualmente no arquivo de regras"

    regras = carregar()
    medida = efetividade(db, gatilho.chave)

    # Desativar por causa de dois casos seria o mesmo erro do banner, so
    # que ao contrario: concluir sem medir.
    if medida.amostra < regras.amostra_minima:
        return True, f"em observacao ({medida.amostra}/{regras.amostra_minima})"

    if medida.taxa is not None and medida.taxa < regras.limiar_efetividade:
        return False, (
            f"desativado automaticamente: antecipacao efetiva {medida.taxa:.0%} "
            f"abaixo do limiar {regras.limiar_efetividade:.0%}"
        )

    return True, f"efetivo ({medida.taxa:.0%})" if medida.taxa is not None else "ativo"
