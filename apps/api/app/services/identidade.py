"""Identidade progressiva (secao 5.1).

Tres niveis de acesso, escalando conforme a confianca na identidade.
Um dado pessoal NUNCA sai no nivel anonimo.

O produto continua util no nivel anonimo: o que cobre o publico externo
nao cadastrado, ignorado na maioria das solucoes.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Canal, NivelIdentidade
from app.models import Participante

# Um codigo curto, valido por pouco tempo. Nao e autenticacao real: no
# hackathon nada e, mas o contrato da funcao ja e o de producao.
VALIDADE_CODIGO = timedelta(minutes=15)

# Desafios pendentes em memoria: some no restart, e isso e correto para
# um codigo de verificacao.
_desafios: dict[str, tuple[str, datetime]] = {}


@dataclass(slots=True)
class Identidade:
    nivel: NivelIdentidade
    participante: Participante | None = None

    @property
    def eh_anonimo(self) -> bool:
        return self.nivel is NivelIdentidade.ANONIMO

    def pode_ver_estado(self) -> bool:
        """Progresso, prazo pessoal, situacao do certificado."""
        return self.nivel in (NivelIdentidade.RECONHECIDO, NivelIdentidade.VERIFICADO)

    def pode_ver_sensivel(self) -> bool:
        """Dado sensivel e acao que afeta o cadastro."""
        return self.nivel is NivelIdentidade.VERIFICADO


def resolver(db: Session, canal: Canal, handle: str) -> Identidade:
    """Reconhece o interlocutor pelo identificador do canal.

    Bater com o cadastro concede o nivel Reconhecido, nao mais que isso.
    """
    if not handle:
        return Identidade(nivel=NivelIdentidade.ANONIMO)

    coluna = Participante.email if canal is Canal.EMAIL else Participante.telefone
    participante = db.scalar(select(Participante).where(coluna == handle))

    if participante is None:
        return Identidade(nivel=NivelIdentidade.ANONIMO)

    # O nivel Verificado nunca e herdado do cadastro: ele exige o desafio
    # por e-mail institucional, feito nesta conversa.
    return Identidade(nivel=NivelIdentidade.RECONHECIDO, participante=participante)


def emitir_desafio(participante: Participante) -> str:
    """Gera o codigo enviado ao e-mail institucional.

    Em producao o codigo sai por e-mail e nunca retorna pela API. Aqui ele
    e devolvido para a demonstracao: o adaptador de e-mail e o que muda.
    """
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    _desafios[str(participante.id)] = (
        hashlib.sha256(codigo.encode()).hexdigest(),
        datetime.now(UTC) + VALIDADE_CODIGO,
    )
    return codigo


def confirmar_desafio(db: Session, participante: Participante, codigo: str) -> Identidade:
    """Eleva ao nivel Verificado se o codigo conferir e estiver no prazo."""
    guardado = _desafios.get(str(participante.id))
    if guardado is None:
        return Identidade(nivel=NivelIdentidade.RECONHECIDO, participante=participante)

    esperado, expira_em = guardado
    if datetime.now(UTC) > expira_em:
        _desafios.pop(str(participante.id), None)
        return Identidade(nivel=NivelIdentidade.RECONHECIDO, participante=participante)

    # Comparacao em tempo constante: o codigo e curto e adivinhavel por
    # forca bruta se o tempo de resposta vazar informacao.
    if not secrets.compare_digest(
        esperado, hashlib.sha256(codigo.encode()).hexdigest()
    ):
        return Identidade(nivel=NivelIdentidade.RECONHECIDO, participante=participante)

    _desafios.pop(str(participante.id), None)
    participante.nivel_identidade = NivelIdentidade.VERIFICADO
    db.flush()
    return Identidade(nivel=NivelIdentidade.VERIFICADO, participante=participante)
