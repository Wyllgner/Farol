"""Testes da camada de seguranca.

Codigo puro, sem banco e sem rede: as tres garantias verificadas aqui
(segredo nunca aparece inteiro, superficie restrita exige token, gasto tem
teto) precisam valer mesmo com a infraestrutura toda fora do ar.
"""

import pytest
from fastapi import HTTPException

from app.config import settings
from app.seguranca import (
    LimitadorDeTaxa,
    TetoDeCusto,
    exigir_admin,
    mascarar,
    token_valido,
    verificar_configuracao,
)


class _RequisicaoFalsa:
    """O minimo que `exigir_admin` toca em uma Request."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client = None
        self.method = "POST"

        class _Url:
            path = "/demo/resetar"

        self.url = _Url()


# --------------------------------------------------------------------------
# Segredos
# --------------------------------------------------------------------------


def test_mascara_nunca_devolve_o_segredo_inteiro():
    chave = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    saida = mascarar(chave)
    assert chave not in saida
    assert saida.endswith(f"({len(chave)} car.)")


def test_segredo_curto_some_por_completo():
    """Com poucos caracteres, mostrar o final ja entrega quase tudo."""
    assert mascarar("123") == "***"
    assert mascarar("") == "(vazio)"


def test_producao_sem_token_nao_sobe(monkeypatch):
    monkeypatch.setattr(type(settings), "producao", property(lambda self: True))
    monkeypatch.setattr(settings, "admin_token", "", raising=False)
    problemas = verificar_configuracao()
    assert any("FAROL_ADMIN_TOKEN vazio" in p for p in problemas)


def test_producao_com_token_fraco_nao_sobe(monkeypatch):
    monkeypatch.setattr(type(settings), "producao", property(lambda self: True))
    monkeypatch.setattr(settings, "admin_token", "farol123", raising=False)
    assert any("curto demais" in p for p in verificar_configuracao())


def test_producao_com_origem_sem_tls_nao_sobe(monkeypatch):
    monkeypatch.setattr(type(settings), "producao", property(lambda self: True))
    monkeypatch.setattr(settings, "admin_token", "x" * 40, raising=False)
    monkeypatch.setattr(
        type(settings), "origens_web", property(lambda self: ["http://farol.emeron.jus.br"])
    )
    assert any("texto claro" in p for p in verificar_configuracao())


# --------------------------------------------------------------------------
# Superficie restrita
# --------------------------------------------------------------------------


def test_token_errado_nao_passa(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "token-secreto-de-verdade-1234", raising=False)
    assert not token_valido("token-secreto-de-verdade-1235")
    assert not token_valido(None)
    assert token_valido("token-secreto-de-verdade-1234")


def test_prefixo_correto_nao_e_aceito(monkeypatch):
    """Guarda contra comparacao ingenua por prefixo."""
    monkeypatch.setattr(settings, "admin_token", "abcdefghijklmnopqrstuvwx", raising=False)
    assert not token_valido("abcdefghij")


@pytest.mark.asyncio
async def test_console_exige_token_em_producao(monkeypatch):
    monkeypatch.setattr(type(settings), "producao", property(lambda self: True))
    monkeypatch.setattr(settings, "admin_token", "x" * 40, raising=False)
    with pytest.raises(HTTPException) as erro:
        await exigir_admin(_RequisicaoFalsa(), x_farol_token=None)
    assert erro.value.status_code == 401


@pytest.mark.asyncio
async def test_dev_sem_token_continua_aberto(monkeypatch):
    """`make dev` nao pode exigir segredo, ou a equipe inventa um fraco e fixo."""
    monkeypatch.setattr(type(settings), "producao", property(lambda self: False))
    monkeypatch.setattr(settings, "admin_token", "", raising=False)
    assert await exigir_admin(_RequisicaoFalsa(), x_farol_token=None) == "dev:aberto"


@pytest.mark.asyncio
async def test_dev_com_token_definido_passa_a_exigir(monkeypatch):
    monkeypatch.setattr(type(settings), "producao", property(lambda self: False))
    monkeypatch.setattr(settings, "admin_token", "y" * 40, raising=False)
    with pytest.raises(HTTPException):
        await exigir_admin(_RequisicaoFalsa(), x_farol_token="errado")


# --------------------------------------------------------------------------
# Limite e teto de gasto
# --------------------------------------------------------------------------


def test_limite_barra_a_partir_do_teto():
    limitador = LimitadorDeTaxa(limite=3, janela_segundos=60)
    assert all(limitador.permitir("ator") for _ in range(3))
    assert not limitador.permitir("ator")


def test_limite_e_por_ator():
    """Um visitante abusivo nao pode derrubar o atendimento dos outros."""
    limitador = LimitadorDeTaxa(limite=1, janela_segundos=60)
    assert limitador.permitir("ator-a")
    assert not limitador.permitir("ator-a")
    assert limitador.permitir("ator-b")


def test_teto_diario_para_de_liberar():
    teto = TetoDeCusto(teto=2)
    assert teto.consumir()
    assert teto.consumir()
    assert not teto.consumir()
    assert teto.estado == {"teto_diario": 2, "gastas_hoje": 2}


def test_teto_zero_significa_sem_limite():
    teto = TetoDeCusto(teto=0)
    assert all(teto.consumir() for _ in range(100))


def test_estourar_o_teto_degrada_em_vez_de_quebrar(monkeypatch):
    """A regra de produto: o FAROL responde pior, mas responde."""
    from app import seguranca
    from app.llm import provider_ativo

    monkeypatch.setattr(seguranca, "teto_llm", TetoDeCusto(teto=0))
    monkeypatch.setattr(seguranca.teto_llm, "consumir", lambda: False)
    assert provider_ativo().nome == "fallback"


# --------------------------------------------------------------------------
# Identificacao do ator atras de proxy
# --------------------------------------------------------------------------


class _RequisicaoComIp:
    def __init__(self, ip: str, encaminhado: str | None = None) -> None:
        class _Cliente:
            host = ip

        self.client = _Cliente()
        self.headers = {"x-forwarded-for": encaminhado} if encaminhado else {}


def test_sem_proxy_o_cabecalho_forjado_e_ignorado(monkeypatch):
    """Confiar em X-Forwarded-For sem proxy entrega o limite de bandeja."""
    from app.seguranca import identificar_ator

    monkeypatch.setattr(settings, "confiar_proxy", False, raising=False)
    real = identificar_ator(_RequisicaoComIp("203.0.113.7"))
    forjado = identificar_ator(_RequisicaoComIp("203.0.113.7", "1.2.3.4"))
    assert real == forjado


def test_com_proxy_vale_o_ultimo_da_lista(monkeypatch):
    """Os anteriores ao ultimo podem ter sido inventados pelo cliente."""
    from app.seguranca import identificar_ator

    monkeypatch.setattr(settings, "confiar_proxy", True, raising=False)
    monkeypatch.setattr(settings, "sal_auditoria", "sal", raising=False)
    a = identificar_ator(_RequisicaoComIp("10.0.0.1", "1.2.3.4, 198.51.100.9"))
    b = identificar_ator(_RequisicaoComIp("10.0.0.1", "9.9.9.9, 198.51.100.9"))
    assert a == b


def test_ator_nunca_carrega_o_ip_em_texto_claro(monkeypatch):
    from app.seguranca import identificar_ator

    monkeypatch.setattr(settings, "confiar_proxy", False, raising=False)
    ator = identificar_ator(_RequisicaoComIp("203.0.113.7"))
    assert "203.0.113.7" not in ator
    assert ator.startswith("anon:")


# --------------------------------------------------------------------------
# URL do banco entregue pela hospedagem
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entregue",
    [
        "postgres://u:s@host:5432/farol",
        "postgresql://u:s@host:5432/farol",
    ],
)
def test_url_da_hospedagem_ganha_o_driver_certo(monkeypatch, entregue):
    """Sem isto, o SQLAlchemy procura o psycopg2, que nao esta instalado."""
    from app.config import Settings

    s = Settings(database_url=entregue)
    assert s.url_do_banco == "postgresql+psycopg://u:s@host:5432/farol"


def test_url_ja_correta_nao_e_mexida():
    from app.config import Settings

    url = "postgresql+psycopg://u:s@host:5432/farol"
    assert Settings(database_url=url).url_do_banco == url
