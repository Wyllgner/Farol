"""Log de auditoria (secao 7.5).

Toda interacao e registrada: entrada, classificacao, fontes recuperadas,
confianca calculada, decisao de triagem, resposta gerada, acao do servidor.
Rastreabilidade completa — requisito nao negociavel em ambiente judiciario.

A tabela e append-only imposto por trigger no banco: nem este modulo nem
um bug em outro lugar conseguem reescrever o que ja foi registrado.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import LogAuditoria


def registrar(
    db: Session,
    etapa: str,
    payload: dict[str, Any],
    caso_id: uuid.UUID | None = None,
) -> None:
    """Grava uma etapa da interacao.

    Nunca levanta excecao para o chamador: perder a auditoria e grave, mas
    derrubar o atendimento de quem esta do outro lado e pior. A falha vai
    para o log da aplicacao e o atendimento segue.
    """
    try:
        db.add(LogAuditoria(caso_id=caso_id, etapa=etapa, payload=payload))
        db.flush()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("falha ao registrar auditoria: %s", etapa)
