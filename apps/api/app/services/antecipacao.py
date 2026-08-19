"""Andar 1: ANTECIPAR (secao 4).

Percorre as matriculas, avalia os gatilhos ativos, deixa o orcamento de
atencao decidir o que merece a interrupcao, envia e registra a hipotese
que sera verificada depois.

A ordem importa: avaliamos todos os candidatos de uma pessoa ANTES de
gastar saldo, para que o saldo va para a mensagem de maior valor, e nao
para a primeira que passou no filtro.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import OutboundMessage
from app.channels.mirror import adaptador
from app.enums import Canal, Direcao
from app.models import Matricula, Participante
from app.services import atencao, auditoria, entrega, gatilhos
from app.services.conversa import obter_ou_criar, registrar_mensagem
from app.services.gatilhos import Gatilho

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class Candidata:
    matricula: Matricula
    gatilho: Gatilho
    valor: float


async def rodar(db: Session, agora: datetime | None = None) -> dict:
    """Uma passada completa do motor de antecipacao."""
    agora = agora or datetime.now(UTC)
    regras = gatilhos.carregar()

    ativos: list[Gatilho] = []
    desativados: dict[str, str] = {}
    for gatilho in regras.gatilhos:
        ligado, motivo = atencao.esta_ativo(db, gatilho)
        (ativos.append(gatilho) if ligado else desativados.update({gatilho.chave: motivo}))

    enviados: dict[str, int] = {}
    barrados: dict[str, int] = {}

    for participante in db.scalars(select(Participante)).all():
        candidatas = _candidatas(db, participante, ativos, agora)
        if not candidatas:
            continue

        # Gasta o orcamento na de maior valor esperado, nao na primeira.
        melhor = max(candidatas, key=lambda c: c.valor)
        autorizado, motivo = atencao.pode_interromper(
            db, participante, melhor.gatilho, melhor.valor
        )

        if not autorizado:
            barrados[motivo] = barrados.get(motivo, 0) + 1
            continue

        await _enviar(db, participante, melhor, agora)
        enviados[melhor.gatilho.chave] = enviados.get(melhor.gatilho.chave, 0) + 1

    db.flush()
    return {
        "enviados": enviados,
        "total_enviado": sum(enviados.values()),
        "barrados_pelo_orcamento": barrados,
        "gatilhos_desativados": desativados,
    }


def _candidatas(
    db: Session, participante: Participante, ativos: list[Gatilho], agora: datetime
) -> list[Candidata]:
    matriculas = db.scalars(
        select(Matricula).where(Matricula.participante_id == participante.id)
    ).all()

    candidatas = []
    for matricula in matriculas:
        for gatilho in ativos:
            if not gatilhos.avaliar(gatilho, matricula, agora):
                continue
            medida = atencao.efetividade(db, gatilho.chave)
            candidatas.append(
                Candidata(
                    matricula=matricula,
                    gatilho=gatilho,
                    valor=atencao.valor_esperado(gatilho, medida.taxa),
                )
            )
    return candidatas


async def _enviar(
    db: Session, participante: Participante, candidata: Candidata, agora: datetime
) -> None:
    """Coloca a mensagem na fila do canal da pessoa.

    Nao debita o orcamento de atencao nem inicia a hipotese: as duas
    coisas dependem de a mensagem ter CHEGADO, e isso quem sabe e a
    entrega (`services.entrega`). Interromper so custa quando de fato
    interrompe, e so vale medir o que a pessoa viu.
    """
    texto = gatilhos.montar_mensagem(candidata.gatilho, candidata.matricula, agora)
    canal = participante.canal_preferido or Canal.WHATSAPP
    # O identificador tem que ser o MESMO que o canal usa para reconhecer
    # a pessoa (`identidade.resolver`), senao a mensagem proativa vai para
    # uma conversa paralela que o widget nunca vai abrir. So o canal de
    # e-mail e enderecado por e-mail.
    handle = (
        participante.email if canal is Canal.EMAIL else participante.telefone
    ) or ""

    conversa = obter_ou_criar(db, canal, handle)

    # A hipotese nasce sem relogio: `verificar_em` fica nulo ate a entrega,
    # e a verificacao ignora o que ainda nao comecou a contar.
    evento = atencao.registrar_hipotese(
        db, participante, candidata.gatilho, candidata.valor
    )
    mensagem = registrar_mensagem(
        db, conversa, Direcao.SAIDA, texto, candidata.gatilho.acoes, entregue=False
    )
    mensagem.evento_proativo_id = evento.id
    db.flush()

    auditoria.registrar(
        db,
        "mensagem_proativa",
        {
            "gatilho": candidata.gatilho.chave,
            "canal": str(canal),
            "valor_esperado": candidata.valor,
            "hipotese": evento.hipotese,
        },
    )

    # Tentativa de entrega imediata. O espelho entrega agora se a aba
    # estiver aberta; o widget do AVA entrega quando a pessoa abrir. Nos
    # dois casos, quem confirma a entrega inicia a hipotese.
    if canal is Canal.WHATSAPP:
        recibo = await adaptador.send(
            handle,
            OutboundMessage(texto=texto, acoes_rapidas=candidata.gatilho.acoes),
        )
        if recibo.entregue:
            entrega.confirmar(db, [mensagem], agora)


def painel(db: Session) -> list[dict]:
    """Estado de cada gatilho, para a tela de transparencia."""
    linhas = []
    for gatilho in gatilhos.carregar().gatilhos:
        medida = atencao.efetividade(db, gatilho.chave)
        ligado, motivo = atencao.esta_ativo(db, gatilho)
        linhas.append(
            {
                "chave": gatilho.chave,
                "titulo": gatilho.titulo,
                "ativo": ligado,
                "motivo": motivo,
                "enviados": medida.amostra + medida.pendentes,
                "confirmados": medida.confirmados,
                "refutados": medida.refutados,
                "pendentes": medida.pendentes,
                "antecipacao_efetiva": medida.taxa,
                "valor_esperado": atencao.valor_esperado(gatilho, medida.taxa),
            }
        )
    return linhas
