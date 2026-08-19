"""Dossie do escalonamento (secao 5.6) e fila por consequencia (secao 5.7).

Quando escala, o servidor nao recebe "oi, preciso de ajuda". Recebe o caso
montado, legivel em 10 segundos: critico no topo, rascunho pronto.

Nada e enviado automaticamente em nome da instituicao: o rascunho existe
para ser revisado, nunca para ser disparado.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Canal, Categoria, Direcao
from app.models import Conversa, Mensagem
from app.services.ancoragem import Ancoragem
from app.services.identidade import Identidade
from app.services.triagem import Decisao

# Quantos turnos entram na transcricao. O servidor precisa do fio da
# conversa, nao do arquivo morto dela: vinte turnos cobrem o atendimento
# inteiro nos casos reais e ainda cabem em uma tela.
LIMITE_DE_TURNOS = 20

# Peso por categoria no calculo de consequencia. Nao e urgencia generica:
# e o que a instituicao efetivamente perde se ninguem atender.
PESO_CATEGORIA: dict[Categoria, float] = {
    Categoria.PRAZO: 3.0,
    Categoria.CERTIFICADO: 2.5,
    Categoria.ACESSO: 2.0,
    Categoria.DOIS_FATORES: 2.0,
    Categoria.SENSIVEL: 3.0,
    Categoria.RECLAMACAO: 2.5,
    Categoria.WEBCONFERENCIA: 1.5,
    Categoria.INSCRICAO: 1.5,
    Categoria.SENHA: 1.5,
    Categoria.LOCALIZACAO_CURSO: 1.0,
    Categoria.CONTEUDO: 1.0,
    Categoria.OUTROS: 0.5,
}


def transcrever(
    db: Session,
    *,
    canal: Canal,
    handle: str,
    participante_id: uuid.UUID | None,
    limite: int = LIMITE_DE_TURNOS,
) -> list[dict]:
    """Transcricao consolidada da conversa, unificada entre canais.

    O servidor recebia so a ultima pergunta. Uma pergunta fora do fio da
    conversa e ilegivel: "e o meu?" nao significa nada sem os dois turnos
    anteriores, e quem atende ficava reconstruindo de cabeca o que o
    sistema ja tinha registrado.

    A unificacao entre canais nao e refinamento: a mesma pessoa comeca no
    widget do AVA e continua no WhatsApp, e sem juntar as duas pontas o
    servidor le metade do caso e responde o que ja foi respondido.
    """
    consulta = select(Mensagem).join(Conversa, Mensagem.conversa_id == Conversa.id)

    if participante_id is not None:
        # Identificada: tudo que a pessoa trocou com a Escola, em qualquer canal.
        consulta = consulta.where(Conversa.participante_id == participante_id)
    else:
        # Anonima: nao ha a quem unificar. Fica no par canal+handle, porque
        # cruzar so por handle arriscaria juntar duas pessoas diferentes.
        consulta = consulta.where(
            Conversa.canal == canal, Conversa.handle_canal == handle
        )

    mensagens = db.scalars(
        consulta.order_by(Mensagem.criado_em.desc()).limit(limite)
    ).all()

    return [
        {
            "quem": "participante" if m.direcao is Direcao.ENTRADA else "farol",
            "canal": str(m.conversa.canal),
            "texto": m.conteudo,
            "em": m.criado_em.isoformat() if m.criado_em else None,
            # Proativa que ainda nao chegou nao e parte do que foi dito: o
            # servidor precisa saber que ela esta na fila, e nao supor que
            # a pessoa ja leu.
            "entregue": m.direcao is Direcao.ENTRADA or m.entregue_em is not None,
        }
        # A consulta desce no tempo para pegar os ULTIMOS turnos; a leitura
        # sobe, porque conversa se le do comeco.
        for m in reversed(mensagens)
    ]


def montar(
    *,
    pergunta: str,
    categoria: Categoria,
    identidade: Identidade,
    estado: dict,
    trechos: list[dict],
    decisao: Decisao,
    ancoragem: Ancoragem,
    rascunho: str,
    orientacao_padrao_falhou: bool = False,
    transcricao: list[dict] | None = None,
) -> dict:
    """Monta o caso para leitura humana rapida."""
    return {
        # Critico no topo: e o que o servidor le primeiro.
        "resumo": _resumir(
            categoria, identidade, estado, decisao, orientacao_padrao_falhou
        ),
        "motivo_do_escalonamento": decisao.motivo,
        "orientacao_padrao_falhou": orientacao_padrao_falhou,
        "categoria": str(categoria),
        "sensivel": decisao.sensivel,
        "nivel_identidade": str(identidade.nivel),
        "pergunta": pergunta,
        # Secao 5.6: transcricao consolidada, unificada entre canais.
        "transcricao": transcricao or [],
        "estado_do_participante": estado,
        "fontes_consultadas": [
            {"documento": t["documento"], "dono": t["dono"], "score": t["score"]}
            for t in trechos
        ],
        "confianca": decisao.confianca,
        "ancoragem": {
            "intacta": ancoragem.intacta,
            "motivo": ancoragem.motivo,
        },
        # Editavel pelo servidor antes do envio. Sempre.
        "rascunho_sugerido": rascunho,
        "montado_em": datetime.now(UTC).isoformat(),
    }


def _resumir(
    categoria: Categoria,
    identidade: Identidade,
    estado: dict,
    decisao: Decisao,
    orientacao_padrao_falhou: bool = False,
) -> str:
    quem = estado.get("primeiro_nome") or "Participante nao identificado"

    # A informacao mais valiosa que existe vai primeiro: a orientacao
    # oficial ja foi tentada e nao funcionou para esta pessoa.
    if orientacao_padrao_falhou:
        return (
            f"{quem}: {categoria}: a orientacao padrao ja foi tentada e "
            f"nao resolveu. Precisa de atendimento humano."
        )

    if decisao.sensivel:
        return f"{quem}: assunto sensivel ({categoria}), encaminhado por politica."

    curso = (estado.get("cursos") or [{}])[0]
    if curso.get("dias_ate_o_prazo") is not None and curso["dias_ate_o_prazo"] <= 3:
        return (
            f"{quem}: {categoria}, prazo em {curso['dias_ate_o_prazo']} dia(s) "
            f"e progresso {curso.get('progresso_pct', 0):.0f}%."
        )
    return f"{quem}: {categoria}, sem fonte suficiente para responder."


def score_consequencia(categoria: Categoria, estado: dict) -> float:
    """Ordena a fila pelo que a instituicao perde se ninguem atender.

    Prazo vence em 2 dias e a pessoa esta travada -> topo.
    Duvida sobre certificado de curso concluido ha 3 meses -> base.
    """
    score = PESO_CATEGORIA.get(categoria, 0.5)

    for curso in estado.get("cursos", []):
        dias = curso.get("dias_ate_o_prazo")
        if dias is not None and dias >= 0:
            # Quanto mais perto do prazo, mais cara a demora. Cresce rapido
            # porque o dano nao e linear: no dia seguinte ao prazo, e total.
            score += max(0.0, 6.0 - dias)

        if curso.get("progresso_pct", 100) < 70 and dias is not None and dias <= 7:
            score += 2.0  # travado e com prazo curto

        if curso.get("nunca_acessou"):
            score += 1.5

    return round(score, 2)
