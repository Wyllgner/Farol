"""Descoberta de causa-raiz (secao 6.1).

Agrupa as demandas por similaridade semantica, cruza com o grafo da
jornada e localiza a ARESTA onde a duvida nasce — nao a categoria
generica, mas o ponto exato de falha.

A diferenca importa: "senha" e uma categoria; "as pessoas nao encontram
o link da webconferencia no modulo 2" e uma causa. So a segunda pode ser
corrigida.

Usa HDBSCAN porque ele descobre agrupamentos que ninguem categorizou
previamente e nao exige dizer de antemao quantos existem — o numero de
causas-raiz e justamente o que nao se sabe.
"""

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgrupamentoCausa, ArestaJornada, Caso, Matricula
from app.services import auditoria

logger = logging.getLogger(__name__)

# Abaixo disso nao ha padrao, ha coincidencia. Emitir ordem de correcao
# baseada em dois casos e o oposto do que o Andar 3 promete.
TAMANHO_MINIMO_CLUSTER = 3


@dataclass(slots=True)
class Cluster:
    # Id do registro no banco. Casar cluster com agrupamento pelo rotulo
    # seria fragil: rotulo nao e unico, e dois agrupamentos distintos
    # podem receber o mesmo nome.
    id: uuid.UUID | None
    rotulo: str
    casos: list[Caso]
    aresta: ArestaJornada | None
    cursos: list[str]

    @property
    def volume(self) -> int:
        return len(self.casos)


async def indexar_pergunta(db: Session, caso: Caso, pergunta: str) -> None:
    """Guarda a pergunta e seu vetor no momento do atendimento."""
    from app.llm import obter_provider

    caso.pergunta = pergunta
    try:
        caso.vetor_pergunta = (await obter_provider().embutir([pergunta]))[0]
    except Exception:  # noqa: BLE001
        # Sem vetor o caso apenas nao entra na analise de causa-raiz.
        # Derrubar o atendimento por causa disso seria desproporcional.
        logger.warning("nao foi possivel vetorizar a pergunta do caso %s", caso.id)
    db.flush()


def _casos_analisaveis(db: Session) -> list[Caso]:
    return list(
        db.scalars(
            select(Caso)
            .where(Caso.vetor_pergunta.is_not(None))
            .where(Caso.duplicado_de_id.is_(None))
            .where(Caso.sensivel.is_(False))
        ).all()
    )


def _clusterizar(vetores: np.ndarray) -> np.ndarray:
    """HDBSCAN sobre distancia de cosseno.

    Rotulo -1 significa ruido: o algoritmo diz "isto nao pertence a
    agrupamento nenhum" em vez de forcar tudo num grupo. Perguntas
    isoladas nao viram causa-raiz.
    """
    from sklearn.cluster import HDBSCAN

    modelo = HDBSCAN(
        min_cluster_size=TAMANHO_MINIMO_CLUSTER,
        metric="cosine",
        # Sem isso, um unico caso distante viraria cluster proprio.
        min_samples=2,
    )
    return modelo.fit_predict(vetores)


def _aresta_predominante(db: Session, casos: list[Caso]) -> ArestaJornada | None:
    """Onde, no grafo, estavam as pessoas que perguntaram isso.

    E a ponte entre "o que perguntam" e "onde travam" — e o mesmo grafo
    que o Andar 1 usa, o que evita duas verdades sobre a mesma jornada.
    """
    contagem: Counter[str] = Counter()
    for caso in casos:
        if caso.participante_id is None:
            continue
        matriculas = db.scalars(
            select(Matricula).where(Matricula.participante_id == caso.participante_id)
        ).all()
        for matricula in matriculas:
            if matricula.aresta_atual_id:
                contagem[str(matricula.aresta_atual_id)] += 1

    if not contagem:
        return None
    id_mais_comum, _ = contagem.most_common(1)[0]
    return db.get(ArestaJornada, id_mais_comum)


def _cursos_afetados(db: Session, casos: list[Caso]) -> list[str]:
    titulos: Counter[str] = Counter()
    for caso in casos:
        if caso.participante_id is None:
            continue
        for matricula in db.scalars(
            select(Matricula).where(Matricula.participante_id == caso.participante_id)
        ).all():
            titulos[matricula.curso.titulo] += 1
    return [titulo for titulo, _ in titulos.most_common()]


