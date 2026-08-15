"""Estado individual do participante (secao 5.2, etapa 3).

"Como emito meu certificado?" quase nunca significa "nao sei o
procedimento". Significa "eu fiz e nao apareceu — o que esta errado
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
        # e-mail completo — nada disso ajuda a responder a duvida.
        "primeiro_nome": identidade.participante.nome.split()[0],
        "perfil": str(identidade.participante.perfil),
        "cursos": cursos,
    }


def resumir_para_prompt(estado: dict) -> str:
    """Converte o estado em texto curto para a geracao ancorada."""
    if not estado:
        return ""

    linhas = [f"Participante: {estado['primeiro_nome']} ({estado['perfil']})"]
    for curso in estado["cursos"]:
        partes = [
            f"progresso {curso['progresso_pct']:.0f}%",
            "nunca acessou" if curso["nunca_acessou"] else "ja acessou",
            "2FA configurado"
            if curso["dois_fatores_configurado"]
            else "2FA NAO configurado",
            f"certificado: {curso['situacao_certificado']}",
        ]
        if curso["dias_ate_o_prazo"] is not None:
            partes.append(f"faltam {curso['dias_ate_o_prazo']} dias para o prazo")
        linhas.append(f"- {curso['curso']}: {', '.join(partes)}")

    return "\n".join(linhas)
