"""Contrato de Resolucao (secao 5.5).

O laco do Andar 2, e a funcionalidade que mais claramente separa o FAROL
de um chatbot: cada atendimento e um contrato aberto que so fecha com
confirmacao.

O que isso resolve e o ERRO SILENCIOSO — o caso perigoso em que o sistema
tem confianca alta, responde errado, e ninguem percebe. Um chatbot
comum encerraria ali, contabilizaria como sucesso e seguiria em frente.

Regra que nao pode ser afrouxada: no "nao resolveu", o FAROL NAO repete a
resposta. Ele escala, e o dossie carrega a informacao mais valiosa que
existe — a orientacao padrao ja foi tentada e falhou para esta pessoa.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ContratoResolucao, SituacaoCaso
from app.models import Caso, DocumentoConhecimento
from app.services import auditoria

# Quanto esperar antes de perguntar. Cedo demais interrompe quem ainda
# esta executando; tarde demais e a pessoa ja desistiu ou esqueceu.
ESPERA_PARA_PERGUNTAR = timedelta(hours=2)

# Depois disso o caso vai para fila de baixa prioridade. Nao insistimos:
# perguntar duas vezes ja seria a interrupcao que o produto quer evitar.
ESPERA_ATE_DESISTIR = timedelta(days=2)

SIM = "Sim, resolveu"
NAO = "Nao resolveu"

PERGUNTAS = {
    "certificado": "Conseguiu emitir o certificado?",
    "2fa": "Conseguiu configurar o acesso em dois fatores?",
    "acesso": "Conseguiu entrar na plataforma?",
    "senha": "Conseguiu redefinir a senha?",
    "webconferencia": "Conseguiu entrar na webconferencia?",
    "localizacao_curso": "Conseguiu encontrar o curso?",
}
PERGUNTA_PADRAO = "Aquilo que voce perguntou ficou resolvido?"


def pergunta_de(categoria: str) -> str:
    """Pergunta concreta, no vocabulario do caso, nunca generica."""
    return PERGUNTAS.get(categoria, PERGUNTA_PADRAO)


def abrir(caso: Caso, resposta: str, trechos: list[dict]) -> None:
    """Todo caso respondido nasce com contrato aberto."""
    caso.resposta_enviada = resposta
    caso.fontes_usadas = [
        {"chunk_id": t["id"], "documento": t["documento"]} for t in trechos
    ]
    caso.contrato_resolucao = ContratoResolucao.ABERTO


def pendentes_de_pergunta(db: Session, agora: datetime | None = None) -> list[Caso]:
    """Casos respondidos que ja podem receber a pergunta de verificacao."""
    agora = agora or datetime.now(UTC)
    return list(
        db.scalars(
            select(Caso)
            .where(Caso.situacao == SituacaoCaso.RESPONDIDO)
            .where(Caso.contrato_resolucao == ContratoResolucao.ABERTO)
            .where(Caso.contrato_perguntado_em.is_(None))
            .where(Caso.criado_em <= agora - ESPERA_PARA_PERGUNTAR)
        ).all()
    )


def marcar_perguntado(db: Session, caso: Caso, agora: datetime | None = None) -> str:
    """Registra que a pergunta saiu. Ela sai UMA vez, nunca duas."""
    caso.contrato_perguntado_em = agora or datetime.now(UTC)
    db.flush()
    auditoria.registrar(
        db, "contrato_perguntado", {"categoria": str(caso.categoria)}, caso_id=caso.id
    )
    return pergunta_de(str(caso.categoria))


def caso_aguardando(db: Session, participante_id) -> Caso | None:
    """Caso desta pessoa que ja recebeu a pergunta e espera resposta."""
    if participante_id is None:
        return None
    return db.scalar(
        select(Caso)
        .where(Caso.participante_id == participante_id)
        .where(Caso.contrato_resolucao == ContratoResolucao.ABERTO)
        .where(Caso.contrato_perguntado_em.is_not(None))
        .order_by(Caso.contrato_perguntado_em.desc())
    )


def confirmar(db: Session, caso: Caso) -> None:
    """A pessoa disse que resolveu: encerra e valida a fonte."""
    caso.contrato_resolucao = ContratoResolucao.CONFIRMADO
    caso.situacao = SituacaoCaso.ENCERRADO
    caso.encerrado_em = datetime.now(UTC)
    _ajustar_peso_das_fontes(db, caso, resolveu=True)
    db.flush()
    auditoria.registrar(db, "contrato_confirmado", {}, caso_id=caso.id)


def registrar_falha(db: Session, caso: Caso) -> Caso:
    """A pessoa disse que nao resolveu.

    Aqui esta a regra central: NAO repetimos a resposta. Escalamos, e o
    servidor recebe explicitamente que a orientacao padrao falhou — e a
    informacao mais util que ele pode ter antes de escrever.
    """
    caso.contrato_resolucao = ContratoResolucao.FALHOU
    caso.situacao = SituacaoCaso.ESCALADO
    caso.orientacao_padrao_falhou = True

    dossie_atual = dict(caso.dossie or {})
    dossie_atual.update(
        {
            "resumo": (
                f"{_nome_de(db, caso, dossie_atual)} — a resposta automatica foi "
                f"entregue e a pessoa confirmou que NAO resolveu."
            ),
            "motivo_do_escalonamento": (
                "contrato de resolucao: participante respondeu que nao resolveu"
            ),
            "orientacao_padrao_falhou": True,
            "resposta_que_falhou": caso.resposta_enviada,
            "fontes_que_falharam": caso.fontes_usadas or [],
        }
    )
    caso.dossie = dossie_atual

    # A fonte que nao resolveu perde peso. E o inicio do rebaixamento
    # automatico por taxa de "nao resolveu" (secao 7.2).
    _ajustar_peso_das_fontes(db, caso, resolveu=False)
    db.flush()
    auditoria.registrar(
        db,
        "contrato_falhou",
        {"resposta_que_falhou": caso.resposta_enviada},
        caso_id=caso.id,
    )
    return caso


def expirar_sem_retorno(db: Session, agora: datetime | None = None) -> int:
    """Sem resposta apos o prazo: fila de baixa prioridade, sem insistir."""
    agora = agora or datetime.now(UTC)
    casos = db.scalars(
        select(Caso)
        .where(Caso.contrato_resolucao == ContratoResolucao.ABERTO)
        .where(Caso.contrato_perguntado_em.is_not(None))
        .where(Caso.contrato_perguntado_em <= agora - ESPERA_ATE_DESISTIR)
    ).all()

    for caso in casos:
        caso.contrato_resolucao = ContratoResolucao.SEM_RETORNO
        # Continua aberto, mas no fim da fila: silencio nao e confirmacao.
        caso.score_consequencia = 0
        auditoria.registrar(db, "contrato_sem_retorno", {}, caso_id=caso.id)

    db.flush()
    return len(casos)


def _nome_de(db: Session, caso: Caso, dossie: dict) -> str:
    """Casos respondidos nao tem dossie montado; busca o nome do cadastro.

    O servidor le a fila por resumo — um 'Participante' generico o obriga
    a abrir o caso so para descobrir com quem esta falando.
    """
    estado = dossie.get("estado_do_participante") or {}
    if nome := estado.get("primeiro_nome"):
        return nome

    if caso.participante_id:
        from app.models import Participante

        participante = db.get(Participante, caso.participante_id)
        if participante:
            return participante.nome.split()[0]

    return "Participante nao identificado"


def _ajustar_peso_das_fontes(db: Session, caso: Caso, resolveu: bool) -> None:
    """Media movel da taxa de resolucao efetiva de cada documento.

    A base aprende com o uso: fonte que resolve sobe, fonte que falha
    desce, e o rebaixamento por desempenho deixa de depender de alguem
    lembrar de revisar.
    """
    titulos = {f["documento"] for f in (caso.fontes_usadas or [])}
    if not titulos:
        return

    for documento in db.scalars(
        select(DocumentoConhecimento).where(DocumentoConhecimento.titulo.in_(titulos))
    ).all():
        atual = float(documento.taxa_resolucao or 50)
        observado = 100.0 if resolveu else 0.0
        # Peso baixo no novo dado: um unico "nao resolveu" nao deve
        # derrubar um documento bom, mas uma sequencia deve.
        documento.taxa_resolucao = round(atual * 0.8 + observado * 0.2, 2)
