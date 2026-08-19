"""Fila do servidor (secoes 5.6, 5.7 e 5.8).

A fila nao e ordenada por chegada nem por urgencia generica, e sim pela
CONSEQUENCIA de nao atender. Isso alinha o trabalho ao que a instituicao
efetivamente perde.

Nada sai automaticamente em nome da instituicao: o rascunho existe para
ser revisado, e o envio e sempre um ato humano.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Categoria, SituacaoCaso, SituacaoDocumento
from app.models import Caso, DocumentoConhecimento
from app.services import auditoria
from app.services.conhecimento import indexar

# Janela de deduplicacao entre canais (secao 5.9). A mesma pessoa
# perguntando o mesmo assunto por WhatsApp e por e-mail e UM caso, e o
# retrabalho por duplicidade que o proprio formulario do setor relata.
JANELA_DEDUPLICACAO = timedelta(hours=6)

# Validade padrao do conhecimento aprovado por servidor. Conteudo sem
# prazo vira divida: alguem precisa reencontra-lo um dia.
VALIDADE_APROVACAO = timedelta(days=180)


def listar(db: Session, incluir_encerrados: bool = False) -> list[Caso]:
    """Casos escalados, do mais caro de ignorar para o menos."""
    situacoes = [SituacaoCaso.ESCALADO]
    if incluir_encerrados:
        situacoes.append(SituacaoCaso.ENCERRADO)

    return list(
        db.scalars(
            select(Caso)
            .where(Caso.situacao.in_(situacoes))
            .where(Caso.duplicado_de_id.is_(None))
            .order_by(Caso.score_consequencia.desc().nullslast(), Caso.criado_em)
        ).all()
    )


def obter(db: Session, caso_id: uuid.UUID) -> Caso | None:
    return db.get(Caso, caso_id)


def assumir(db: Session, caso: Caso, servidor: str) -> Caso:
    """Marca quem esta cuidando. O cronometro da fila comeca aqui."""
    caso.assumido_por = servidor
    caso.assumido_em = datetime.now(UTC)
    db.flush()
    auditoria.registrar(db, "caso_assumido", {"servidor": servidor}, caso_id=caso.id)
    return caso


def responder(db: Session, caso: Caso, texto: str, servidor: str) -> Caso:
    """Envia a resposta revisada pelo servidor.

    O texto que sai e o que o servidor escreveu ou editou: nunca o
    rascunho cru. A revisao humana e o contrato com a instituicao.
    """
    caso.resposta_enviada = texto
    caso.situacao = SituacaoCaso.ENCERRADO
    caso.encerrado_em = datetime.now(UTC)
    caso.assumido_por = caso.assumido_por or servidor
    db.flush()

    auditoria.registrar(
        db,
        "resposta_humana",
        {
            "servidor": servidor,
            "texto": texto,
            "editou_o_rascunho": texto.strip() != (caso.rascunho_resposta or "").strip(),
        },
        caso_id=caso.id,
    )
    return caso


async def aprovar_como_conhecimento(
    db: Session,
    caso: Caso,
    titulo: str,
    servidor: str,
    conteudo: str | None = None,
) -> DocumentoConhecimento:
    """Transforma a resposta do servidor em fonte oficial citavel (F20).

    E assim que a base cresce: pela operacao normal, com curadoria humana.
    A cada escalonamento o sistema fica melhor, e a curva de escalonamento
    cai sozinha.
    """
    texto = (conteudo or caso.resposta_enviada or "").strip()
    if not texto:
        raise ValueError("nao ha resposta para aprovar como conhecimento")

    documento = DocumentoConhecimento(
        titulo=titulo,
        conteudo=texto,
        dono=servidor,
        # Nasce com prazo: conhecimento sem validade e o proximo documento
        # vencido respondendo com o carimbo da Escola.
        valido_ate=(datetime.now(UTC) + VALIDADE_APROVACAO).date(),
        situacao=SituacaoDocumento.VIGENTE,
        aprovado_por_servidor=True,
    )
    db.add(documento)
    db.flush()

    await indexar(db, documento)

    auditoria.registrar(
        db,
        "conhecimento_aprovado",
        {"documento": titulo, "servidor": servidor},
        caso_id=caso.id,
    )
    return documento


def encontrar_duplicado(
    db: Session,
    participante_id: uuid.UUID | None,
    categoria: Categoria,
    agora: datetime | None = None,
) -> Caso | None:
    """Mesma pessoa, mesmo assunto, janela curta: e o mesmo caso.

    Sem participante identificado nao ha como deduplicar com seguranca: 
    e juntar casos de pessoas diferentes seria pior que duplicar.
    """
    if participante_id is None:
        return None

    agora = agora or datetime.now(UTC)
    return db.scalar(
        select(Caso)
        .where(Caso.participante_id == participante_id)
        .where(Caso.categoria == categoria)
        .where(Caso.situacao != SituacaoCaso.ENCERRADO)
        .where(Caso.duplicado_de_id.is_(None))
        .where(Caso.criado_em >= agora - JANELA_DEDUPLICACAO)
        .order_by(Caso.criado_em.desc())
    )


def marcar_duplicado(db: Session, caso: Caso, original: Caso) -> None:
    """Une o caso novo ao original, somando o sinal em vez de duplicar."""
    caso.duplicado_de_id = original.id
    # O contato repetido por outro canal e sinal de urgencia real: a
    # pessoa se deu ao trabalho de procurar duas vezes.
    original.score_consequencia = (original.score_consequencia or 0) + 1
    db.flush()
    auditoria.registrar(
        db,
        "caso_deduplicado",
        {"original": str(original.id), "canal_novo": str(caso.canal)},
        caso_id=caso.id,
    )


def metricas(db: Session) -> dict:
    """Numeros da fila para o painel."""
    abertos = db.scalars(
        select(Caso).where(Caso.situacao == SituacaoCaso.ESCALADO)
    ).all()
    encerrados = db.scalars(
        select(Caso).where(Caso.situacao == SituacaoCaso.ENCERRADO)
    ).all()

    return {
        "na_fila": len(abertos),
        "encerrados": len(encerrados),
        "com_orientacao_padrao_falha": sum(
            1 for c in abertos if c.orientacao_padrao_falhou
        ),
        "sensiveis": sum(1 for c in abertos if c.sensivel),
    }
