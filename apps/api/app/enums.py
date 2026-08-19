"""Vocabulario controlado do FAROL.

Estes enums nao sao detalhe de implementacao: a Politica de Triagem (secao 5.3)
e deterministica e opera sobre eles. Alterar um valor aqui altera o comportamento
institucional do sistema.
"""

from enum import StrEnum


class Perfil(StrEnum):
    MAGISTRADO = "magistrado"
    SERVIDOR = "servidor"
    ESTUDANTE = "estudante"
    DOCENTE = "docente"
    EXTERNO = "externo"


class NivelIdentidade(StrEnum):
    """Secao 5.1: dado pessoal nunca sai no nivel anonimo."""

    ANONIMO = "anonimo"
    RECONHECIDO = "reconhecido"
    VERIFICADO = "verificado"


class Canal(StrEnum):
    WHATSAPP = "whatsapp"
    WIDGET_AVA = "widget_ava"
    EMAIL = "email"
    TELEFONE = "telefone"


class Categoria(StrEnum):
    """As 12 categorias de intencao da secao 5.2."""

    ACESSO = "acesso"
    SENHA = "senha"
    DOIS_FATORES = "2fa"
    LOCALIZACAO_CURSO = "localizacao_curso"
    PRAZO = "prazo"
    WEBCONFERENCIA = "webconferencia"
    CERTIFICADO = "certificado"
    INSCRICAO = "inscricao"
    CONTEUDO = "conteudo"
    RECLAMACAO = "reclamacao"
    SENSIVEL = "sensivel"
    OUTROS = "outros"


# Secao 5.3: estas categorias escalam SEMPRE, independentemente da confianca.
CATEGORIAS_SENSIVEIS: frozenset[Categoria] = frozenset(
    {Categoria.SENSIVEL, Categoria.RECLAMACAO}
)


class DecisaoTriagem(StrEnum):
    RESPONDE = "responde"
    RESPONDE_COM_OFERTA_HUMANA = "responde_com_oferta_humana"
    ESCALA = "escala"


class SituacaoCaso(StrEnum):
    ABERTO = "aberto"
    RESPONDIDO = "respondido"
    ESCALADO = "escalado"
    ENCERRADO = "encerrado"


class ContratoResolucao(StrEnum):
    """Secao 5.5: o laco do Andar 2."""

    ABERTO = "aberto"
    CONFIRMADO = "confirmado"
    FALHOU = "falhou"
    SEM_RETORNO = "sem_retorno"


class SituacaoDocumento(StrEnum):
    VIGENTE = "vigente"
    EM_REVISAO = "em_revisao"
    REBAIXADO = "rebaixado"
    VENCIDO = "vencido"


class SituacaoCertificado(StrEnum):
    NAO_ELEGIVEL = "nao_elegivel"
    LIBERADO = "liberado"
    EMITIDO = "emitido"


class Direcao(StrEnum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class EfeitoAntecipacao(StrEnum):
    """Secao 4.4: a hipotese verificavel de toda mensagem proativa."""

    PENDENTE = "pendente"
    CONFIRMADO = "confirmado"  # nao abriu atendimento: o atendimento foi evitado
    REFUTADO = "refutado"  # abriu mesmo assim: o gatilho nao funcionou


class SituacaoOrdem(StrEnum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    IMPLEMENTADA = "implementada"
    CONFIRMADA = "confirmada"  # previsao bateu: causa extinta
    DESCARTADA = "descartada"  # previsao falhou: hipotese descartada
