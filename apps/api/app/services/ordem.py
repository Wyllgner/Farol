"""Ordens de Correcao (secao 6.2) — o laco do Andar 3.

Nao e sugestao em painel. E experimento com metodo: hipotese, evidencia,
acao, PREVISAO NUMERICA, data de medicao e resultado.

O FAROL nao da palpite. Faz uma previsao e volta em 30 dias para dizer se
acertou — e quando erra, descarta a hipotese e propoe a proxima. Um
Andar 3 que so acumulasse sugestoes sem medir seria o banner de novo, em
formato de dashboard.

Uma ordem por vez, priorizada por impacto, para caber na rotina de quem
ja esta sobrecarregado.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import SituacaoOrdem
from app.models import AgrupamentoCausa, OrdemCorrecao
from app.services import agrupamento as agrupamento_servico
from app.services import auditoria
from app.services.agrupamento import Cluster

# Prazo entre implementar e medir. Menos que isso mede ruido; mais que
# isso e tempo demais para descobrir que a hipotese estava errada.
JANELA_MEDICAO = timedelta(days=30)

# Margem de tolerancia sobre a previsao. Exigir acerto exato tornaria
# toda previsao um fracasso tecnico.
TOLERANCIA_ACERTO = 0.6

# Acoes sugeridas por aresta da jornada. Sao os defeitos que a literatura
# de usabilidade e o proprio desafio apontam como causadores de duvida.
ACOES_POR_ARESTA: dict[str, str] = {
    "inscricao": (
        "Reescrever o e-mail de boas-vindas com o passo a passo do primeiro "
        "acesso no corpo da mensagem, sem exigir clique em anexo."
    ),
    "primeiro_acesso": (
        "Mover a instrucao de configuracao do 2FA para a primeira tela apos "
        "o login, em vez de deixa-la no banner lateral."
    ),
    "configuracao_2fa": (
        "Adicionar ao lado do QR Code a orientacao sobre relogio do celular, "
        "que e a causa mais comum de codigo recusado."
    ),
    "localizacao_curso": (
        "Alterar o filtro padrao do painel para mostrar todos os cursos, e "
        "nao apenas os em andamento."
    ),
    "consumo_conteudo": (
        "Mover o link da webconferencia para o topo da pagina do curso, "
        "acima da dobra, com o horario ao lado."
    ),
    "webconferencia": (
        "Publicar a gravacao no mesmo local do link do encontro, sinalizando "
        "o prazo de 48 horas na propria pagina."
    ),
    "atividades": (
        "Sinalizar visualmente na lista de atividades quais estao apenas "
        "salvas como rascunho e ainda nao foram enviadas."
    ),
    "prazo": (
        "Exibir o prazo pessoal no topo da pagina do curso, com contagem "
        "regressiva, em vez de apenas no edital."
    ),
    "conclusao": (
        "Mostrar no Relatorio de Progresso exatamente qual requisito falta "
        "para liberar o certificado."
    ),
    "certificado": (
        "Enviar aviso automatico de certificado liberado com o link direto "
        "de emissao, em vez de esperar a pessoa voltar ao AVA."
    ),
}

ACAO_GENERICA = (
    "Revisar a pagina onde esta duvida nasce e tornar a informacao visivel "
    "sem exigir busca."
)


def _acao_para(aresta_origem: str | None) -> str:
    return ACOES_POR_ARESTA.get(aresta_origem or "", ACAO_GENERICA)


def _prever_queda(volume: int, concentracao: float) -> int:
    """Previsao de queda mensal.

    Deliberadamente conservadora: prever demais e a forma mais rapida de
    perder a credibilidade do Andar 3, e a credibilidade e o que faz a
    instituicao implementar a proxima ordem.

    Concentracao alta significa defeito localizado, que responde melhor a
    uma correcao pontual.
    """
    eficacia = 0.35 + 0.35 * concentracao
    return max(1, round(volume * eficacia))


async def propor(db: Session, cluster: Cluster) -> OrdemCorrecao | None:
    """Transforma um agrupamento em experimento verificavel."""
    registro = db.get(AgrupamentoCausa, cluster.id) if cluster.id else None
    if registro is None:
        return None

    ja_existe = db.scalar(
        select(OrdemCorrecao)
        .where(OrdemCorrecao.agrupamento_id == registro.id)
        .where(
            OrdemCorrecao.situacao.in_(
                [SituacaoOrdem.PENDENTE, SituacaoOrdem.EM_ANDAMENTO]
            )
        )
    )
    if ja_existe is not None:
        return ja_existe

    curso, concentracao = agrupamento_servico.concentracao_em_um_curso(cluster, db)
    aresta = cluster.aresta
    origem = aresta.origem if aresta else None

    taxa = float(aresta.taxa_travamento) if aresta else 0.0
    evidencia_partes = [f"{cluster.volume} casos agrupados por similaridade semantica"]
    if concentracao > 0 and curso:
        evidencia_partes.append(f"{concentracao:.0%} vem do curso '{curso}'")
    if aresta:
        evidencia_partes.append(
            f"taxa de travamento na aresta {aresta.origem} -> {aresta.destino} "
            f"e de {taxa:.0%}"
        )

    previsao = _prever_queda(cluster.volume, concentracao)

    ordem = OrdemCorrecao(
        agrupamento_id=registro.id,
        hipotese=(
            f"As pessoas travam em '{origem or 'ponto nao identificado'}' porque "
            f"{cluster.rotulo}."
        ),
        evidencia="; ".join(evidencia_partes) + ".",
        acao=_acao_para(origem),
        previsao_queda_mensal=previsao,
        # A data de medicao so faz sentido a partir da implementacao, e
        # por isso e definida quando a ordem e marcada como implementada.
        medir_em=None,
        situacao=SituacaoOrdem.PENDENTE,
        impacto_estimado=previsao,
        volume_base_mensal=cluster.volume,
    )
    db.add(ordem)
    db.flush()

    auditoria.registrar(
        db,
        "ordem_emitida",
        {
            "hipotese": ordem.hipotese,
            "previsao_queda_mensal": previsao,
            "volume_base": cluster.volume,
        },
    )
    return ordem


def em_destaque(db: Session) -> OrdemCorrecao | None:
    """A UMA ordem que o gestor deve olhar agora.

    Uma por vez e decisao de produto, nao limitacao: o risco classificado
    como maximo e ninguem implementar as correcoes, e uma lista de dez
    itens e uma lista que ninguem comeca.
    """
    return db.scalar(
        select(OrdemCorrecao)
        .where(OrdemCorrecao.situacao == SituacaoOrdem.PENDENTE)
        .order_by(OrdemCorrecao.impacto_estimado.desc(), OrdemCorrecao.criado_em)
    )


def marcar_implementada(
    db: Session, ordem: OrdemCorrecao, quando: date | None = None
) -> OrdemCorrecao:
    """Inicia a contagem para a medicao."""
    quando = quando or datetime.now(UTC).date()
    ordem.situacao = SituacaoOrdem.IMPLEMENTADA
    ordem.implementada_em = quando
    ordem.medir_em = quando + JANELA_MEDICAO
    db.flush()
    auditoria.registrar(
        db,
        "ordem_implementada",
        {"hipotese": ordem.hipotese, "medir_em": ordem.medir_em.isoformat()},
    )
    return ordem


def medir(db: Session, agora: datetime | None = None) -> dict:
    """Fecha o laco: a previsao se confirmou?

    Confirmada -> causa extinta. Refutada -> hipotese descartada e a
    proxima causa provavel entra na fila. Nao ha terceira opcao: uma
    previsao que "quase" acertou continua sendo uma previsao errada.
    """
    agora = agora or datetime.now(UTC)
    hoje = agora.date()

    vencidas = db.scalars(
        select(OrdemCorrecao)
        .where(OrdemCorrecao.situacao == SituacaoOrdem.IMPLEMENTADA)
        .where(OrdemCorrecao.medir_em.is_not(None))
        .where(OrdemCorrecao.medir_em <= hoje)
    ).all()

    confirmadas = descartadas = 0
    for ordem in vencidas:
        desde = datetime.combine(ordem.implementada_em, datetime.min.time(), tzinfo=UTC)
        volume_depois = agrupamento_servico.volume_no_periodo(
            db, ordem.agrupamento_id, desde=desde
        )
        queda = ordem.volume_base_mensal - volume_depois
        ordem.resultado_medido = queda

        if queda >= ordem.previsao_queda_mensal * TOLERANCIA_ACERTO:
            ordem.situacao = SituacaoOrdem.CONFIRMADA
            ordem.conclusao = (
                f"Queda de {queda} casos/mes contra previsao de "
                f"{ordem.previsao_queda_mensal}. Causa extinta."
            )
            confirmadas += 1
        else:
            ordem.situacao = SituacaoOrdem.DESCARTADA
            ordem.conclusao = (
                f"Queda de {queda} casos/mes contra previsao de "
                f"{ordem.previsao_queda_mensal}. Hipotese descartada: o "
                f"problema tem outra causa."
            )
            descartadas += 1

        auditoria.registrar(
            db,
            "ordem_medida",
            {
                "hipotese": ordem.hipotese,
                "previsto": ordem.previsao_queda_mensal,
                "medido": queda,
                "situacao": str(ordem.situacao),
            },
        )

    db.flush()
    return {"confirmadas": confirmadas, "descartadas": descartadas}


def acerto_das_previsoes(db: Session) -> dict:
    """Credibilidade do Andar 3: o quanto as previsoes acertam.

    Publicado inclusive quando e ruim — o valor da metrica esta em ela
    poder desmentir o proprio sistema.
    """
    medidas = db.scalars(
        select(OrdemCorrecao).where(OrdemCorrecao.resultado_medido.is_not(None))
    ).all()
    if not medidas:
        return {"medidas": 0, "acerto": None}

    acertos = sum(1 for o in medidas if o.situacao is SituacaoOrdem.CONFIRMADA)
    return {
        "medidas": len(medidas),
        "acerto": round(acertos / len(medidas), 4),
        "causas_extintas": acertos,
        "hipoteses_descartadas": len(medidas) - acertos,
    }
