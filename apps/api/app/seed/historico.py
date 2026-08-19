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
    EfeitoAntecipacao,
    SituacaoCaso,
    SituacaoOrdem,
)
from app.models import (
    AgrupamentoCausa,
    Caso,
    Conversa,
    EventoProativo,
    OrdemCorrecao,
    Participante,
)

# Mesma semente do seed principal: a demonstracao precisa ser reproduzivel.
random.seed(42)

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
HIPOTESE = (
    "Se esta orientacao chegar agora, esta pessoa nao precisara abrir "
    "atendimento sobre o assunto em 7 dias."
)


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
        casos = db.scalars(select(Caso).where(Caso.conversa_id.in_(ids))).all()
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
                handle_canal=p.telefone or f"anon-{p.id}",
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

            # --- Andar 1: mensagens proativas com hipotese ja verificada ---
            entregues = PROATIVAS[semana]
            confirmadas = CONFIRMADAS[semana]
            gatilhos_da_semana = [
                "sem_2fa", "webconferencia_hoje", "prazo_apertado",
                "certificado_parado", "nunca_acessou",
            ]
            for i in range(entregues):
                participante = random.choice(participantes)
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
            implementada = ancora.date() - timedelta(
                days=(SEMANAS - dados["semana_implementacao"]) * 7
            )
            ordem = OrdemCorrecao(
                agrupamento_id=agrupamento.id,
                hipotese=dados["hipotese"],
                evidencia=dados["evidencia"],
                acao=dados["acao"],
                previsao_queda_mensal=dados["previsao"],
                volume_base_mensal=dados["previsao"] * 2,
                implementada_em=implementada,
                medir_em=implementada + timedelta(days=30),
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
        }


def main() -> None:
    resultado = semear_historico()
    print("Historico semeado:")
    for chave, valor in resultado.items():
        print(f"  {chave}: {valor}")


if __name__ == "__main__":
    main()
