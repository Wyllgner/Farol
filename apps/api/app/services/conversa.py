"""Conversa: persistencia do dialogo e roteamento do fluxo guiado.

Esta camada fica entre o canal e o motor de resolucao. Ela decide se a
mensagem continua um fluxo guiado em andamento ou se vai para o pipeline
normal, e essa decisao vem antes de qualquer chamada de modelo, porque
quem esta no passo 3 de 5 respondendo "nao consegui" nao esta fazendo
uma pergunta nova.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import InboundMessage, OutboundMessage
from app.enums import Canal, Categoria, Direcao, SituacaoCaso
from app.llm import obter_provider
from app.models import Caso, Conversa, Mensagem
from app.services import (
    agrupamento,
    atencao,
    auditoria,
    contrato,
    dossie,
    esclarecimento,
    fila,
    fluxo_guiado,
    seguimento,
)
from app.services.ancoragem import Ancoragem, verificar
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
    entregue: bool = True,
) -> Mensagem:
    """Grava a mensagem e devolve o registro.

    `entregue` distingue a resposta que a pessoa acabou de ler, no meio de
    uma conversa que ela mesma comecou, da mensagem proativa que ainda vai
    esperar a pessoa aparecer.
    """
    mensagem = Mensagem(
        conversa_id=conversa.id,
        direcao=direcao,
        conteudo=conteudo,
        acoes_rapidas=acoes or [],
        entregue_em=datetime.now(UTC) if entregue else None,
    )
    db.add(mensagem)
    db.flush()
    return mensagem


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

    # 4. "Nao entendi" sobre a ultima resposta. Vem antes do pipeline pela
    #    mesma razao do contrato: nao e pergunta nova, e como consulta
    #    semantica esse texto nao recupera nada.
    if esclarecimento.eh_incompreensao(entrada.texto) and (
        resposta := await _reexplicar(db, conversa)
    ):
        return resposta

    # 5. Aceite explicito da oferta feita na mensagem anterior.
    if entrada.texto.strip().lower() == ACEITE.lower():
        return _iniciar_fluxo(db, conversa, fluxo_guiado.FLUXO_2FA.chave)

    # 6. Pipeline normal, com o turno anterior a mao para as perguntas que
    #    dependem dele.
    resultado = await atender(
        db,
        canal=entrada.canal,
        handle=entrada.handle,
        pergunta=entrada.texto,
        historico=_historico_da_sessao(db, conversa),
    )

    # Pedir para repetir uma vez ajuda; pedir duas vezes seguidas e deixar
    # a pessoa presa num loop educado. Na segunda, vai para um servidor.
    if resultado.pediu_repeticao:
        if _ja_pediu_para_repetir(db, conversa):
            return _escalar_sem_entender(db, conversa, entrada.texto)
        return OutboundMessage(texto=resultado.resposta, acoes_rapidas=[])

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
            texto="Que bom! Qualquer outra dúvida, é só chamar.",
            acoes_rapidas=[],
        )

    # A regra central do laco: nao repetimos a resposta que ja falhou.
    contrato.registrar_falha(db, caso)
    _deduplicar(db, caso)
    return OutboundMessage(
        texto=(
            "Obrigado por avisar. Não vou repetir a mesma orientação: se ela "
            "não funcionou, o caso precisa de um servidor. Já encaminhei com o "
            "registro do que foi tentado e você recebe o retorno por aqui."
        ),
        acoes_rapidas=[],
    )


def _historico_da_sessao(db: Session, conversa: Conversa) -> list[tuple[str, str]]:
    """Mensagens desta sessao, em ordem cronologica, sem a que acabou de chegar.

    `processar` ja gravou a mensagem atual antes de rotear, entao ela e
    descartada aqui: o modelo recebe a pergunta atual separada, e ve-la
    duas vezes so aumentaria a chance de responder a anterior.
    """
    corte = datetime.now(UTC) - seguimento.JANELA_DE_SESSAO
    linhas = db.execute(
        select(Mensagem.direcao, Mensagem.conteudo)
        .where(Mensagem.conversa_id == conversa.id)
        .where(Mensagem.criado_em >= corte)
        .order_by(Mensagem.criado_em.desc(), Mensagem.id.desc())
        .limit(seguimento.LIMITE_DE_MENSAGENS + 1)
    ).all()

    # Veio do mais novo para o mais velho: a primeira linha e a mensagem
    # atual. Descarta e devolve na ordem em que a conversa aconteceu.
    return [(str(direcao), conteudo) for direcao, conteudo in reversed(linhas[1:])]


def _ja_pediu_para_repetir(db: Session, conversa: Conversa) -> bool:
    """A ultima coisa que o FAROL disse ja foi "nao entendi"?"""
    ultima = db.scalar(
        select(Mensagem.conteudo)
        .where(Mensagem.conversa_id == conversa.id)
        .where(Mensagem.direcao == Direcao.SAIDA)
        .order_by(Mensagem.criado_em.desc(), Mensagem.id.desc())
    )
    return ultima == esclarecimento.PEDIDO_DE_REPETICAO


def _escalar_sem_entender(
    db: Session, conversa: Conversa, texto: str
) -> OutboundMessage:
    """Duas tentativas e ainda sem entender: o servidor le melhor que eu.

    Escala com a mensagem original intacta. Um servidor humano entende em
    dois segundos o que o sistema nao conseguiu interpretar, e e por isso
    que o dossie carrega o texto literal, sem tentativa de adivinhacao.
    """
    identidade = resolver(db, conversa.canal, conversa.handle_canal)
    estado_participante = montar_estado(db, identidade)

    decisao = Decisao(
        decisao=decidir(Categoria.OUTROS, 0.0, False, True).decisao,
        motivo="mensagem nao compreendida depois de pedir reformulacao",
        confianca=0.0,
        sensivel=False,
    )
    pasta = dossie.montar(
        pergunta=texto,
        categoria=Categoria.OUTROS,
        identidade=identidade,
        estado=estado_participante,
        trechos=[],
        decisao=decisao,
        ancoragem=Ancoragem(intacta=False, afirmacoes_sem_fonte=["nao gerado"]),
        rascunho="",
    )
    pasta["motivo_do_escalonamento"] = (
        "o FAROL nao entendeu a mensagem nem depois de pedir para reformular"
    )
    pasta["mensagem_original"] = texto

    caso = Caso(
        participante_id=identidade.participante.id if identidade.participante else None,
        conversa_id=conversa.id,
        canal=conversa.canal,
        categoria=Categoria.OUTROS,
        sensivel=False,
        confianca=0,
        decisao_triagem=decisao.decisao,
        situacao=SituacaoCaso.ESCALADO,
        dossie=pasta,
        score_consequencia=dossie.score_consequencia(
            Categoria.OUTROS, estado_participante
        ),
    )
    db.add(caso)
    db.flush()

    auditoria.registrar(
        db, "escalonamento_sem_entender", {"mensagem": texto}, caso_id=caso.id
    )

    return OutboundMessage(
        texto=(
            "Continuo sem entender, e não quero te fazer repetir de novo. "
            "Passei sua mensagem para um servidor da SECOEAD, que responde "
            "por aqui mesmo."
        ),
        acoes_rapidas=[],
    )


async def _reexplicar(db: Session, conversa: Conversa) -> OutboundMessage | None:
    """Reescreve a ultima resposta em linguagem mais simples.

    Devolve None quando nao ha o que reescrever (a pessoa escreveu "nao
    entendi" sem ter recebido resposta antes): ai a mensagem segue para o
    pipeline, que ao menos tentara entender o assunto.
    """
    caso = esclarecimento.ultimo_caso_respondido(db, conversa.id)
    if caso is None or not caso.resposta_enviada:
        return None

    trechos = esclarecimento.trechos_do_caso(db, caso)
    if not trechos:
        return None

    # Duas explicacoes que nao chegaram sao um sinal sobre o texto
    # oficial, e nao mais um caso de reescrever.
    if esclarecimento.reescritas_ja_feitas(db, caso) >= esclarecimento.LIMITE_DE_REESCRITAS:
        return _escalar_por_incompreensao(db, conversa, caso)

    provider = obter_provider()
    gerada = await provider.gerar_ancorado(
        esclarecimento.pedido_de_reescrita(caso.resposta_enviada), trechos
    )
    ancoragem = (
        verificar(gerada.texto, trechos, gerada.fontes)
        if not gerada.nao_sei
        else Ancoragem(intacta=False, afirmacoes_sem_fonte=["modelo devolveu NAO_SEI"])
    )
    # A reescrita nao tem licenca extra: se ela perdeu a ancoragem, cai
    # na mesma regra de todo o resto e vai para um servidor.
    if not ancoragem.intacta:
        auditoria.registrar(
            db,
            "reexplicacao_bloqueada",
            {"motivo": ancoragem.motivo},
            caso_id=caso.id,
        )
        return _escalar_por_incompreensao(db, conversa, caso)

    auditoria.registrar(
        db,
        esclarecimento.ETAPA_AUDITORIA,
        {"resposta_anterior": caso.resposta_enviada, "reescrita": gerada.texto},
        caso_id=caso.id,
    )
    # A resposta que vale para o contrato passa a ser a que a pessoa leu.
    caso.resposta_enviada = gerada.texto
    db.flush()

    return OutboundMessage(
        texto=gerada.texto,
        acoes_rapidas=["Falar com um servidor"],
        fontes=[{"documento": t["documento"], "dono": t["dono"]} for t in trechos],
    )


def _escalar_por_incompreensao(
    db: Session, conversa: Conversa, caso: Caso
) -> OutboundMessage:
    """A explicacao ja foi reescrita e ainda nao chegou: vai para humano.

    O dossie diz ao servidor exatamente isto, porque e o que ele precisa
    saber antes de escrever: o problema nao e a pessoa nem a falta de
    fonte, e o texto oficial que nao esta se fazendo entender.
    """
    identidade = resolver(db, conversa.canal, conversa.handle_canal)
    pasta = dict(caso.dossie or {})
    pasta.update(
        {
            "resumo": (
                f"{identidade.participante.nome.split()[0] if identidade.participante else 'Participante'}"
                ": a orientacao foi entregue e reescrita, e a pessoa segue "
                "sem entender."
            ),
            "motivo_do_escalonamento": (
                "incompreensao repetida: a explicacao automatica nao chegou "
                "nem depois de reescrita"
            ),
            "orientacao_padrao_falhou": True,
            "resposta_que_nao_foi_compreendida": caso.resposta_enviada,
            "fontes_usadas": caso.fontes_usadas or [],
        }
    )
    esclarecimento.marcar_escalado(caso, pasta)
    _deduplicar(db, caso)
    db.flush()

    auditoria.registrar(
        db,
        "escalonamento_por_incompreensao",
        {"categoria": str(caso.categoria)},
        caso_id=caso.id,
    )

    return OutboundMessage(
        texto=(
            "Entendi, e isso é informação útil: se expliquei duas vezes e não "
            "ficou claro, o problema é a explicação, não você. Já encaminhei "
            "para um servidor da SECOEAD com o registro do que foi tentado. "
            "Você recebe o retorno por aqui."
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
            "Pronto, não mando mais avisos automáticos. Você continua podendo "
            "perguntar aqui quando precisar."
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
