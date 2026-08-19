"""entrega diferida da mensagem proativa

Enviar e entregar sao coisas diferentes. Ate aqui o motor de antecipacao
tratava as duas como uma so: debitava o orcamento de atencao e abria a
hipotese no momento em que MONTAVA a mensagem, mesmo quando ela nao
chegava a ninguem (canal sem adaptador, aba do espelho fechada). A
verificacao entao fechava essas hipoteses como confirmadas, creditando ao
gatilho antecipacoes que nunca existiram.

`entregue_em` e o que separa as duas coisas: nulo significa "na fila".
`evento_proativo_id` liga a mensagem a hipotese que ela abre, para que o
relogio da verificacao comece a contar na entrega, e nao antes.

Revision ID: 091060d120a4
Revises: 39eeedd904b1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "091060d120a4"
down_revision: str | None = "39eeedd904b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# O autogenerate propos derrubar o indice HNSW de `chunk.vetor`, que ele
# nao enxerga por ser especifico do pgvector. Nao ha nada de errado com o
# indice: ele fica onde esta.


def upgrade() -> None:
    op.add_column(
        "mensagem", sa.Column("entregue_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("mensagem", sa.Column("evento_proativo_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "mensagem_evento_proativo_id_fkey",
        "mensagem",
        "evento_proativo",
        ["evento_proativo_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Tudo que ja existia foi de fato mostrado a alguem: marcar como
    # entregue evita que o historico apareca como fila pendente e seja
    # reenviado na primeira conexao.
    op.execute("UPDATE mensagem SET entregue_em = criado_em")


def downgrade() -> None:
    op.drop_constraint("mensagem_evento_proativo_id_fkey", "mensagem", type_="foreignkey")
    op.drop_column("mensagem", "evento_proativo_id")
    op.drop_column("mensagem", "entregue_em")
