"""Continuidade da conversa: a pergunta que depende da anterior.

"mas que curso e esse?" nao significa nada sozinha. O pipeline trata cada
mensagem como se fosse a primeira, entao essa frase virava uma consulta
semantica isolada, casava com o documento errado e produzia uma resposta
correta para uma pergunta que ninguem fez.

Aqui o problema e resolvido antes da recuperacao: quando a mensagem
depende da anterior, a consulta enviada a busca e a soma das duas, e a
geracao recebe o ultimo turno para resolver o "esse".

O reconhecimento e deterministico e olha para a FORMA da frase, nao para
o assunto: pronome sem referente, conector no inicio, ou brevidade. Sao
as marcas de que falta contexto, e nenhuma delas exige entender o tema.
"""

import re
import unicodedata
from datetime import timedelta

# Quanto da conversa conta como "esta sessao". A Conversa do FAROL nao
# termina nunca: ela e a linha do tempo daquela pessoa naquele canal, e
# pode ter meses. Mandar tudo para o prompt seria caro e, pior, faria uma
# duvida resolvida em marco contaminar a interpretacao de uma pergunta de
# agosto. A janela e o que aproxima "sessao" sem inventar um conceito de
# sessao que o WhatsApp nao tem.
JANELA_DE_SESSAO = timedelta(hours=2)
LIMITE_DE_MENSAGENS = 12

# Acima disso a mensagem ja se sustenta sozinha, mesmo que continue o
# assunto anterior.
MAXIMO_DE_PALAVRAS_DEPENDENTE = 6

# Pronomes e adverbios que apontam para algo dito antes. Sem o turno
# anterior, nao ha a que se referirem.
_ANAFORICOS = {
    "esse", "essa", "esses", "essas", "isso", "isto", "este", "esta",
    "ele", "ela", "eles", "elas", "dele", "dela", "disso", "nisso",
    "aquele", "aquela", "aquilo", "la", "ai", "dai", "ali", "mesmo",
}

# Conectores que abrem frase presa na anterior: "e o prazo?", "mas como?".
_CONECTORES_INICIAIS = {"mas", "e", "entao", "ai", "porem", "so", "ou", "nem"}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", limpo)).strip()


def eh_seguimento(texto: str) -> bool:
    """A mensagem depende do turno anterior para fazer sentido?

    Falso positivo aqui e barato: a consulta so fica um pouco mais longa,
    e a recuperacao continua trazendo o documento certo. Falso negativo e
    o que produz a resposta sobre o assunto errado.
    """
    normalizado = _normalizar(texto)
    if not normalizado:
        return False

    palavras = normalizado.split(" ")

    if palavras[0] in _CONECTORES_INICIAIS:
        return True

    if any(p in _ANAFORICOS for p in palavras):
        return True

    return len(palavras) <= MAXIMO_DE_PALAVRAS_DEPENDENTE


# Palavras que nao carregam assunto: nao ajudam a busca a encontrar
# documento nenhum, e a presenca delas nao significa que a pergunta se
# sustenta sozinha.
_SEM_ASSUNTO = _ANAFORICOS | _CONECTORES_INICIAIS | {
    "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "para", "pra", "por", "com", "que", "qual", "quais",
    "quando", "como", "onde", "quanto", "quanta", "meu", "minha", "seu",
    "sua", "eu", "voce", "vc", "e", "ja", "ainda", "sim", "nao", "ser",
    "esta", "estao", "tem", "vai", "fica", "falta", "faltam", "mesmo",
}


def tem_assunto_proprio(texto: str) -> bool:
    """A pergunta traz um termo que a busca pode usar sozinha?

    "e o certificado?" depende do turno anterior para ser LIDA, mas nao
    para ser BUSCADA: "certificado" ja encontra o documento certo. Juntar
    o assunto anterior nesse caso e o que fazia a pergunta nova ser
    respondida com o tema da anterior.
    """
    palavras = _normalizar(texto).split(" ")
    return any(p not in _SEM_ASSUNTO and len(p) >= 4 for p in palavras)


def consulta_com_contexto(pergunta: str, pergunta_anterior: str) -> str:
    """Consulta de recuperacao que carrega o assunto do turno anterior.

    Soma as duas em vez de substituir: a mensagem nova pode estar
    trocando de assunto, e nesse caso o termo novo tem que competir na
    busca em pe de igualdade.
    """
    if not pergunta_anterior.strip():
        return pergunta
    return f"{pergunta_anterior}\n{pergunta}"


def ultima_pergunta(historico: list[tuple[str, str]]) -> str:
    """A ultima coisa que a PESSOA disse antes da mensagem atual."""
    for quem, texto in reversed(historico):
        if quem == "entrada":
            return texto
    return ""


def bloco_de_contexto(historico: list[tuple[str, str]]) -> str:
    """A sessao inteira, para a geracao resolver pronome e elipse.

    Recebe pares (quem, texto) em ordem cronologica, ja recortados pela
    janela de sessao. Vai para o prompt como contexto de LEITURA, nunca
    como fonte: o que pode sustentar afirmacao continua sendo so o trecho
    oficial e o estado individual, e a verificacao de ancoragem nao ganha
    excecao por causa disto.

    A distincao importa mais do que parece. A resposta anterior do FAROL
    esta neste bloco, e ela contem prazos e percentuais. Se o historico
    valesse como fonte, um numero errado dito uma vez viraria verdade
    permanente por citacao circular do proprio sistema.
    """
    if not historico:
        return ""

    linhas = [f"{'Pessoa' if quem == 'entrada' else 'FAROL'}: {texto}" for quem, texto in historico]
    return (
        "[Conversa ate aqui, so para entender a pergunta. NAO e fonte e nao "
        "sustenta afirmacao nenhuma]\n" + "\n".join(linhas)
    )
