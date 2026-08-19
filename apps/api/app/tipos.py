"""Tipos de coluna do dominio.

Guardar enums como texto e a escolha certa (schema legivel, sem tipo
nativo do Postgres para migrar), mas o SQLAlchemy devolve `str` puro na
leitura. Isso quebra silenciosamente qualquer comparacao por identidade
`caso.situacao is SituacaoCaso.ESCALADO` vira False depois de um
reload, sem erro e sem aviso.

Este decorador reconstroi o enum na leitura, para que o objeto vindo do
banco seja indistinguivel do objeto recem-criado em memoria.
"""

from enum import StrEnum

from sqlalchemy import String, TypeDecorator


class EnumTexto(TypeDecorator):
    """Coluna de texto que devolve o membro do enum na leitura."""

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[StrEnum], length: int = 32, **kwargs):
        self.enum_class = enum_class
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return self.enum_class(value)
        except ValueError:
            # Valor gravado fora do vocabulario controlado. Devolvemos o
            # texto cru em vez de estourar: perder a leitura de uma linha
            # antiga seria pior que devolve-la sem tipo.
            return value
