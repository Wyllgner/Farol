"""Console de Demonstracao (secao 12.1).

Trata a apresentacao como funcionalidade, porque e onde o produto e
julgado. Sem isto, demonstrar os lacos exigiria comandos de banco na
frente da banca, e um laco que so pode ser mostrado por SQL nao foi
demonstrado.

Regra que vale para tudo aqui: o console NAO tem caminho proprio. Ele
chama exatamente as mesmas funcoes que o agendador chamaria. O que se
demonstra e o que roda.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import SituacaoCertificado
from app.models import Matricula
from app.services import auditoria

logger = logging.getLogger(__name__)

# Avancar o tempo e recuar os carimbos de data: do ponto de vista do
# sistema, e a mesma coisa, e nao exige um relogio falso espalhado pelo
# codigo: o que faria o caminho da demo divergir do caminho real.
TABELAS_COM_TEMPO: list[tuple[str, list[str]]] = [
    ("caso", ["criado_em", "contrato_perguntado_em", "assumido_em", "encerrado_em"]),
    ("evento_proativo", ["criado_em", "enviado_em", "verificar_em"]),
    ("conversa", ["criado_em"]),
    ("mensagem", ["criado_em"]),
    ("matricula", ["ultimo_acesso"]),
    # log_auditoria fica DE FORA de proposito: a tabela e append-only por
    # trigger no banco, e nem o console de demonstracao pode reescrever a
    # auditoria. O log registra quando as coisas de fato aconteceram: 
    # move-lo no tempo seria falsificar o registro, que e exatamente o que
    # a imutabilidade existe para impedir.
]

# Datas puras (sem hora) precisam de intervalo em dias.
COLUNAS_DATA: list[tuple[str, list[str]]] = [
    ("ordem_correcao", ["implementada_em", "medir_em"]),
    ("matricula", ["prazo_pessoal"]),
]


@dataclass(slots=True)
class Cenario:
    """Um participante e o estado que o torna interessante na demo."""

    telefone: str
    nome: str
    curso: str
    rotulo: str
    detalhe: str


def avancar_tempo(db: Session, dias: int) -> dict:
    """Move o relogio do mundo ficticio para a frente."""
    if dias <= 0:
        raise ValueError("informe um numero de dias maior que zero")

    afetadas = 0
    for tabela, colunas in TABELAS_COM_TEMPO:
        for coluna in colunas:
            resultado = db.execute(
                text(
                    f"UPDATE {tabela} SET {coluna} = {coluna} - "
                    f"make_interval(days => :dias) WHERE {coluna} IS NOT NULL"
                ),
                {"dias": dias},
            )
            afetadas += resultado.rowcount or 0

    for tabela, colunas in COLUNAS_DATA:
        for coluna in colunas:
            resultado = db.execute(
                text(
                    f"UPDATE {tabela} SET {coluna} = {coluna} - :dias "
                    f"WHERE {coluna} IS NOT NULL"
                ),
                {"dias": dias},
            )
            afetadas += resultado.rowcount or 0

    db.flush()
    auditoria.registrar(db, "demo_avancou_tempo", {"dias": dias, "registros": afetadas})
    return {"dias": dias, "registros_ajustados": afetadas}


def alternar_ensaio(db: Session, ativo: bool) -> dict:
    """Liga ou desliga o Modo Ensaio ao vivo.

    A mudanca vale para o processo em execucao. Em producao isso seria
    configuracao versionada, nao um botao, mas na apresentacao precisa
    ser um botao.
    """
    settings.modo_ensaio = ativo
    auditoria.registrar(db, "demo_modo_ensaio", {"ativo": ativo})
    return {"modo_ensaio": ativo}


def cenarios(db: Session) -> list[Cenario]:
    """Participantes escolhidos por estado, nao por ordem alfabetica.

    Quem apresenta precisa achar em um clique a pessoa que aciona cada
    comportamento: procurar na lista de 60 durante a demo e como nao ter
    o console.
    """
    encontrados: list[Cenario] = []
    ja_usados: set[str] = set()

    def adicionar(matricula: Matricula, rotulo: str, detalhe: str) -> bool:
        """Devolve se de fato incluiu: quem chama precisa saber para
        continuar procurando em vez de desistir no primeiro repetido."""
        telefone = matricula.participante.telefone
        if not telefone or telefone in ja_usados:
            return False
        ja_usados.add(telefone)
        encontrados.append(
            Cenario(
                telefone=telefone,
                nome=matricula.participante.nome,
                curso=matricula.curso.titulo,
                rotulo=rotulo,
                detalhe=detalhe,
            )
        )
        return True

    matriculas = db.scalars(select(Matricula)).all()

    procuras: list[tuple[str, str, object]] = [
        (
            "2FA pendente",
            "aciona a oferta de acompanhamento guiado",
            lambda m: not m.dois_fatores_configurado and m.ultimo_acesso is not None,
        ),
        (
            "certificado liberado",
            "a resposta cita o estado individual desta pessoa",
            lambda m: m.situacao_certificado is SituacaoCertificado.LIBERADO,
        ),
        (
            "nunca acessou",
            "alvo do gatilho de primeiro acesso",
            lambda m: m.ultimo_acesso is None,
        ),
        (
            "prazo apertado",
            "alvo do gatilho de prazo",
            lambda m: float(m.progresso) < 70 and m.prazo_pessoal is not None,
        ),
        (
            "optou por nao receber",
            "barrado pelo orcamento de atencao",
            lambda m: not m.participante.aceita_avisos,
        ),
    ]

    for rotulo, detalhe, condicao in procuras:
        for m in matriculas:
            if condicao(m) and adicionar(m, rotulo, detalhe):
                break

    return encontrados


def restaurar_saldos(db: Session) -> dict:
    """Devolve o saldo de atencao a todos.

    Depois de um ensaio, o orcamento esta gasto e os gatilhos param de
    disparar. Sem isto, a segunda passagem da demo mostraria zero
    mensagens e pareceria defeito.
    """
    total = db.execute(
        text(
            "UPDATE participante SET saldo_atencao = :saldo, aceita_avisos = true"
        ),
        {"saldo": 4},
    ).rowcount
    db.execute(text("DELETE FROM evento_proativo"))
    db.flush()
    auditoria.registrar(db, "demo_restaurou_saldos", {"participantes": total})
    return {"participantes": total or 0}


def estado(db: Session) -> dict:
    """Resumo do mundo, para o console mostrar antes e depois de cada acao."""
    def contar(consulta: str) -> int:
        return db.scalar(text(consulta)) or 0

    return {
        "modo_ensaio": settings.modo_ensaio,
        "participantes": contar("SELECT count(*) FROM participante"),
        "casos": contar("SELECT count(*) FROM caso"),
        "casos_na_fila": contar("SELECT count(*) FROM caso WHERE situacao='escalado'"),
        "casos_em_ensaio": contar("SELECT count(*) FROM caso WHERE em_ensaio"),
        "mensagens_proativas": contar("SELECT count(*) FROM evento_proativo"),
        "hipoteses_pendentes": contar(
            "SELECT count(*) FROM evento_proativo WHERE efeito='pendente'"
        ),
        "agrupamentos": contar("SELECT count(*) FROM agrupamento_causa"),
        "ordens_pendentes": contar(
            "SELECT count(*) FROM ordem_correcao WHERE situacao='pendente'"
        ),
        "documentos": contar("SELECT count(*) FROM documento_conhecimento"),
        "categorias_liberadas": contar(
            "SELECT count(*) FROM liberacao_categoria WHERE liberada"
        ),
    }
