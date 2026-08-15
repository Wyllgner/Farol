"""Modo Ensaio (secao 7.1).

A funcionalidade que torna a adocao institucionalmente possivel.

Nas primeiras semanas o FAROL roda em modo sombra: GERA a resposta, mas
NAO envia. O servidor ve o que ele teria respondido, aprova ou corrige.
So depois de atingir uma taxa de acerto acordada uma categoria e liberada
para resposta automatica — categoria por categoria.

Nenhuma instituicao do Judiciario liga no dia 1 um sistema que fala em
nome da Casa. Nao pedimos confianca: pedimos duas semanas de observacao.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import Categoria
from app.models import Caso, LiberacaoCategoria
from app.services import auditoria

# Taxa de acerto a partir da qual faz sentido propor a liberacao.
TAXA_PARA_LIBERAR = 0.90

# Amostra minima antes de propor. Liberar com tres casos revisados seria
# trocar a observacao por otimismo.
AMOSTRA_MINIMA = 10

AVISO_AO_PARTICIPANTE = (
    "Recebi sua mensagem. Neste momento as respostas da Escola passam por "
    "conferencia de um servidor antes do envio, entao voce recebera o "
    "retorno por aqui em breve."
)


@dataclass(slots=True)
class Desempenho:
    categoria: Categoria
    revisados: int
    aprovados: int
    liberada: bool

    @property
    def taxa_acerto(self) -> float | None:
        """None enquanto nao ha revisao — nao inventamos numero."""
        if self.revisados == 0:
            return None
        return round(self.aprovados / self.revisados, 4)

    @property
    def pode_liberar(self) -> bool:
        taxa = self.taxa_acerto
        return (
            not self.liberada
            and self.revisados >= AMOSTRA_MINIMA
            and taxa is not None
            and taxa >= TAXA_PARA_LIBERAR
        )


def ativo() -> bool:
    return settings.modo_ensaio


def categoria_liberada(db: Session, categoria: Categoria) -> bool:
    registro = db.scalar(
        select(LiberacaoCategoria).where(LiberacaoCategoria.categoria == categoria)
    )
    return bool(registro and registro.liberada)


def deve_reter(db: Session, categoria: Categoria) -> bool:
    """A resposta desta categoria pode sair sozinha?

    Com o Modo Ensaio ligado, so sai o que ja foi liberado explicitamente.
    O padrao e reter — o silencio nunca autoriza.
    """
    if not ativo():
        return False
    return not categoria_liberada(db, categoria)


def liberar(db: Session, categoria: Categoria, servidor: str) -> LiberacaoCategoria:
    registro = db.scalar(
        select(LiberacaoCategoria).where(LiberacaoCategoria.categoria == categoria)
    )
    if registro is None:
        registro = LiberacaoCategoria(categoria=categoria)
        db.add(registro)

    registro.liberada = True
    registro.liberada_em = datetime.now(UTC)
    registro.liberada_por = servidor
    db.flush()

    auditoria.registrar(
        db,
        "categoria_liberada",
        {"categoria": str(categoria), "servidor": servidor},
    )
    return registro


def recolher(db: Session, categoria: Categoria, servidor: str) -> None:
    """Devolve a categoria ao modo sombra.

    Existe porque a liberacao precisa ser reversivel: descobrir um erro
    depois de liberar nao pode exigir desligar o sistema inteiro.
    """
    registro = db.scalar(
        select(LiberacaoCategoria).where(LiberacaoCategoria.categoria == categoria)
    )
    if registro is not None:
        registro.liberada = False
        registro.liberada_em = None
        db.flush()
        auditoria.registrar(
            db, "categoria_recolhida", {"categoria": str(categoria), "servidor": servidor}
        )


def registrar_revisao(db: Session, caso: Caso, aprovado: bool, servidor: str) -> None:
    """O servidor julgou o que o FAROL teria respondido.

    Aprovado significa "eu teria enviado isso". E dessa razao que sai a
    taxa de acerto, e por isso ela mede a resposta gerada, nao a resposta
    final entregue.
    """
    caso.aprovado_em_ensaio = aprovado
    db.flush()
    auditoria.registrar(
        db,
        "revisao_ensaio",
        {"aprovado": aprovado, "servidor": servidor, "categoria": str(caso.categoria)},
        caso_id=caso.id,
    )


def desempenho(db: Session) -> list[Desempenho]:
    """Taxa de acerto por categoria — a base da decisao de liberar."""
    linhas = db.execute(
        select(
            Caso.categoria,
            func.count(Caso.id),
            func.count(Caso.id).filter(Caso.aprovado_em_ensaio.is_(True)),
        )
        .where(Caso.em_ensaio.is_(True))
        .where(Caso.aprovado_em_ensaio.is_not(None))
        .group_by(Caso.categoria)
    ).all()
    contagem = {categoria: (total, ok) for categoria, total, ok in linhas}

    liberadas = {
        registro.categoria
        for registro in db.scalars(select(LiberacaoCategoria)).all()
        if registro.liberada
    }

    resultado = []
    for categoria in Categoria:
        revisados, aprovados = contagem.get(categoria, (0, 0))
        resultado.append(
            Desempenho(
                categoria=categoria,
                revisados=revisados,
                aprovados=aprovados,
                liberada=categoria in liberadas,
            )
        )
    return resultado
