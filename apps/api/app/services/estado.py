"""Estado individual do participante (secao 5.2, etapa 3).

"Como emito meu certificado?" quase nunca significa "nao sei o
procedimento". Significa "eu fiz e nao apareceu: o que esta errado
COMIGO?". Nenhum FAQ responde a uma pergunta cujo objeto e o estado
individual do usuario.

Este modulo e o unico ponto por onde dado pessoal entra na resposta, e
ele respeita o nivel de identidade por construcao: no nivel anonimo
devolve vazio, nao devolve "menos campos".
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Matricula
from app.services.identidade import Identidade


def _dias_ate(alvo: date | None, hoje: date) -> int | None:
    return None if alvo is None else (alvo - hoje).days


def montar(db: Session, identidade: Identidade) -> dict:
    """Estado do participante, limitado ao que o nivel permite revelar."""
    if not identidade.pode_ver_estado() or identidade.participante is None:
        # Nivel anonimo: nenhum dado pessoal, nem parcial.
        return {}

    hoje = datetime.now(UTC).date()
    matriculas = db.scalars(
        select(Matricula).where(Matricula.participante_id == identidade.participante.id)
    ).all()

    cursos = []
    for matricula in matriculas:
        ultimo_acesso = matricula.ultimo_acesso
        cursos.append(
            {
                "curso": matricula.curso.titulo,
                "progresso_pct": float(matricula.progresso),
                "nunca_acessou": ultimo_acesso is None,
                "dias_desde_ultimo_acesso": None
                if ultimo_acesso is None
                else (datetime.now(UTC) - ultimo_acesso).days,
                "dois_fatores_configurado": matricula.dois_fatores_configurado,
                "prazo_pessoal": matricula.prazo_pessoal.isoformat()
                if matricula.prazo_pessoal
                else None,
                "dias_ate_o_prazo": _dias_ate(matricula.prazo_pessoal, hoje),
                "situacao_certificado": str(matricula.situacao_certificado),
                "etapa_na_jornada": matricula.aresta_atual.origem
                if matricula.aresta_atual_id
                else None,
            }
        )

    return {
        # Minimizacao (secao 13): so o primeiro nome. Nunca CPF, nunca
        # e-mail completo: nada disso ajuda a responder a duvida.
        "primeiro_nome": identidade.participante.nome.split()[0],
        "perfil": str(identidade.participante.perfil),
        "cursos": cursos,
    }


# O resumo vai para dentro do prompt e volta, as vezes literalmente, na
# mensagem que a pessoa le. Entao ele e escrito em portugues, nao em
# identificador: "nao_elegivel" vazando para o WhatsApp denuncia o banco
# de dados por tras e nao significa nada para quem recebe.
_CERTIFICADO_EM_PORTUGUES = {
    "nao_elegivel": "certificado ainda nao liberado",
    "liberado": "certificado liberado para emissao",
    "emitido": "certificado ja emitido",
}


# Que campos do estado importam para cada assunto. O prompt pede ao
# modelo que cite so o que responde a pergunta, e o modelo obedece quase
# sempre: "quase" nao serve. Filtrar aqui e determinismo, nao pedido -
# o que nao entra no prompt nao tem como sair na resposta.
#
# Quem pergunta do 2FA nao pediu relatorio de matricula, e receber um
# faz o atendimento soar automatico justamente onde ele deveria soar
# atento.
_CAMPOS_POR_CATEGORIA: dict[str, tuple[str, ...]] = {
    "2fa": ("dois_fatores",),
    "senha": ("dois_fatores",),
    "acesso": ("dois_fatores", "acesso"),
    "prazo": ("prazo", "progresso"),
    "certificado": ("certificado", "progresso", "prazo"),
    "conteudo": ("progresso", "acesso"),
    "localizacao_curso": ("acesso",),
    "inscricao": ("acesso",),
    "webconferencia": (),
    "outros": (),
}

# Sem categoria conhecida, entrega tudo: o custo de um campo a mais e
# ruido, e o de um campo a menos e nao conseguir responder.
_TODOS_OS_CAMPOS = ("progresso", "acesso", "dois_fatores", "certificado", "prazo")


def resumir_para_prompt(estado: dict, categoria: str | None = None) -> str:
    """Converte o estado em texto curto para a geracao ancorada.

    `categoria` recorta o que entra: o modelo so pode mencionar o que
    recebeu, entao o filtro aqui vale mais que a instrucao no prompt.
    """
    if not estado:
        return ""

    campos = _TODOS_OS_CAMPOS if categoria is None else _CAMPOS_POR_CATEGORIA.get(
        str(categoria), _TODOS_OS_CAMPOS
    )

    linhas = [f"Participante: {estado['primeiro_nome']} ({estado['perfil']})"]
    for curso in estado["cursos"]:
        partes = []
        if "progresso" in campos:
            partes.append(f"progresso {curso['progresso_pct']:.0f}%")
        if "acesso" in campos:
            partes.append("nunca acessou" if curso["nunca_acessou"] else "ja acessou")
        if "dois_fatores" in campos:
            partes.append(
                "2FA configurado"
                if curso["dois_fatores_configurado"]
                else "2FA NAO configurado"
            )
        if "certificado" in campos:
            partes.append(
                _CERTIFICADO_EM_PORTUGUES.get(
                    str(curso["situacao_certificado"]),
                    "situacao do certificado indefinida",
                )
            )
        if "prazo" in campos and curso["dias_ate_o_prazo"] is not None:
            partes.append(f"faltam {curso['dias_ate_o_prazo']} dias para o prazo")

        # O nome do curso sai sempre: e ele que faz a resposta ser sobre
        # o caso da pessoa, e nao sobre "o curso" em abstrato.
        linhas.append(
            f"- {curso['curso']}: {', '.join(partes)}" if partes else f"- {curso['curso']}"
        )

    return "\n".join(linhas)
