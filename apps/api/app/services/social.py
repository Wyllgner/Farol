"""Conversa social: o que chega antes da pergunta.

Saudacao, agradecimento, despedida e confirmacao nao sao perguntas. Elas
nao tem fonte oficial que as sustente, e por isso o pipeline de resolucao
as tratava como duvida sem lastro e escalava para um servidor. Escalar um
"oi" gasta o tempo de quem atende e ensina a pessoa que o canal nao
conversa.

O reconhecimento aqui e deterministico e conservador, pelas mesmas razoes
do opt-out: e codigo puro sobre vocabulario fechado, nenhuma chamada de
modelo. E conservador na direcao certa: na duvida, devolve None e a
mensagem segue para o pipeline normal. Confundir uma pergunta real com
uma saudacao seria o unico erro caro deste modulo.

As respostas sao texto fixo institucional. Elas nao afirmam nada sobre o
caso da pessoa nem sobre regra da Escola, entao nao ha o que ancorar: e a
unica classe de resposta que pode sair sem fonte.
"""

import re
import unicodedata
from enum import StrEnum

# Mensagem social e curta por natureza. O limite existe para que
# "bom dia, meu certificado nao sai" nunca seja lido como "bom dia".
MAXIMO_DE_PALAVRAS = 6


class Intencao(StrEnum):
    SAUDACAO = "saudacao"
    AGRADECIMENTO = "agradecimento"
    DESPEDIDA = "despedida"
    RECONHECIMENTO = "reconhecimento"
    APRESENTACAO = "apresentacao"


# Frases inteiras: quem pergunta o que o FAROL e merece resposta sobre o
# FAROL, nao uma busca na base de conhecimento da Escola.
_APRESENTACAO = {
    "quem e voce",
    "quem e vc",
    "quem fala",
    "com quem eu falo",
    "com quem estou falando",
    "o que voce faz",
    "o que vc faz",
    "o que voce pode fazer",
    "voce e um robo",
    "voce e um bot",
    "voce e humano",
    "isso e um robo",
    "como voce pode me ajudar",
    "no que voce pode ajudar",
    "voce pode me ajudar",
    "pode me ajudar",
    "preciso de ajuda",
    "ajuda",
}

# Palavras que nao mudam a natureza da mensagem e podem aparecer em
# qualquer um dos grupos.
_NEUTRAS = {"por", "favor", "entao", "muito", "mto", "ja", "e"}

_NUCLEOS: dict[Intencao, set[str]] = {
    Intencao.AGRADECIMENTO: {
        "obrigado", "obrigada", "obg", "brigado", "brigada",
        "valeu", "vlw", "grato", "grata", "agradecido", "agradecida",
    },
    Intencao.DESPEDIDA: {
        "tchau", "adeus", "flw", "falou", "abraco", "abracos", "xau", "ate",
    },
    Intencao.SAUDACAO: {
        "oi", "ola", "opa", "eai", "salve", "alo", "hey", "oie", "bom", "boa",
        # "e ai" e "e ae" chegam separadas depois da normalizacao.
        "ai", "ae",
    },
    Intencao.RECONHECIMENTO: {
        "ok", "okay", "certo", "entendi", "entendido", "sim", "blz", "beleza",
        "show", "joia", "perfeito", "legal", "otimo", "bacana", "isso",
    },
}

# Palavras que acompanham o nucleo sem trocar a intencao: "bom dia",
# "tudo bem", "ate mais", "obrigado mesmo".
_SATELITES: dict[Intencao, set[str]] = {
    Intencao.AGRADECIMENTO: {"mesmo", "demais", "ajuda", "tudo", "por", "isso"},
    Intencao.DESPEDIDA: {"ate", "mais", "logo", "breve", "amanha", "depois"},
    Intencao.SAUDACAO: {
        "dia", "tarde", "noite", "tudo", "bem", "bom", "boa", "como", "vai",
        "voce", "vc", "esta", "ta", "td", "blz", "beleza",
    },
    Intencao.RECONHECIMENTO: {"tudo", "bem", "esta", "ta", "entao"},
}

# A ordem resolve as sobreposicoes: "obrigado, ate mais" e despedida
# agradecida, mas o agradecimento e o que a pessoa quis dizer, e
# "boa noite" no fim da conversa continua sendo lido como saudacao,
# porque responder saudacao a quem se despede custa menos que o contrario.
_PRIORIDADE = (
    Intencao.AGRADECIMENTO,
    Intencao.DESPEDIDA,
    Intencao.SAUDACAO,
    Intencao.RECONHECIMENTO,
)

# Tudo que pode aparecer numa mensagem puramente social. O que estiver
# fora disto e assunto, e assunto vai para o pipeline.
_VOCABULARIO_SOCIAL = (
    _NEUTRAS
    | set().union(*_NUCLEOS.values())
    | set().union(*_SATELITES.values())
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    # Pontuacao e emoji saem: "oi!!" e "oi 👋" sao "oi".
    return re.sub(r"[^a-z0-9\s]", " ", limpo).strip()


def detectar(texto: str) -> Intencao | None:
    """Devolve a intencao social da mensagem, ou None se for pergunta.

    None e a resposta segura: significa "isto segue para o pipeline".
    """
    normalizado = re.sub(r"\s+", " ", _normalizar(texto))
    if not normalizado:
        return None

    if normalizado in _APRESENTACAO:
        return Intencao.APRESENTACAO

    palavras = normalizado.split(" ")
    if len(palavras) > MAXIMO_DE_PALAVRAS:
        return None

    # Uma unica palavra fora do vocabulario social ja indica que ha uma
    # pergunta ali dentro: "oi, esqueci minha senha" e sobre a senha.
    if any(p not in _VOCABULARIO_SOCIAL for p in palavras):
        return None

    # Mensagem inteiramente social: a prioridade decide qual das intencoes
    # presentes responder ("obrigado, ate mais" e agradecimento).
    for intencao in _PRIORIDADE:
        if any(p in _NUCLEOS[intencao] for p in palavras):
            return intencao

    return None


# O FAROL se apresenta pelo que resolve, nao pela tecnologia que usa.
_APRESENTACAO_TEXTO = (
    "Aqui é o FAROL, o atendimento da Seção de Educação a Distância da "
    "EMERON. Ajudo com acesso ao AVA, senha, autenticação em dois fatores, "
    "prazos, webconferência e certificado. Quando não sei, encaminho para um "
    "servidor da SECOEAD."
)

_TEXTOS: dict[Intencao, str] = {
    Intencao.SAUDACAO: (
        "Oi{nome}! Aqui é o FAROL, da SECOEAD. Ajudo com acesso ao AVA, senha, "
        "prazos, webconferência e certificado. O que você precisa?"
    ),
    Intencao.APRESENTACAO: _APRESENTACAO_TEXTO,
    Intencao.AGRADECIMENTO: (
        "Por nada{nome}. Se precisar de mais alguma coisa, é só chamar."
    ),
    Intencao.DESPEDIDA: (
        "Até logo{nome}. Qualquer dúvida do curso, é só escrever por aqui."
    ),
    Intencao.RECONHECIMENTO: (
        "Combinado{nome}. Se aparecer outra dúvida, é só escrever."
    ),
}


def responder(intencao: Intencao, primeiro_nome: str = "") -> str:
    """Texto fixo, com o nome quando a pessoa foi reconhecida no canal."""
    nome = f", {primeiro_nome}" if primeiro_nome else ""
    return _TEXTOS[intencao].format(nome=nome)
