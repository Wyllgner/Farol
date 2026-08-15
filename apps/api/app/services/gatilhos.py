"""Motor de gatilhos proativos (secao 4.2).

As regras vivem em YAML e nao em codigo: o servidor edita sem programador,
e a tela de transparencia publica o mesmo arquivo que o motor executa.

Este modulo so AVALIA condicoes. Quem decide se a mensagem vale a
interrupcao e o orcamento de atencao, e quem julga se o gatilho continua
valendo a pena e a verificacao de efeito.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path

import yaml

from app.models import Matricula

CAMINHO_REGRAS = Path(__file__).resolve().parent.parent / "gatilhos" / "regras.yaml"


@dataclass(slots=True)
class Gatilho:
    chave: str
    titulo: str
    ativo: bool
    aresta: str
    categoria: str
    condicoes: dict
    custo_atendimento_min: int
    probabilidade_evitar: float
    mensagem: str
    acoes: list[str]


@dataclass(slots=True)
class Regras:
    gatilhos: list[Gatilho]
    janela_dias: int
    limiar_efetividade: float
    amostra_minima: int
    saldo_inicial: int
    valor_esperado_minimo: float
    ignoradas_para_reduzir: int

    def por_chave(self, chave: str) -> Gatilho | None:
        return next((g for g in self.gatilhos if g.chave == chave), None)


@lru_cache(maxsize=1)
def carregar() -> Regras:
    dados = yaml.safe_load(CAMINHO_REGRAS.read_text(encoding="utf-8"))
    verificacao = dados["verificacao"]
    orcamento = dados["orcamento"]
    return Regras(
        gatilhos=[Gatilho(**g) for g in dados["gatilhos"]],
        janela_dias=verificacao["janela_dias"],
        limiar_efetividade=verificacao["limiar_efetividade"],
        amostra_minima=verificacao["amostra_minima"],
        saldo_inicial=orcamento["saldo_inicial"],
        valor_esperado_minimo=orcamento["valor_esperado_minimo"],
        ignoradas_para_reduzir=orcamento["ignoradas_para_reduzir"],
    )


def recarregar() -> Regras:
    """Editar o YAML nao deveria exigir reiniciar o processo."""
    carregar.cache_clear()
    return carregar()


# --------------------------------------------------------------------------
# Avaliacao de condicoes
# --------------------------------------------------------------------------


def _horas_ate_proxima_webconferencia(matricula: Matricula, agora: datetime) -> float | None:
    proximas = []
    for encontro in matricula.curso.webconferencias or []:
        try:
            quando = datetime.fromisoformat(encontro["quando"])
        except (KeyError, ValueError):
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=UTC)
        delta = (quando - agora).total_seconds() / 3600
        if delta >= 0:
            proximas.append(delta)
    return min(proximas) if proximas else None


def avaliar(gatilho: Gatilho, matricula: Matricula, agora: datetime) -> bool:
    """Diz se esta matricula satisfaz as condicoes do gatilho."""
    condicoes = gatilho.condicoes
    hoje: date = agora.date()

    if condicoes.get("nunca_acessou") and matricula.ultimo_acesso is not None:
        return False
    if condicoes.get("ja_acessou") and matricula.ultimo_acesso is None:
        return False

    if (minimo := condicoes.get("dias_desde_inscricao_min")) is not None and (
        hoje - matricula.data_inscricao
    ).days < minimo:
        return False

    if (
        esperado := condicoes.get("dois_fatores_configurado")
    ) is not None and matricula.dois_fatores_configurado != esperado:
        return False

    if (maximo := condicoes.get("dias_ate_prazo_max")) is not None:
        if matricula.prazo_pessoal is None:
            return False
        dias = (matricula.prazo_pessoal - hoje).days
        # Prazo ja vencido nao e antecipacao, e constrangimento.
        if dias < 0 or dias > maximo:
            return False

    if (teto := condicoes.get("progresso_max")) is not None and float(
        matricula.progresso
    ) > teto:
        return False

    if (situacao := condicoes.get("certificado")) is not None and str(
        matricula.situacao_certificado
    ) != situacao:
        return False

    if (minimo := condicoes.get("dias_desde_liberacao_min")) is not None:
        # Sem data de liberacao explicita no modelo, usamos o ultimo acesso
        # como aproximacao de quando a pessoa poderia ter visto o aviso.
        referencia = matricula.ultimo_acesso
        if referencia is None or (agora - referencia).days < minimo:
            return False

    if (teto := condicoes.get("webconferencia_em_horas_max")) is not None:
        horas = _horas_ate_proxima_webconferencia(matricula, agora)
        if horas is None or horas > teto:
            return False

    return True


def montar_mensagem(gatilho: Gatilho, matricula: Matricula, agora: datetime) -> str:
    hoje = agora.date()
    dias_ate_prazo = (
        (matricula.prazo_pessoal - hoje).days if matricula.prazo_pessoal else 0
    )
    texto = gatilho.mensagem.format(
        primeiro_nome=matricula.participante.nome.split()[0],
        curso=matricula.curso.titulo,
        progresso=f"{float(matricula.progresso):.0f}",
        dias_ate_prazo=dias_ate_prazo,
    ).strip()

    # Opt-out em TODA mensagem proativa (secao 4.3). Nao e cortesia: e o
    # que separa antecipacao de spam institucional.
    return f"{texto}\n\n_Se preferir nao receber avisos, responda PARAR._"
