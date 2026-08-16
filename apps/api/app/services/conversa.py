"""Conversa: persistencia do dialogo e roteamento do fluxo guiado.

Esta camada fica entre o canal e o motor de resolucao. Ela decide se a
mensagem continua um fluxo guiado em andamento ou se vai para o pipeline
normal — e essa decisao vem antes de qualquer chamada de modelo, porque
quem esta no passo 3 de 5 respondendo "nao consegui" nao esta fazendo
uma pergunta nova.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import InboundMessage, OutboundMessage
from app.enums import Canal, Direcao, SituacaoCaso
from app.models import Caso, Conversa, Mensagem
from app.services import (
    agrupamento,
    atencao,
    auditoria,
    contrato,
    dossie,
    fila,
    fluxo_guiado,
)
from app.services.ancoragem import Ancoragem
from app.services.atendimento import atender
from app.services.estado import montar as montar_estado
from app.services.fluxo_guiado import Estado
from app.services.identidade import resolver
from app.services.triagem import Decisao, decidir

OFERTA_FLUXO = "Quer que eu te acompanhe passo a passo?"
ACEITE = "Sim, me acompanhe"


def obter_ou_criar(db: Session, canal: Canal, handle: str) -> Conversa:
    conversa = db.scalar(
        select(Conversa).where(
            Conversa.canal == canal, Conversa.handle_canal == handle
        )
    )
    if conversa is None:
        identidade = resolver(db, canal, handle)
        conversa = Conversa(
            canal=canal,
            handle_canal=handle,
            participante_id=identidade.participante.id
            if identidade.participante
            else None,
        )
        db.add(conversa)
        db.flush()
    elif conversa.participante_id is None:
        # A conversa pode ter nascido antes de a pessoa existir no cadastro
        # (ou ter perdido o vinculo). Reconhecer de novo evita que ela siga
        # anonima para sempre so por ter falado com o FAROL antes.
        identidade = resolver(db, canal, handle)
        if identidade.participante is not None:
            conversa.participante_id = identidade.participante.id
            db.flush()
    return conversa


def registrar_mensagem(
    db: Session,
    conversa: Conversa,
    direcao: Direcao,
    conteudo: str,
    acoes: list[str] | None = None,
) -> None:
    db.add(
        Mensagem(
            conversa_id=conversa.id,
            direcao=direcao,
            conteudo=conteudo,
            acoes_rapidas=acoes or [],
        )
    )
    db.flush()


async def processar(db: Session, entrada: InboundMessage) -> OutboundMessage:
    """Ponto unico de entrada, qualquer que seja o canal."""
    conversa = obter_ou_criar(db, entrada.canal, entrada.handle)

    if pagina := entrada.contexto.get("pagina"):
        conversa.contexto_pagina = pagina

    registrar_mensagem(db, conversa, Direcao.ENTRADA, entrada.texto)

    saida = await _rotear(db, conversa, entrada)

    registrar_mensagem(
        db, conversa, Direcao.SAIDA, saida.texto, saida.acoes_rapidas
    )
    return saida


async def _rotear(
    db: Session, conversa: Conversa, entrada: InboundMessage
) -> OutboundMessage:
    estado_fluxo = Estado.de_json(conversa.fluxo_estado)

    # 1. Fluxo em andamento tem prioridade sobre o pipeline.
    if estado_fluxo is not None:
        return _continuar_fluxo(db, conversa, estado_fluxo, entrada.texto)

    # 2. Opt-out vem antes de tudo. Quem pediu para parar de receber nao
    #    pode ser respondido com mais uma mensagem sobre outro assunto.
    if atencao.eh_optout(entrada.texto):
        return _processar_optout(db, conversa)

    # 3. Resposta ao Contrato de Resolucao. Vem antes do pipeline: quem
    #    responde "nao resolveu" nao esta fazendo uma pergunta nova.
    if resposta := _responder_contrato(db, conversa, entrada.texto):
        return resposta

    # 4. Aceite explicito da oferta feita na mensagem anterior.
    if entrada.texto.strip().lower() == ACEITE.lower():
        return _iniciar_fluxo(db, conversa, fluxo_guiado.FLUXO_2FA.chave)

    # 5. Pipeline normal.
    resultado = await atender(
        db, canal=entrada.canal, handle=entrada.handle, pergunta=entrada.texto
    )

    if resultado.caso is not None:
        resultado.caso.conversa_id = conversa.id
        # Guarda a pergunta e seu vetor: e o insumo do Andar 3, e o
        # momento do atendimento e a unica hora em que o texto original
        # esta a mao.
        await agrupamento.indexar_pergunta(db, resultado.caso, entrada.texto)
        if not resultado.foi_entregue:
            _deduplicar(db, resultado.caso)
        else:
            # Todo caso respondido nasce com contrato aberto: ele so
            # fecha quando a pessoa confirmar que resolveu.
            contrato.abrir(resultado.caso, resultado.resposta, resultado.trechos)
        db.flush()

    acoes = list(resultado.acoes_rapidas)
    texto = resultado.resposta

    # Procedimento que ja falhou como texto merece acompanhamento, nao
    # mais texto. So oferecemos quando o estado mostra que faz sentido.
    if resultado.foi_entregue:
        estado_participante = montar_estado(db, resultado.identidade)
        if fluxo_guiado.deve_oferecer(resultado.categoria, estado_participante):
            texto = f"{texto}\n\n{OFERTA_FLUXO}"
            acoes = [ACEITE, *acoes]

    return OutboundMessage(
        texto=texto,
        acoes_rapidas=acoes,
        fontes=[
            {"documento": t["documento"], "dono": t["dono"]} for t in resultado.trechos
        ],
    )


def _responder_contrato(
    db: Session, conversa: Conversa, texto: str
) -> OutboundMessage | None:
    """Processa 'sim, resolveu' ou 'nao resolveu' de um contrato aberto."""
    resposta = texto.strip().lower()
    if resposta not in (contrato.SIM.lower(), contrato.NAO.lower()):
        return None

    caso = contrato.caso_aguardando(db, conversa.participante_id)
    if caso is None:
        return None

    if resposta == contrato.SIM.lower():
        contrato.confirmar(db, caso)
        return OutboundMessage(
            texto="Que bom. Qualquer outra duvida, e so chamar.",
            acoes_rapidas=[],
        )

    # A regra central do laco: nao repetimos a resposta que ja falhou.
    contrato.registrar_falha(db, caso)
    _deduplicar(db, caso)
    return OutboundMessage(
        texto=(
            "Obrigado por avisar. Nao vou repetir a mesma orientacao — se ela "
            "nao funcionou, o caso precisa de um servidor. Ja encaminhei com o "
            "registro do que foi tentado e voce recebera retorno por aqui."
        ),
        acoes_rapidas=[],
    )


def _processar_optout(db: Session, conversa: Conversa) -> OutboundMessage:
    """Uma palavra basta, e vale para sempre."""
    from app.models import Participante

    if conversa.participante_id:
        participante = db.get(Participante, conversa.participante_id)
        if participante:
            atencao.desativar_avisos(db, participante)

    return OutboundMessage(
        texto=(
            "Pronto, nao vou mais mandar avisos automaticos. Voce continua "
            "podendo perguntar aqui quando precisar."
        ),
        acoes_rapidas=[],
    )


def _deduplicar(db: Session, caso: Caso) -> None:
    """Mesma pessoa e mesmo assunto em janela curta viram um caso so."""
    original = fila.encontrar_duplicado(db, caso.participante_id, caso.categoria)
    if original is not None and original.id != caso.id:
        fila.marcar_duplicado(db, caso, original)


def _iniciar_fluxo(db: Session, conversa: Conversa, chave: str) -> OutboundMessage:
    passo = fluxo_guiado.iniciar(chave)
    conversa.fluxo_estado = passo.estado.como_json() if passo.estado else None
    db.flush()
    auditoria.registrar(db, "fluxo_iniciado", {"fluxo": chave})
    return OutboundMessage(texto=passo.texto, acoes_rapidas=passo.acoes_rapidas)


def _continuar_fluxo(
    db: Session, conversa: Conversa, estado: Estado, resposta: str
) -> OutboundMessage:
    passo = fluxo_guiado.avancar(estado, resposta)
    conversa.fluxo_estado = passo.estado.como_json() if passo.estado else None
    db.flush()

    auditoria.registrar(
        db,
        "fluxo_passo",
        {
            "fluxo": estado.fluxo,
            "passo": estado.passo,
            "resposta": resposta,
            "escalou": passo.escalar,
            "concluido": passo.concluido,
        },
    )

    if passo.escalar:
        _escalar_fluxo(db, conversa, estado)

    return OutboundMessage(texto=passo.texto, acoes_rapidas=passo.acoes_rapidas)


def _escalar_fluxo(db: Session, conversa: Conversa, estado: Estado) -> None:
    """Escalonamento por falha repetida no acompanhamento.

    O dossie carrega a informacao mais valiosa que existe: em que passo
    exato a pessoa travou, e que a orientacao padrao ja falhou ali.
    """
    from app.models import Caso

    fluxo = fluxo_guiado.FLUXOS[estado.fluxo]
    passo = fluxo.passos[estado.passo]
    identidade = resolver(db, conversa.canal, conversa.handle_canal)
    estado_participante = montar_estado(db, identidade)

    decisao = Decisao(
        decisao=decidir(fluxo.categoria, 0.0, False, True).decisao,
        motivo=(
            f"fluxo guiado travou no passo {estado.passo + 1} de {fluxo.total} "
            f"({passo.chave}) apos {fluxo_guiado.LIMITE_FALHAS} tentativas"
        ),
        confianca=0.0,
        sensivel=False,
    )

    pasta = dossie.montar(
        pergunta=f"[fluxo guiado] {fluxo.titulo}",
        categoria=fluxo.categoria,
        identidade=identidade,
        estado=estado_participante,
        trechos=[],
        decisao=decisao,
        ancoragem=Ancoragem(intacta=False, afirmacoes_sem_fonte=["fluxo guiado"]),
        rascunho="",
        orientacao_padrao_falhou=True,
    )
    pasta["passo_em_que_travou"] = {
        "indice": estado.passo + 1,
        "total": fluxo.total,
        "chave": passo.chave,
        "instrucao": passo.instrucao,
        "alternativa_ja_tentada": passo.alternativa,
    }

    caso = Caso(
        participante_id=identidade.participante.id if identidade.participante else None,
        conversa_id=conversa.id,
        canal=conversa.canal,
        categoria=fluxo.categoria,
        sensivel=False,
        confianca=0,
        decisao_triagem=decisao.decisao,
        situacao=SituacaoCaso.ESCALADO,
        dossie=pasta,
        orientacao_padrao_falhou=True,
        score_consequencia=dossie.score_consequencia(
            fluxo.categoria, estado_participante
        ),
    )
    db.add(caso)
    db.flush()
    auditoria.registrar(
        db, "escalonamento", {"motivo": decisao.motivo}, caso_id=caso.id
    )
