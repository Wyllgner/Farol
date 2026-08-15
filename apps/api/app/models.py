"""As 12 entidades da secao 11 do documento mestre.

Convencao: nomes de tabela e coluna em portugues, acompanhando o dominio do
documento. O codigo do motor fala a mesma lingua que a banca.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base
from app.enums import (
    Canal,
    Categoria,
    ContratoResolucao,
    DecisaoTriagem,
    Direcao,
    EfeitoAntecipacao,
    NivelIdentidade,
    Perfil,
    SituacaoCaso,
    SituacaoCertificado,
    SituacaoDocumento,
    SituacaoOrdem,
)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --------------------------------------------------------------------------
# Participantes, cursos e matriculas
# --------------------------------------------------------------------------


class Participante(Base, TimestampMixin):
    __tablename__ = "participante"

    id: Mapped[uuid.UUID] = _pk()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(32), unique=True)
    perfil: Mapped[Perfil] = mapped_column(String(24), nullable=False)
    canal_preferido: Mapped[Canal] = mapped_column(String(24), default=Canal.WHATSAPP)
    nivel_identidade: Mapped[NivelIdentidade] = mapped_column(
        String(24), default=NivelIdentidade.ANONIMO, nullable=False
    )

    # Secao 4.3 — Orcamento de Atencao. Saldo de interrupcoes ainda disponivel.
    saldo_atencao: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    aceita_avisos: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    matriculas: Mapped[list["Matricula"]] = relationship(back_populates="participante")


class Curso(Base, TimestampMixin):
    __tablename__ = "curso"

    id: Mapped[uuid.UUID] = _pk()
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    prazo_conclusao: Mapped[date] = mapped_column(Date, nullable=False)
    # Modulos e webconferencias sao estrutura de conteudo, nao entidade de negocio:
    # ficam como JSON para manter o schema enxuto no MVP.
    modulos: Mapped[list] = mapped_column(JSON, default=list)
    webconferencias: Mapped[list] = mapped_column(JSON, default=list)


class Matricula(Base, TimestampMixin):
    __tablename__ = "matricula"

    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participante.id", ondelete="CASCADE"), nullable=False
    )
    curso_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curso.id", ondelete="CASCADE"), nullable=False
    )
    data_inscricao: Mapped[date] = mapped_column(Date, nullable=False)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progresso: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    dois_fatores_configurado: Mapped[bool] = mapped_column(Boolean, default=False)
    prazo_pessoal: Mapped[date | None] = mapped_column(Date)
    situacao_certificado: Mapped[SituacaoCertificado] = mapped_column(
        String(24), default=SituacaoCertificado.NAO_ELEGIVEL
    )
    # Onde a pessoa esta no grafo da jornada (secao 4.1). Compartilhado
    # entre o Andar 1 e o Andar 3 — e o que elimina duplicacao conceitual.
    aresta_atual_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aresta_jornada.id", ondelete="SET NULL")
    )

    participante: Mapped[Participante] = relationship(back_populates="matriculas")
    curso: Mapped[Curso] = relationship()
    aresta_atual: Mapped["ArestaJornada | None"] = relationship()

    __table_args__ = (Index("ix_matricula_part_curso", "participante_id", "curso_id", unique=True),)


# --------------------------------------------------------------------------
# Base de conhecimento
# --------------------------------------------------------------------------


class DocumentoConhecimento(Base, TimestampMixin):
    __tablename__ = "documento_conhecimento"

    id: Mapped[uuid.UUID] = _pk()
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    dono: Mapped[str] = mapped_column(String(200), nullable=False)
    # Secao 7.2 — sem fonte valida e vigente, o FAROL escala.
    valido_ate: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[SituacaoDocumento] = mapped_column(
        String(24), default=SituacaoDocumento.VIGENTE, nullable=False
    )
    taxa_resolucao: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ultima_citacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprovado_por_servidor: Mapped[bool] = mapped_column(Boolean, default=False)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = _pk()
    documento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documento_conhecimento.id", ondelete="CASCADE"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    vetor: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim))

    documento: Mapped[DocumentoConhecimento] = relationship(back_populates="chunks")


# --------------------------------------------------------------------------
# Conversas
# --------------------------------------------------------------------------


class Conversa(Base, TimestampMixin):
    __tablename__ = "conversa"

    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participante.id", ondelete="SET NULL")
    )
    canal: Mapped[Canal] = mapped_column(String(24), nullable=False)
    # Identificador do interlocutor no canal (telefone, e-mail, sessao do widget).
    # Existe separado de participante_id porque no nivel anonimo nao ha cadastro.
    handle_canal: Mapped[str] = mapped_column(String(200), nullable=False)
    # Estado do fluxo guiado em andamento (secao 5.4). Vive na conversa e
    # nao em memoria: acompanhar alguem por cinco passos nao pode depender
    # de o processo continuar de pe.
    fluxo_estado: Mapped[dict | None] = mapped_column(JSON)
    # Contexto da pagina, quando o canal e o widget do AVA.
    contexto_pagina: Mapped[str | None] = mapped_column(String(300))

    mensagens: Mapped[list["Mensagem"]] = relationship(
        back_populates="conversa", cascade="all, delete-orphan"
    )


class Mensagem(Base, TimestampMixin):
    __tablename__ = "mensagem"

    id: Mapped[uuid.UUID] = _pk()
    conversa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversa.id", ondelete="CASCADE"), nullable=False
    )
    direcao: Mapped[Direcao] = mapped_column(String(16), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    # Respostas rapidas oferecidas junto da mensagem (secao 12.2: uma acao por mensagem).
    acoes_rapidas: Mapped[list] = mapped_column(JSON, default=list)

    conversa: Mapped[Conversa] = relationship(back_populates="mensagens")


# --------------------------------------------------------------------------
# Casos e o Contrato de Resolucao
# --------------------------------------------------------------------------


class Caso(Base, TimestampMixin):
    __tablename__ = "caso"

    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participante.id", ondelete="SET NULL")
    )
    conversa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversa.id", ondelete="SET NULL")
    )
    canal: Mapped[Canal] = mapped_column(String(24), nullable=False)
    categoria: Mapped[Categoria] = mapped_column(String(32), nullable=False)
    sensivel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confianca: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    decisao_triagem: Mapped[DecisaoTriagem | None] = mapped_column(String(32))
    situacao: Mapped[SituacaoCaso] = mapped_column(
        String(24), default=SituacaoCaso.ABERTO, nullable=False
    )
    dossie: Mapped[dict | None] = mapped_column(JSON)
    rascunho_resposta: Mapped[str | None] = mapped_column(Text)

    # Secao 5.5 — o laco. Um caso so fecha com confirmacao da pessoa.
    contrato_resolucao: Mapped[ContratoResolucao] = mapped_column(
        String(24), default=ContratoResolucao.ABERTO, nullable=False
    )
    contrato_perguntado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A informacao mais valiosa que existe quando a pessoa diz "nao resolveu".
    orientacao_padrao_falhou: Mapped[bool] = mapped_column(Boolean, default=False)

    # Secao 5.7 — a fila e ordenada por consequencia, nao por chegada.
    score_consequencia: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # Secao 5.9 — deduplicacao entre canais aponta para o caso original.
    duplicado_de_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("caso.id", ondelete="SET NULL")
    )


# --------------------------------------------------------------------------
# Andar 1 — antecipacao
# --------------------------------------------------------------------------


class EventoProativo(Base, TimestampMixin):
    __tablename__ = "evento_proativo"

    id: Mapped[uuid.UUID] = _pk()
    gatilho: Mapped[str] = mapped_column(String(64), nullable=False)
    participante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participante.id", ondelete="CASCADE"), nullable=False
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valor_esperado: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    # Secao 4.4 — toda mensagem proativa gera uma hipotese verificavel.
    hipotese: Mapped[str] = mapped_column(Text, nullable=False)
    verificar_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    efeito: Mapped[EfeitoAntecipacao] = mapped_column(
        String(24), default=EfeitoAntecipacao.PENDENTE, nullable=False
    )


class ArestaJornada(Base, TimestampMixin):
    __tablename__ = "aresta_jornada"

    id: Mapped[uuid.UUID] = _pk()
    origem: Mapped[str] = mapped_column(String(64), nullable=False)
    destino: Mapped[str] = mapped_column(String(64), nullable=False)
    taxa_travamento: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal(0))
    volume: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_aresta_origem_destino", "origem", "destino", unique=True),)


# --------------------------------------------------------------------------
# Andar 3 — extincao de causa
# --------------------------------------------------------------------------


class AgrupamentoCausa(Base, TimestampMixin):
    __tablename__ = "agrupamento_causa"

    id: Mapped[uuid.UUID] = _pk()
    rotulo: Mapped[str] = mapped_column(String(300), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    aresta_origem_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aresta_jornada.id", ondelete="SET NULL")
    )
    cursos_afetados: Mapped[list] = mapped_column(JSON, default=list)


class OrdemCorrecao(Base, TimestampMixin):
    """Secao 6.2 — nao e sugestao em painel, e experimento com metodo."""

    __tablename__ = "ordem_correcao"

    id: Mapped[uuid.UUID] = _pk()
    agrupamento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agrupamento_causa.id", ondelete="SET NULL")
    )
    hipotese: Mapped[str] = mapped_column(Text, nullable=False)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    acao: Mapped[str] = mapped_column(Text, nullable=False)
    # O FAROL nao da palpite: faz uma previsao numerica e volta para conferir.
    previsao_queda_mensal: Mapped[int] = mapped_column(Integer, nullable=False)
    medir_em: Mapped[date | None] = mapped_column(Date)
    resultado_medido: Mapped[int | None] = mapped_column(Integer)
    situacao: Mapped[SituacaoOrdem] = mapped_column(
        String(24), default=SituacaoOrdem.PENDENTE, nullable=False
    )
    impacto_estimado: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------


class LogAuditoria(Base, TimestampMixin):
    """Secao 7.5 — append-only. Requisito nao negociavel em ambiente judiciario.

    A imutabilidade nao e garantida so por convencao: a migration revoga
    UPDATE e DELETE nesta tabela para a role da aplicacao.
    """

    __tablename__ = "log_auditoria"

    id: Mapped[uuid.UUID] = _pk()
    caso_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("caso.id", ondelete="SET NULL"))
    etapa: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
