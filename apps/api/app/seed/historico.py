"""Historico de operacao do FAROL: as 12 semanas anteriores a hoje.

O seed principal monta o mundo no instante zero. Ele nao tem passado, e
sem passado o painel de indicadores nao consegue mostrar a unica coisa
que a tese afirma: que a curva DESCE. Um numero sozinho nao prova
tendencia; uma serie prova.

Os dados aqui sao ficticios, como todo o resto do mundo do FAROL, e
sao gravados nas mesmas tabelas que a operacao real grava. Os
indicadores continuam sendo CALCULADOS pelo sistema a partir delas: nao
existe numero escrito direto na tela.

A curva e desenhada com intencao, e a intencao e a tese do produto:

  semanas 1-4    volume alto, quase tudo escalado para humano
  semanas 5-8    Andar 1 comeca a evitar; a fila afina
  semanas 9-12   ordens de correcao sao implementadas e as causas
                 comecam a sumir: o volume da categoria corrigida despenca

Executar: python -m app.seed.historico
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from app.db import SessionLocal
from app.enums import (
    Canal,
    Categoria,
    ContratoResolucao,
    DecisaoTriagem,
    Direcao,
    EfeitoAntecipacao,
    SituacaoCaso,
    SituacaoOrdem,
)
from app.models import (
    AgrupamentoCausa,
    Caso,
    Conversa,
    EventoProativo,
    LogAuditoria,
    Mensagem,
    OrdemCorrecao,
    Participante,
)
from app.services import demo

# Mesma semente do seed principal: a demonstracao precisa ser reproduzivel.
random.seed(42)

# Os participantes que o console oferece como cenario NAO entram no
# historico de mensagens proativas.
#
# O motor barra um gatilho que ja disparou para a mesma pessoa, e essa
# regra e correta: ninguem quer receber o mesmo aviso duas vezes. Mas o
# historico gera 322 eventos sobre 60 pessoas, entao quase todo mundo
# fica bloqueado, e o "ele fala primeiro" da demonstracao nao acontece
# justamente com a pessoa que quem apresenta escolheu na tela.
#
# Eles continuam recebendo casos historicos: o que se preserva aqui e so
# o direito de serem interrompidos ao vivo.
CENARIOS_DA_DEMO = {
    "+556990000000",  # nunca acessou
    "+556990000001",  # 2FA pendente
    "+556990000002",  # prazo apertado
    "+556990000004",  # certificado liberado
    "+556990000017",  # optou por nao receber
}

SEMANAS = 12

# Volume semanal por categoria. Cada linha e uma historia:
#
# 2fa e webconferencia sao as duas dores que o desafio relata e que ja
# receberam banner e video sem resolver. Elas sobem, recebem ordem de
# correcao na semana 8, e caem de verdade depois - e essa queda que o
# Andar 3 previu numericamente e volta para conferir.
#
# senha e prazo sao o ruido de fundo estavel: existem para que a queda
# das outras duas nao pareca so uma queda geral de movimento.
CURVAS: dict[Categoria, list[int]] = {
    Categoria.DOIS_FATORES:  [18, 21, 19, 22, 20, 17, 15, 16, 9, 6, 4, 3],
    Categoria.WEBCONFERENCIA:[14, 16, 15, 17, 16, 14, 13, 15, 8, 6, 5, 4],
    Categoria.CERTIFICADO:   [9, 11, 10, 12, 13, 11, 10, 9, 8, 7, 7, 6],
    Categoria.PRAZO:         [7, 6, 8, 7, 9, 8, 7, 8, 7, 6, 7, 6],
    Categoria.SENHA:         [6, 7, 5, 6, 6, 5, 6, 5, 5, 4, 5, 4],
    Categoria.LOCALIZACAO_CURSO: [5, 4, 6, 5, 4, 4, 3, 4, 3, 3, 2, 2],
    Categoria.CONTEUDO:      [3, 4, 3, 5, 4, 3, 4, 3, 3, 2, 3, 2],
    Categoria.RECLAMACAO:    [2, 1, 2, 2, 1, 2, 1, 1, 1, 1, 1, 1],
}

# Fracao dos casos da semana que o FAROL resolveu sem humano. Sobe ao
# longo do tempo: a base de conhecimento amadurece e o Modo Ensaio vai
# liberando categoria por categoria.
AUTONOMIA = [0.34, 0.41, 0.47, 0.52, 0.58, 0.63, 0.68, 0.72, 0.78, 0.81, 0.84, 0.86]

# Mensagens proativas entregues por semana, e quantas delas tiveram a
# hipotese CONFIRMADA (a pessoa nao abriu atendimento depois do aviso).
# O Andar 1 so entra em operacao na semana 4: antes disso nao havia
# gatilho calibrado, e fingir que havia esconderia a curva de aprendizado.
PROATIVAS = [0, 0, 0, 12, 19, 26, 31, 38, 44, 47, 51, 54]
CONFIRMADAS = [0, 0, 0, 7, 13, 19, 24, 30, 36, 40, 44, 47]

# As quatro ordens do periodo. As duas primeiras acertaram a previsao
# (causa extinta), a terceira acertou por pouco e a quarta ERROU: ela
# fica no painel de proposito. Uma metrica de acerto que nunca mostra
# erro nao mede nada, e a banca merece ver o sistema se desmentindo.
ORDENS = [
    {
        "rotulo": "Configurar o segundo fator de autenticacao",
        "hipotese": (
            "As pessoas travam em 'primeiro_acesso' porque a instrucao do 2FA "
            "esta na terceira aba do manual, e nao na tela onde o erro acontece."
        ),
        "evidencia": (
            "79 casos agrupados por similaridade semantica em 8 semanas; "
            "taxa de travamento na aresta primeiro_acesso -> configuracao_2fa e de 34%, "
            "a maior do grafo da jornada."
        ),
        "acao": (
            "Mover a instrucao de configuracao do 2FA para a primeira tela apos o "
            "login, em video de 40 segundos com legenda."
        ),
        "semana_emissao": 6,
        "semana_implementacao": 8,
        "previsao": 12,
        "medido": 13,
        "situacao": SituacaoOrdem.CONFIRMADA,
        "conclusao": (
            "Previsao de 12 casos/mes a menos; medido 13. Causa extinta: a aresta "
            "primeiro_acesso -> configuracao_2fa saiu do topo do radar."
        ),
    },
    {
        "rotulo": "Nao conseguir abrir o link da webconferencia",
        "hipotese": (
            "As pessoas travam em 'consumo_conteudo' porque o link da webconferencia "
            "fica abaixo da dobra, depois da lista de materiais."
        ),
        "evidencia": (
            "62 casos agrupados por similaridade semantica em 8 semanas; "
            "84% chegam nas duas horas anteriores ao inicio da sessao ao vivo."
        ),
        "acao": (
            "Mover o link da webconferencia para o topo da pagina do curso, acima "
            "da dobra, com contagem regressiva para a proxima sessao."
        ),
        "semana_emissao": 6,
        "semana_implementacao": 8,
        "previsao": 9,
        "medido": 10,
        "situacao": SituacaoOrdem.CONFIRMADA,
        "conclusao": (
            "Previsao de 9 casos/mes a menos; medido 10. Causa extinta."
        ),
    },
    {
        "rotulo": "Confirmar se o certificado ja foi emitido",
        "hipotese": (
            "As pessoas perguntam do certificado porque nada avisa quando ele "
            "e liberado: elas conferem manualmente ate aparecer."
        ),
        "evidencia": (
            "41 casos agrupados; 71% vem de matriculas com certificado ja liberado "
            "ha mais de tres dias."
        ),
        "acao": (
            "Enviar aviso automatico de certificado liberado com o link direto de "
            "emissao, em ate uma hora apos a liberacao."
        ),
        "semana_emissao": 8,
        "semana_implementacao": 9,
        "previsao": 5,
        "medido": 5,
        "situacao": SituacaoOrdem.CONFIRMADA,
        "conclusao": "Previsao de 5 casos/mes a menos; medido 5. Causa extinta.",
    },
    {
        # A ordem que ainda espera decisao. O Radar mostra UMA recomendacao
        # por vez, e sem nenhuma pendente de peso ele destaca o que sobrou
        # da ultima analise: a tela de recomendacao vira tela de resto.
        "rotulo": "Nao saber onde fica a sala da webconferencia ao vivo",
        "hipotese": (
            "As pessoas perguntam onde e a sala ao vivo porque o convite chega "
            "por e-mail um dia antes e nao fica em lugar nenhum dentro do AVA."
        ),
        "evidencia": (
            "57 casos agrupados por similaridade semantica nas ultimas 4 semanas; "
            "68% chegam entre 30 e 90 minutos antes do inicio da sessao; "
            "taxa de travamento na aresta consumo_conteudo -> webconferencia e de 29%."
        ),
        "acao": (
            "Fixar o convite da proxima sessao ao vivo no topo da pagina do curso, "
            "com data, hora e botao de entrada, ate o fim da transmissao."
        ),
        "semana_emissao": 11,
        "semana_implementacao": None,
        "previsao": 14,
        "medido": None,
        "situacao": SituacaoOrdem.PENDENTE,
        "conclusao": None,
    },
    {
        "rotulo": "Nao encontrar o curso na plataforma apos entrar",
        "hipotese": (
            "As pessoas nao acham o curso porque o menu 'Meus cursos' usa um "
            "icone sem rotulo textual."
        ),
        "evidencia": "23 casos agrupados; concentrados no perfil servidor.",
        "acao": "Adicionar rotulo textual ao icone 'Meus cursos' no menu principal.",
        "semana_emissao": 8,
        "semana_implementacao": 9,
        "previsao": 6,
        "medido": 1,
        "situacao": SituacaoOrdem.DESCARTADA,
        "conclusao": (
            "Previsao de 6 casos/mes a menos; medido 1. Hipotese descartada: o "
            "rotulo nao era a causa. Casos remanescentes voltam para agrupamento."
        ),
    },
]

# Conversa que antecede o escalonamento, por categoria.
#
# Ela existe para os casos que FICAM na fila. O dossie promete transcricao
# consolidada, e um caso historico sem conversa mostrava um dossie pela
# metade justamente na tela que a demonstracao abre para provar que o
# servidor recebe o caso inteiro.
#
# As falas do FAROL ficam em constantes porque sao longas: dentro do dict
# elas virariam concatenacao implicita, que e onde nasce o bug classico de
# esquecer uma virgula e colar duas mensagens numa so.
_SAUDACAO = (
    "Oi! Aqui e o FAROL, da SECOEAD. Ajudo com acesso ao AVA, senha, prazos, "
    "webconferencia e certificado. O que voce precisa?"
)
_PRAZO = (
    "O prazo da atividade final aparece no Relatorio de Progresso do curso, "
    "junto da lista de pendencias. No seu caso, o prazo ainda esta aberto. "
    "Quer que eu detalhe o que falta entregar?"
)
_CERTIFICADO = (
    "O certificado e liberado automaticamente quando 75% de frequencia e "
    "todas as atividades obrigatorias estao concluidas. Confira no Relatorio "
    "de Progresso qual pendencia impede a liberacao."
)
_COORDENACAO = (
    "Posso ajudar com duvidas sobre acesso, prazos, webconferencia e "
    "certificado. Se preferir falar com um servidor da SECOEAD, eu encaminho "
    "seu caso agora."
)
_ACOLHIMENTO = (
    "Boa tarde! Aqui e o FAROL, da SECOEAD. Me conta o que aconteceu que eu "
    "vejo como ajudar."
)
_TRIAGEM_2FA = (
    "Vamos por partes. O erro aparece antes ou depois de digitar a senha? Se "
    "for depois, e a verificacao em duas etapas."
)
_CODIGO_2FA = (
    "Esse codigo vem do aplicativo autenticador cadastrado no primeiro "
    "acesso. Abra o app e use o codigo de 6 digitos que estiver valido no "
    "momento: ele troca a cada 30 segundos."
)
_WEBCONFERENCIA = (
    "A webconferencia acontece dentro do AVA, na pagina do curso, no modulo "
    "do encontro. A sala abre 15 minutos antes do horario."
)

CONVERSAS: dict[Categoria, list[tuple[str, str]]] = {
    Categoria.PRAZO: [
        ("participante", "boa tarde"),
        ("farol", _SAUDACAO),
        ("participante", "e sobre a atividade final do curso"),
        ("farol", _PRAZO),
    ],
    Categoria.CERTIFICADO: [
        ("participante", "oi, bom dia"),
        ("farol", _SAUDACAO),
        ("participante", "queria saber do meu certificado"),
        ("farol", _CERTIFICADO),
    ],
    Categoria.RECLAMACAO: [
        ("participante", "preciso falar com alguem da coordenacao"),
        ("farol", _COORDENACAO),
    ],
    Categoria.SENSIVEL: [
        ("participante", "boa tarde, preciso de uma orientacao"),
        ("farol", _ACOLHIMENTO),
    ],
    Categoria.DOIS_FATORES: [
        ("participante", "nao estou conseguindo entrar no ava"),
        ("farol", _TRIAGEM_2FA),
        ("participante", "depois, ele pede um codigo"),
        ("farol", _CODIGO_2FA),
    ],
    Categoria.WEBCONFERENCIA: [
        ("participante", "oi"),
        ("farol", _SAUDACAO),
        ("participante", "e sobre o encontro ao vivo de hoje"),
        ("farol", _WEBCONFERENCIA),
    ],
}

# Categorias sem conversa propria usam a do assunto mais proximo: escrever
# seis dialogos para categorias que quase nao escalam seria trabalho para
# encher o banco, nao para tornar a fila legivel.
CONVERSA_PADRAO = CONVERSAS[Categoria.CERTIFICADO]

# Perguntas de exemplo por categoria. Ficam no caso para que o Radar
# tenha texto real para exibir, e nao um registro vazio com contador.
PERGUNTAS = {
    Categoria.DOIS_FATORES: [
        "nao consigo configurar o segundo fator de autenticacao",
        "o codigo do 2fa nao chega no meu celular",
        "travei na verificacao em duas etapas",
    ],
    Categoria.WEBCONFERENCIA: [
        "o link da webconferencia nao abre",
        "entrei na sala e nao tem audio",
        "perdi a webconferencia ao vivo, tem gravacao?",
    ],
    Categoria.CERTIFICADO: [
        "meu certificado ja saiu?",
        "como emito o certificado do curso?",
        "conclui o curso e o certificado nao apareceu",
    ],
    Categoria.PRAZO: [
        "qual o prazo pra entregar a atividade final?",
        "consigo prorrogar o prazo da atividade?",
    ],
    Categoria.SENHA: [
        "esqueci minha senha do AVA",
        "minha senha nao funciona mais",
    ],
    Categoria.LOCALIZACAO_CURSO: [
        "nao encontro o curso na plataforma",
        "onde fica a sala do meu curso?",
    ],
    Categoria.CONTEUDO: [
        "o material da aula 3 esta indisponivel",
        "o video da aula nao carrega",
    ],
    Categoria.RECLAMACAO: [
        "quero registrar uma reclamacao sobre o atendimento",
        "ninguem respondeu meu chamado ate agora",
    ],
}


# Marcador das conversas que o historico cria. E por ele que uma segunda
# execucao reconhece o que ela mesma escreveu: apagar por data nao serve,
# porque o console de demonstracao move o relogio e joga a operacao ao
# vivo para o passado tambem.
MARCADOR = "seed:historico"

# Hipotese textual dos eventos proativos historicos. Evento nao tem
# conversa, entao o marcador dele e o proprio texto que so o historico
# escreve.
# Definida em services.demo porque o console precisa dela para preservar o
# historico ao restaurar saldos. Duas copias do mesmo texto viravam duas
# verdades no dia em que uma delas mudasse.
HIPOTESE = demo.HIPOTESE_DO_HISTORICO


def _limpar_historico(db) -> dict:
    """Remove um historico anterior sem tocar na operacao ao vivo.

    Rodar duas vezes nao pode dobrar a curva. Os casos historicos nunca
    geram log de auditoria - eles nascem prontos, sem passar pela
    triagem -, e por isso podem ser apagados sem esbarrar no trigger de
    imutabilidade que recusa o SET NULL sobre log_auditoria.
    """
    conversas = db.scalars(
        select(Conversa).where(Conversa.contexto_pagina == MARCADOR)
    ).all()
    ids = {c.id for c in conversas}

    casos = []
    if ids:
        # Caso com log de auditoria e caso que a operacao real produziu:
        # apagar dispara SET NULL sobre log_auditoria, que e um UPDATE, e o
        # trigger de imutabilidade recusa. O vinculo com a conversa cai
        # sozinho quando ela e apagada, e o caso continua na fila onde deve.
        com_log = select(LogAuditoria.caso_id).where(LogAuditoria.caso_id.is_not(None))
        casos = db.scalars(
            select(Caso).where(Caso.conversa_id.in_(ids), Caso.id.not_in(com_log))
        ).all()
        for caso in casos:
            db.delete(caso)
        db.flush()

    eventos = db.scalars(
        select(EventoProativo).where(EventoProativo.hipotese == HIPOTESE)
    ).all()
    for evento in eventos:
        db.delete(evento)

    rotulos = [d["rotulo"] for d in ORDENS]
    agrupamentos = db.scalars(
        select(AgrupamentoCausa).where(AgrupamentoCausa.rotulo.in_(rotulos))
    ).all()
    alvos = {a.id for a in agrupamentos}
    if alvos:
        for o in db.scalars(
            select(OrdemCorrecao).where(OrdemCorrecao.agrupamento_id.in_(alvos))
        ).all():
            db.delete(o)
        db.flush()
        for a in agrupamentos:
            db.delete(a)

    for conversa in conversas:
        db.delete(conversa)
    db.flush()

    return {"casos": len(casos), "eventos": len(eventos), "ordens": len(alvos)}


def _datar(db, tabela: str, registro_id: uuid.UUID, quando: datetime) -> None:
    """Reescreve criado_em.

    O TimestampMixin carimba now() no INSERT, que e o comportamento certo
    para a operacao e o errado para semear passado. O UPDATE cru e o
    caminho mais honesto: nenhuma regra de negocio finge que este dado
    nasceu agora.
    """
    db.execute(
        text(f"UPDATE {tabela} SET criado_em = :quando WHERE id = :id"),
        {"quando": quando, "id": registro_id},
    )


def _montar_atendimento(db, *, caso, conversa, participante, quando) -> None:
    """Grava a conversa que antecede o escalonamento e o dossie do caso.

    O dossie e montado aqui, e nao por dossie.montar, porque este caso
    nunca passou pelo pipeline: ele nasce escalado. Reproduzir a chamada
    exigiria fabricar identidade, ancoragem e trechos recuperados, que e
    mais mentira do que o seed precisa contar. O que a tela le e o formato,
    e o formato e este.
    """
    turnos = CONVERSAS.get(caso.categoria, CONVERSA_PADRAO)

    # A conversa acontece nos minutos que antecedem a pergunta que escalou.
    inicio = quando - timedelta(minutes=len(turnos) + 1)
    transcricao = []
    for passo, (quem, texto) in enumerate(turnos):
        instante = inicio + timedelta(minutes=passo)
        mensagem = Mensagem(
            conversa_id=conversa.id,
            direcao=Direcao.ENTRADA if quem == "participante" else Direcao.SAIDA,
            conteudo=texto,
            entregue_em=instante,
        )
        db.add(mensagem)
        db.flush()
        _datar(db, "mensagem", mensagem.id, instante)
        transcricao.append(
            {
                "quem": quem,
                "canal": str(conversa.canal),
                "texto": texto,
                "em": instante.isoformat(),
                "entregue": True,
            }
        )

    # A pergunta que escalou fecha a conversa.
    ultima = Mensagem(
        conversa_id=conversa.id,
        direcao=Direcao.ENTRADA,
        conteudo=caso.pergunta,
        entregue_em=quando,
    )
    db.add(ultima)
    db.flush()
    _datar(db, "mensagem", ultima.id, quando)
    transcricao.append(
        {
            "quem": "participante",
            "canal": str(conversa.canal),
            "texto": caso.pergunta,
            "em": quando.isoformat(),
            "entregue": True,
        }
    )

    # Estado real da matricula. Sem ele a fila mostra "Anonimo" e o dossie
    # perde justamente o que o Andar 2 promete: a resposta e sobre o caso
    # DAQUELA pessoa, e o servidor precisa ver de quem se trata.
    hoje = quando.date()
    cursos = []
    for matricula in participante.matriculas:
        prazo = matricula.prazo_pessoal
        ultimo = matricula.ultimo_acesso
        cursos.append(
            {
                "curso": matricula.curso.titulo,
                "progresso_pct": float(matricula.progresso),
                "nunca_acessou": ultimo is None,
                # O caso e do passado e o ultimo acesso pode ser posterior
                # a ele: a subtracao crua dava "ultimo acesso ha -3 dias" na
                # tela do servidor.
                "dias_desde_ultimo_acesso": (
                    None if ultimo is None else max(0, (quando - ultimo).days)
                ),
                "dois_fatores_configurado": matricula.dois_fatores_configurado,
                "prazo_pessoal": prazo.isoformat() if prazo else None,
                "dias_ate_o_prazo": None if prazo is None else (prazo - hoje).days,
                "situacao_certificado": str(matricula.situacao_certificado),
                "etapa_na_jornada": None,
            }
        )

    primeiro_nome = participante.nome.split()[0]
    estado_do_participante = {
        # Minimizacao (secao 13): so o primeiro nome, como em producao.
        "primeiro_nome": primeiro_nome,
        "perfil": str(participante.perfil),
        "cursos": cursos,
    }
    if caso.sensivel:
        resumo = (
            f"{primeiro_nome}: assunto sensivel ({caso.categoria}), "
            f"encaminhado por politica."
        )
        motivo = "categoria sensivel: escala sempre, independentemente da confianca"
    else:
        resumo = f"{primeiro_nome}: {caso.categoria}, sem fonte suficiente para responder."
        motivo = f"confianca baixa ({float(caso.confianca):.2f}) e sem fonte que sustente"

    caso.dossie = {
        "resumo": resumo,
        "motivo_do_escalonamento": motivo,
        "orientacao_padrao_falhou": caso.orientacao_padrao_falhou,
        "categoria": str(caso.categoria),
        "sensivel": caso.sensivel,
        "nivel_identidade": "reconhecido",
        "pergunta": caso.pergunta,
        "transcricao": transcricao,
        "estado_do_participante": estado_do_participante,
        "fontes_consultadas": [],
        "confianca": float(caso.confianca),
        "ancoragem": {
            "intacta": False,
            "motivo": "afirmacao nao sustentada pelas fontes: nao gerado",
        },
        "rascunho_sugerido": "",
        "montado_em": quando.isoformat(),
    }


def semear_historico() -> dict:
    agora = datetime.now(UTC)

    # Ancora na segunda-feira desta semana, que e onde /indicadores/series
    # corta os baldes. Semear a partir de "agora" desalinharia a primeira
    # semana pela metade e ela apareceria no grafico como um vale que
    # nunca existiu.
    ancora = (agora - timedelta(days=agora.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    with SessionLocal() as db:
        removidos = _limpar_historico(db)

        participantes = db.scalars(select(Participante)).all()
        if not participantes:
            raise RuntimeError(
                "mundo vazio: rode 'python -m app.seed' antes do historico"
            )

        # Uma conversa por participante para pendurar os casos historicos.
        conversas = {}
        for p in participantes:
            conversa = Conversa(
                participante_id=p.id,
                canal=Canal.WHATSAPP,
                # Handle proprio, que NUNCA colide com o do canal real.
                # Com o telefone puro, a primeira mensagem que a pessoa
                # mandasse ao vivo caia nesta conversa: o caso novo nascia
                # dentro do historico, e a proxima semeadura tentava apagar
                # um caso que ja tinha log de auditoria.
                handle_canal=f"historico:{p.telefone or p.id}",
                contexto_pagina=MARCADOR,
            )
            db.add(conversa)
            conversas[p.id] = conversa
        db.flush()

        total_casos = 0
        for semana in range(SEMANAS):
            # Semana 0 e a mais antiga; semana 11 termina ontem.
            inicio = ancora - timedelta(days=(SEMANAS - semana) * 7)
            autonomia = AUTONOMIA[semana]

            for categoria, curva in CURVAS.items():
                for _ in range(curva[semana]):
                    participante = random.choice(participantes)
                    quando = inicio + timedelta(
                        days=random.randint(0, 6), hours=random.randint(8, 18)
                    )
                    sensivel = categoria is Categoria.RECLAMACAO

                    # Sensivel escala sempre, independentemente da confianca:
                    # e a mesma regra da triagem em producao, e o historico
                    # nao pode contradizer a politica que a tela publica.
                    if sensivel:
                        decisao = DecisaoTriagem.ESCALA
                        situacao = SituacaoCaso.ESCALADO
                        confianca = round(random.uniform(0.30, 0.60), 3)
                    elif random.random() < autonomia:
                        decisao = DecisaoTriagem.RESPONDE
                        situacao = SituacaoCaso.ENCERRADO
                        confianca = round(random.uniform(0.72, 0.97), 3)
                    elif random.random() < 0.55:
                        decisao = DecisaoTriagem.RESPONDE_COM_OFERTA_HUMANA
                        situacao = SituacaoCaso.ENCERRADO
                        confianca = round(random.uniform(0.46, 0.69), 3)
                    else:
                        decisao = DecisaoTriagem.ESCALA
                        situacao = SituacaoCaso.ESCALADO
                        confianca = round(random.uniform(0.10, 0.44), 3)

                    # O contrato so existe onde houve resposta: escalar nao
                    # e resolver, e creditar confirmacao a um caso escalado
                    # inflaria a taxa que mede exatamente o oposto.
                    if situacao is SituacaoCaso.ENCERRADO:
                        sorteio = random.random()
                        if sorteio < 0.61:
                            contrato = ContratoResolucao.CONFIRMADO
                        elif sorteio < 0.72:
                            contrato = ContratoResolucao.FALHOU
                        else:
                            contrato = ContratoResolucao.SEM_RETORNO
                    else:
                        contrato = ContratoResolucao.ABERTO

                    # O servidor atendeu e fechou o que foi escalado ha
                    # mais de duas semanas. Deixar tudo aberto encheria a
                    # fila com 150 casos que nenhuma equipe real deixaria
                    # parados, e a tela de fila deixaria de ser legivel.
                    if (
                        situacao is SituacaoCaso.ESCALADO
                        and semana < SEMANAS - 2
                    ):
                        situacao = SituacaoCaso.ENCERRADO

                    caso = Caso(
                        participante_id=participante.id,
                        conversa_id=conversas[participante.id].id,
                        canal=Canal.WHATSAPP,
                        categoria=categoria,
                        sensivel=sensivel,
                        pergunta=random.choice(PERGUNTAS[categoria]),
                        confianca=confianca,
                        decisao_triagem=decisao,
                        situacao=situacao,
                        contrato_resolucao=contrato,
                        orientacao_padrao_falhou=(
                            contrato is ContratoResolucao.FALHOU
                        ),
                    )
                    db.add(caso)
                    db.flush()
                    _datar(db, "caso", caso.id, quando)
                    total_casos += 1

                    # Só quem fica na fila ganha conversa e dossiê. Montar
                    # transcrição para os 600 casos encerrados encheria o
                    # banco de texto que ninguém vai abrir; a tela que
                    # precisa do dossiê é a fila.
                    if situacao is SituacaoCaso.ESCALADO:
                        _montar_atendimento(
                            db,
                            caso=caso,
                            conversa=conversas[participante.id],
                            participante=participante,
                            quando=quando,
                        )

            # --- Andar 1: mensagens proativas com hipotese ja verificada ---
            entregues = PROATIVAS[semana]
            confirmadas = CONFIRMADAS[semana]
            gatilhos_da_semana = [
                "sem_2fa", "webconferencia_hoje", "prazo_apertado",
                "certificado_parado", "nunca_acessou",
            ]
            elegiveis = [
                p for p in participantes if p.telefone not in CENARIOS_DA_DEMO
            ]
            for i in range(entregues):
                participante = random.choice(elegiveis)
                enviado = inicio + timedelta(
                    days=random.randint(0, 6), hours=random.randint(9, 17)
                )
                efeito = (
                    EfeitoAntecipacao.CONFIRMADO
                    if i < confirmadas
                    else EfeitoAntecipacao.REFUTADO
                )
                evento = EventoProativo(
                    gatilho=gatilhos_da_semana[i % len(gatilhos_da_semana)],
                    participante_id=participante.id,
                    enviado_em=enviado,
                    verificar_em=enviado + timedelta(days=7),
                    hipotese=HIPOTESE,
                    efeito=efeito,
                )
                db.add(evento)
                db.flush()
                _datar(db, "evento_proativo", evento.id, enviado)

        # --- Andar 3: as ordens do periodo, com medicao concluida ---
        for dados in ORDENS:
            agrupamento = AgrupamentoCausa(
                rotulo=dados["rotulo"],
                volume=dados["previsao"] * 2,
                cursos_afetados=[],
            )
            db.add(agrupamento)
            db.flush()

            emissao = ancora - timedelta(days=(SEMANAS - dados["semana_emissao"]) * 7)
            # A ordem pendente ainda nao foi implementada nem medida: ela e o
            # que o gestor tem para decidir hoje.
            implementada = (
                None
                if dados["semana_implementacao"] is None
                else ancora.date()
                - timedelta(days=(SEMANAS - dados["semana_implementacao"]) * 7)
            )
            ordem = OrdemCorrecao(
                agrupamento_id=agrupamento.id,
                hipotese=dados["hipotese"],
                evidencia=dados["evidencia"],
                acao=dados["acao"],
                previsao_queda_mensal=dados["previsao"],
                volume_base_mensal=dados["previsao"] * 2,
                implementada_em=implementada,
                medir_em=None if implementada is None else implementada + timedelta(days=30),
                resultado_medido=dados["medido"],
                situacao=dados["situacao"],
                conclusao=dados["conclusao"],
                impacto_estimado=dados["previsao"],
            )
            db.add(ordem)
            db.flush()
            _datar(db, "ordem_correcao", ordem.id, emissao)
            _datar(db, "agrupamento_causa", agrupamento.id, emissao)

        db.commit()

        return {
            "removido_da_execucao_anterior": removidos,
            "semanas": SEMANAS,
            "casos_criados": total_casos,
            "mensagens_proativas": sum(PROATIVAS),
            "hipoteses_confirmadas": sum(CONFIRMADAS),
            "ordens": len(ORDENS),
            "causas_extintas": sum(
                1 for o in ORDENS if o["situacao"] is SituacaoOrdem.CONFIRMADA
            ),
            "ordens_pendentes": sum(
                1 for o in ORDENS if o["situacao"] is SituacaoOrdem.PENDENTE
            ),
        }


def main() -> None:
    resultado = semear_historico()
    print("Historico semeado:")
    for chave, valor in resultado.items():
        print(f"  {chave}: {valor}")


if __name__ == "__main__":
    main()