async def _rotular(casos: list[Caso]) -> str:
    """Nomeia o agrupamento em linguagem de pessoa.

    O rotulo e o que o gestor le no Radar. "categoria: webconferencia"
    nao ajuda ninguem a agir; "nao encontram o link da webconferencia"
    aponta para uma correcao.
    """
    from app.llm import obter_provider

    perguntas = [c.pergunta for c in casos if c.pergunta][:12]
    if not perguntas:
        return "duvidas sem texto registrado"

    provider = obter_provider()
    if provider.nome == "fallback":
        return f"duvidas sobre {casos[0].categoria}"

    try:
        resposta = await provider.gerar_ancorado(
            "Resuma em ate 10 palavras o problema comum a estas perguntas de "
            "participantes de um curso, em portugues, comecando por um verbo "
            "no infinitivo ou por 'nao'. Responda so o resumo.",
            [{"id": f"p{i}", "texto": p} for i, p in enumerate(perguntas)],
        )
        if resposta.texto.strip():
            return resposta.texto.strip().rstrip(".")[:300]
    except Exception:  # noqa: BLE001
        logger.warning("falha ao rotular agrupamento; usando rotulo derivado")

    return f"duvidas sobre {casos[0].categoria}"


async def agrupar(db: Session) -> list[Cluster]:
    """Executa a descoberta de causa-raiz sobre os casos acumulados."""
    casos = _casos_analisaveis(db)
    if len(casos) < TAMANHO_MINIMO_CLUSTER:
        return []

    vetores = np.array([caso.vetor_pergunta for caso in casos], dtype=np.float32)
    rotulos = _clusterizar(vetores)

    # Agrupamentos sao recalculados por completo: manter os antigos ao lado
    # dos novos faria o painel somar a mesma causa duas vezes.
    for antigo in db.scalars(select(AgrupamentoCausa)).all():
        db.delete(antigo)
    db.flush()

    clusters: list[Cluster] = []
    for rotulo_numerico in sorted(set(rotulos)):
        if rotulo_numerico == -1:
            continue  # ruido: pergunta isolada nao e causa-raiz

        membros = [caso for caso, r in zip(casos, rotulos, strict=True) if r == rotulo_numerico]
        aresta = _aresta_predominante(db, membros)
        cursos = _cursos_afetados(db, membros)
        rotulo = await _rotular(membros)

        registro = AgrupamentoCausa(
            rotulo=rotulo,
            volume=len(membros),
            aresta_origem_id=aresta.id if aresta else None,
            cursos_afetados=cursos,
        )
        db.add(registro)
        db.flush()

        for caso in membros:
            caso.agrupamento_id = registro.id

        clusters.append(
            Cluster(
                id=registro.id,
                rotulo=rotulo,
                casos=membros,
                aresta=aresta,
                cursos=cursos,
            )
        )

    db.flush()
    auditoria.registrar(
        db,
        "agrupamento_executado",
        {
            "casos_analisados": len(casos),
            "agrupamentos": len(clusters),
            "ruido": int((rotulos == -1).sum()),
        },
    )
    return sorted(clusters, key=lambda c: c.volume, reverse=True)


def concentracao_em_um_curso(cluster: Cluster, db: Session) -> tuple[str, float]:
    """Quanto do agrupamento vem de um unico curso.

    Concentracao alta e o sinal mais util que existe: significa que o
    defeito nao esta na plataforma inteira, esta em um lugar especifico
    que alguem consegue arrumar hoje.
    """
    contagem: Counter[str] = Counter()
    for caso in cluster.casos:
        if caso.participante_id is None:
            continue
        for matricula in db.scalars(
            select(Matricula).where(Matricula.participante_id == caso.participante_id)
        ).all():
            contagem[matricula.curso.titulo] += 1

    if not contagem:
        return "", 0.0
    curso, quantidade = contagem.most_common(1)[0]
    return curso, round(quantidade / sum(contagem.values()), 4)


def volume_no_periodo(
    db: Session, agrupamento_id, desde: datetime | None = None
) -> int:
    """Quantos casos deste agrupamento no periodo — a linha de base.

    Sem uma linha de base explicita nao ha como dizer que o volume caiu:
    so daria para dizer que ele esta alto ou baixo, que e outra coisa.
    """
    consulta = select(func.count(Caso.id)).where(Caso.agrupamento_id == agrupamento_id)
    if desde is not None:
        consulta = consulta.where(Caso.criado_em >= desde)
    return db.scalar(consulta) or 0
