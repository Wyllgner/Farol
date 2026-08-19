"""Pipeline de resolucao (secao 5.2).

1. Classificacao de intencao em 12 categorias
2. Recuperacao semantica na base oficial
3. Enriquecimento com estado individual
4. Geracao ancorada, sob restricao rigida
5. Verificacao de ancoragem: bloqueia afirmacao sem fonte
6. Politica de triagem deterministica decide o destino

A ordem nao e negociavel: a triagem decide DEPOIS de saber se ha fonte e
se a ancoragem resistiu, e nunca antes.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.enums import Canal, Categoria, DecisaoTriagem, SituacaoCaso
from app.llm import obter_provider
from app.models import Caso
from app.services import (
    auditoria,
    dossie,
    ensaio,
    esclarecimento,
    seguimento,
    social,
)
from app.services.ancoragem import Ancoragem, verificar
from app.services.conhecimento import buscar
from app.services.estado import montar as montar_estado
from app.services.estado import resumir_para_prompt
from app.services.identidade import Identidade, resolver
from app.services.triagem import (
    TEXTO_RECUSA,
    Decisao,
    calcular_confianca,
    decidir,
    eh_sensivel,
)

OFERTA_HUMANA = "Se isso não resolver, posso encaminhar para um servidor da SECOEAD."

# O modelo ve as proprias respostas no historico e as vezes reescreve a
# oferta com outras palavras ("se precisar, posso encaminhar..."). Comparar
# a frase inteira nao pega essa variacao; este nucleo pega.
_NUCLEO_DA_OFERTA = "encaminhar para um servidor"


@dataclass(slots=True)
class Atendimento:
    resposta: str
    decisao: Decisao
    categoria: Categoria
    identidade: Identidade
    trechos: list[dict] = field(default_factory=list)
    ancoragem: Ancoragem | None = None
    caso: Caso | None = None
    acoes_rapidas: list[str] = field(default_factory=list)
    # Retido pelo Modo Ensaio: a resposta foi gerada mas nao enviada.
    retido: bool = False
    # O FAROL nao entendeu a mensagem e pediu para a pessoa repetir.
    pediu_repeticao: bool = False
    # O assunto nao e da Escola: delimitou o escopo, sem abrir caso.
    fora_do_escopo: bool = False

    @property
    def escalou(self) -> bool:
        return self.decisao.escala

    @property
    def foi_entregue(self) -> bool:
        """A resposta chegou ao participante?

        So o que foi entregue abre contrato de resolucao: perguntar
        "resolveu?" sobre uma resposta que nunca saiu nao faz sentido.
        Pedido de repeticao tambem nao abre contrato: nao houve orientacao
        sobre a qual perguntar "resolveu?".
        """
        return (
            not self.escalou
            and not self.retido
            and not self.pediu_repeticao
            and not self.fora_do_escopo
        )


async def atender(
    db: Session,
    *,
    canal: Canal,
    handle: str,
    pergunta: str,
    historico: list[tuple[str, str]] | None = None,
) -> Atendimento:
    provider = obter_provider()
    degradado = provider.nome == "fallback"
    historico = historico or []

    identidade = resolver(db, canal, handle)
    auditoria.registrar(
        db,
        "entrada",
        {
            "canal": str(canal),
            "pergunta": pergunta,
            "nivel_identidade": str(identidade.nivel),
            "provider": provider.nome,
        },
    )

    # 0. Conversa social. Vem antes da classificacao porque nao e pergunta:
    #    nao ha fonte que sustente um "oi", e mandar isso ao pipeline faria
    #    o sistema escalar cortesia para um servidor. Tambem poupa a chamada
    #    de modelo, que aqui nao decidiria nada.
    if intencao_social := social.detectar(pergunta):
        return _responder_social(db, intencao_social, identidade)

    # 1. Classificacao
    classificacao = await provider.classificar(pergunta)
    categoria = classificacao.categoria
    auditoria.registrar(
        db,
        "classificacao",
        {
            "categoria": str(categoria),
            "confianca": classificacao.confianca,
            "degradado": classificacao.degradado,
        },
    )

    # Categoria sensivel escala sempre. Poupamos a chamada de geracao: o
    # destino ja esta decidido, e gerar texto que sera descartado so
    # aumentaria a chance de vazar dado pessoal na conversa.
    if eh_sensivel(categoria):
        estado = montar_estado(db, identidade)
        return _escalar(
            db,
            pergunta=pergunta,
            canal=canal,
            categoria=categoria,
            identidade=identidade,
            estado=estado,
            trechos=[],
            decisao=decidir(categoria, classificacao.confianca, False, True),
            ancoragem=Ancoragem(intacta=False, afirmacoes_sem_fonte=["nao gerado"]),
        )

    # 2. Recuperacao: so fonte vigente entra.
    #    Pergunta presa na anterior ("mas que curso e esse?") nao se
    #    sustenta como consulta semantica: sozinha ela casa com o
    #    documento errado. A busca leva o assunto do turno anterior junto.
    dependente = seguimento.eh_seguimento(pergunta)
    # A busca leva so a ultima pergunta junto, e nao a sessao inteira:
    # recuperacao e similaridade de vetor, e texto demais dilui o alvo ate
    # a consulta nao se parecer com nada. A sessao completa vai para a
    # geracao, que se beneficia de contexto em vez de sofrer com ele.
    # So junta o assunto anterior quando a pergunta nao tem assunto
    # proprio. "e o certificado?" depende do turno anterior para ser lida,
    # mas "certificado" ja acha o documento certo sozinho: somar o tema
    # antigo ali fazia a pergunta nova ser respondida com o tema velho.
    consulta = (
        seguimento.consulta_com_contexto(
            pergunta, seguimento.ultima_pergunta(historico)
        )
        if dependente and not seguimento.tem_assunto_proprio(pergunta)
        else pergunta
    )
    trechos = await buscar(db, consulta)
    auditoria.registrar(
        db,
        "recuperacao",
        {
            "quantidade": len(trechos),
            "usou_contexto_anterior": consulta != pergunta,
            "fontes": [{"documento": t["documento"], "score": t["score"]} for t in trechos],
        },
    )

    # 2b. Nada recuperado. Antes de escalar, separa o que nao e caso de
    #     servidor. Exige DOIS sinais independentes para nao responder:
    #     a base nao cobre o assunto E o classificador diz que ele nao e
    #     da Escola. Assim nada que a base cobre e recusado por escopo.
    if not trechos:
        if not classificacao.no_escopo:
            return _fora_do_escopo(db, identidade, categoria)

        # Mensagem curta demais para se saber do que se trata: escalar
        # seria mandar a um servidor um problema de "nao entendi a frase",
        # que a propria pessoa resolve reescrevendo. Mensagem longa sem
        # fonte continua escalando, porque ali existe pergunta.
        if esclarecimento.eh_vaga(pergunta):
            return _pedir_repeticao(db, identidade, categoria)

    # 3. Estado individual, limitado pelo nivel de identidade
    estado = montar_estado(db, identidade)

    # 4. Geracao ancorada
    resumo_estado = resumir_para_prompt(estado, categoria)
    partes = [pergunta]
    # O turno anterior so entra quando a pergunta depende dele: em
    # pergunta nova, ele so aumentaria a chance de responder a anterior.
    if dependente and (contexto := seguimento.bloco_de_contexto(historico)):
        partes.append(contexto)
    if resumo_estado:
        partes.append(f"[Estado deste participante]\n{resumo_estado}")
    gerada = await provider.gerar_ancorado("\n\n".join(partes), trechos)

    # 5. Verificacao de ancoragem
    ancoragem = (
        verificar(gerada.texto, trechos, gerada.fontes, estado=resumo_estado)
        if not gerada.nao_sei
        else Ancoragem(intacta=False, afirmacoes_sem_fonte=["modelo devolveu NAO_SEI"])
    )
    auditoria.registrar(
        db,
        "ancoragem",
        {
            "intacta": ancoragem.intacta,
            "motivo": ancoragem.motivo,
            "fontes_citadas": ancoragem.fontes_citadas,
        },
    )

    # 6. Triagem deterministica
    confianca = calcular_confianca(
        confianca_classificacao=classificacao.confianca,
        melhor_score_fonte=trechos[0]["score"] if trechos else 0.0,
        ancoragem_intacta=ancoragem.intacta,
        degradado=degradado,
    )
    decisao = decidir(
        categoria,
        confianca,
        tem_fonte=bool(trechos),
        nao_sei=gerada.nao_sei or not ancoragem.intacta,
    )
    auditoria.registrar(
        db,
        "triagem",
        {
            "decisao": str(decisao.decisao),
            "motivo": decisao.motivo,
            "confianca": confianca,
        },
    )

    if decisao.escala:
        return _escalar(
            db,
            pergunta=pergunta,
            canal=canal,
            categoria=categoria,
            identidade=identidade,
            estado=estado,
            trechos=trechos,
            decisao=decisao,
            ancoragem=ancoragem,
            rascunho=gerada.texto,
        )

    # Modo Ensaio (secao 7.1): a resposta existe, mas nao sai. O servidor
    # ve o que o FAROL teria respondido e aprova ou corrige. Avaliado
    # depois da triagem porque o caso que ja escalaria vai para humano de
    # qualquer forma: reter duas vezes seria ruido.
    if ensaio.deve_reter(db, categoria):
        return _reter_em_ensaio(
            db,
            pergunta=pergunta,
            canal=canal,
            categoria=categoria,
            identidade=identidade,
            estado=estado,
            trechos=trechos,
            decisao=decisao,
            ancoragem=ancoragem,
            rascunho=gerada.texto,
        )

    resposta = gerada.texto
    acoes = ["Falar com um servidor"]
    # Nao repetir a oferta que o proprio texto ja fez: a duplicata denuncia
    # a costura entre o que o modelo escreveu e o que o sistema acrescenta.
    if decisao.decisao is DecisaoTriagem.RESPONDE_COM_OFERTA_HUMANA and (
        _NUCLEO_DA_OFERTA not in resposta.lower()
    ):
        resposta = f"{resposta}\n\n{OFERTA_HUMANA}"

    caso = Caso(
        participante_id=identidade.participante.id if identidade.participante else None,
        canal=canal,
        categoria=categoria,
        sensivel=False,
        confianca=round(confianca, 3),
        decisao_triagem=decisao.decisao,
        situacao=SituacaoCaso.RESPONDIDO,
        score_consequencia=dossie.score_consequencia(categoria, estado),
    )
    db.add(caso)
    db.flush()

    auditoria.registrar(db, "resposta", {"texto": resposta}, caso_id=caso.id)

    return Atendimento(
        resposta=resposta,
        decisao=decisao,
        categoria=categoria,
        identidade=identidade,
        trechos=trechos,
        ancoragem=ancoragem,
        caso=caso,
        acoes_rapidas=acoes,
    )


FORA_DO_ESCOPO = (
    "Essa eu não sei responder: por aqui eu cuido só dos cursos da EMERON — "
    "acesso ao AVA, senha, prazos, webconferência e certificado. Se a sua "
    "dúvida for sobre isso, me conta que eu ajudo."
)


def _fora_do_escopo(
    db: Session,
    identidade: Identidade,
    categoria: Categoria,
) -> Atendimento:
    """Delimita o assunto sem escalar e sem constranger.

    Nao e recusa de competencia como a da triagem, que entrega o caso a um
    servidor: aqui nao existe caso. Mandar conversa fiada para a fila
    ocuparia quem atende com o que nao e trabalho, e o dossie chegaria
    vazio porque nao ha nada a decidir.

    A resposta nao repreende nem explica que aquilo foi impróprio: so diz
    do que ela trata e devolve a conversa para o que resolve.
    """
    auditoria.registrar(
        db,
        "fora_do_escopo",
        {"categoria": str(categoria), "motivo": "sem fonte e assunto alheio a Escola"},
    )

    return Atendimento(
        resposta=FORA_DO_ESCOPO,
        decisao=Decisao(
            decisao=DecisaoTriagem.RESPONDE,
            motivo="assunto fora do escopo da Escola: delimita sem escalar",
            confianca=0.0,
            sensivel=False,
        ),
        categoria=categoria,
        identidade=identidade,
        trechos=[],
        acoes_rapidas=[],
        # Nao e resposta de conhecimento: nao abre contrato de resolucao.
        fora_do_escopo=True,
    )


def _pedir_repeticao(
    db: Session,
    identidade: Identidade,
    categoria: Categoria,
) -> Atendimento:
    """Admite que nao entendeu e devolve a palavra para a pessoa.

    Nao abre Caso: nao houve atendimento, houve um mal-entendido. Contar
    isso como demanda sujaria o volume que o Andar 3 mede.
    """
    auditoria.registrar(
        db,
        "pedido_de_repeticao",
        {"categoria": str(categoria), "motivo": "mensagem curta e sem fonte recuperada"},
    )

    return Atendimento(
        resposta=esclarecimento.PEDIDO_DE_REPETICAO,
        decisao=Decisao(
            decisao=DecisaoTriagem.RESPONDE,
            motivo="mensagem nao compreendida: pedido de reformulacao, sem escalar",
            confianca=0.0,
            sensivel=False,
        ),
        categoria=categoria,
        identidade=identidade,
        trechos=[],
        acoes_rapidas=[],
        pediu_repeticao=True,
    )


def _responder_social(
    db: Session,
    intencao: social.Intencao,
    identidade: Identidade,
) -> Atendimento:
    """Responde cortesia com cortesia, e nao abre caso.

    Nao cria Caso de proposito: um "obrigado" nao e atendimento, e conta-lo
    como tal inflaria o volume que o Andar 3 existe para derrubar. Tambem
    nao passa pelo Modo Ensaio, porque nao ha afirmacao institucional aqui
    para um servidor conferir: o texto e fixo e nao fala do caso da pessoa.
    """
    primeiro_nome = (
        identidade.participante.nome.split(" ")[0] if identidade.participante else ""
    )
    resposta = social.responder(intencao, primeiro_nome)

    auditoria.registrar(
        db, "conversa_social", {"intencao": str(intencao), "resposta": resposta}
    )

    return Atendimento(
        resposta=resposta,
        decisao=Decisao(
            decisao=DecisaoTriagem.RESPONDE,
            motivo=f"conversa social ({intencao}): nao e pergunta, nao precisa de fonte",
            confianca=1.0,
            sensivel=False,
        ),
        categoria=Categoria.OUTROS,
        identidade=identidade,
        trechos=[],
        acoes_rapidas=["Falar com um servidor"],
    )


def _reter_em_ensaio(
    db: Session,
    *,
    pergunta: str,
    canal: Canal,
    categoria: Categoria,
    identidade: Identidade,
    estado: dict,
    trechos: list[dict],
    decisao: Decisao,
    ancoragem: Ancoragem,
    rascunho: str,
) -> Atendimento:
    """Gera, registra e NAO envia. O servidor decide."""
    pasta = dossie.montar(
        pergunta=pergunta,
        categoria=categoria,
        identidade=identidade,
        estado=estado,
        trechos=trechos,
        decisao=decisao,
        ancoragem=ancoragem,
        rascunho=rascunho,
    )
    pasta["resumo"] = (
        f"[MODO ENSAIO] {pasta.get('resumo', '')}: confira se a resposta "
        f"gerada esta correta antes de enviar."
    )
    pasta["motivo_do_escalonamento"] = (
        f"categoria '{categoria}' ainda nao liberada para resposta automatica"
    )

    caso = Caso(
        participante_id=identidade.participante.id if identidade.participante else None,
        canal=canal,
        categoria=categoria,
        sensivel=False,
        confianca=round(decisao.confianca, 3),
        decisao_triagem=decisao.decisao,
        situacao=SituacaoCaso.ESCALADO,
        dossie=pasta,
        rascunho_resposta=rascunho,
        em_ensaio=True,
        score_consequencia=dossie.score_consequencia(categoria, estado),
    )
    db.add(caso)
    db.flush()

    auditoria.registrar(
        db,
        "retido_em_ensaio",
        {"categoria": str(categoria), "resposta_gerada": rascunho},
        caso_id=caso.id,
    )

    return Atendimento(
        resposta=ensaio.AVISO_AO_PARTICIPANTE,
        decisao=decisao,
        categoria=categoria,
        identidade=identidade,
        trechos=trechos,
        ancoragem=ancoragem,
        caso=caso,
        acoes_rapidas=[],
        retido=True,
    )


def _escalar(
    db: Session,
    *,
    pergunta: str,
    canal: Canal,
    categoria: Categoria,
    identidade: Identidade,
    estado: dict,
    trechos: list[dict],
    decisao: Decisao,
    ancoragem: Ancoragem,
    rascunho: str = "",
) -> Atendimento:
    """Recusa com dignidade e entrega o caso montado ao servidor."""
    pasta = dossie.montar(
        pergunta=pergunta,
        categoria=categoria,
        identidade=identidade,
        estado=estado,
        trechos=trechos,
        decisao=decisao,
        ancoragem=ancoragem,
        rascunho=rascunho,
    )

    caso = Caso(
        participante_id=identidade.participante.id if identidade.participante else None,
        canal=canal,
        categoria=categoria,
        sensivel=decisao.sensivel,
        confianca=round(decisao.confianca, 3),
        decisao_triagem=decisao.decisao,
        situacao=SituacaoCaso.ESCALADO,
        dossie=pasta,
        # O rascunho existe para ser revisado, nunca para sair sozinho.
        rascunho_resposta=rascunho or None,
        score_consequencia=dossie.score_consequencia(categoria, estado),
    )
    db.add(caso)
    db.flush()

    auditoria.registrar(
        db, "escalonamento", {"motivo": decisao.motivo}, caso_id=caso.id
    )

    return Atendimento(
        resposta=TEXTO_RECUSA,
        decisao=decisao,
        categoria=categoria,
        identidade=identidade,
        trechos=trechos,
        ancoragem=ancoragem,
        caso=caso,
        acoes_rapidas=[],
    )
