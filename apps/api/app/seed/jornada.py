"""Grafo da jornada do participante (secao 4.1).

O motor nao opera sobre regras escritas a mao, e sim sobre este grafo.
Cada aresta carrega uma taxa de travamento observada; quando uma aresta
trava acima da media, o FAROL age ali — inclusive em pontos que ninguem
programou.

E a mesma estrutura usada pelo Andar 3 para localizar onde a duvida
nasce, o que elimina duplicacao conceitual entre os dois andares.
"""

# (origem, destino, taxa_travamento_inicial)
#
# As taxas sao a hipotese de partida, derivadas do que o proprio desafio
# relata como dor: 2FA e webconferencia ja receberam banner e video e
# mesmo assim seguem gerando atendimento. O sistema mede e corrige.
ARESTAS: list[tuple[str, str, float]] = [
    ("inscricao", "primeiro_acesso", 0.18),
    ("primeiro_acesso", "configuracao_2fa", 0.34),
    ("configuracao_2fa", "localizacao_curso", 0.22),
    ("localizacao_curso", "consumo_conteudo", 0.11),
    ("consumo_conteudo", "webconferencia", 0.29),
    ("webconferencia", "atividades", 0.14),
    ("atividades", "prazo", 0.19),
    ("prazo", "conclusao", 0.16),
    ("conclusao", "certificado", 0.24),
    ("certificado", "concluido", 0.07),
]

# Media das taxas acima. O Andar 1 age nas arestas que superam isso.
TAXA_MEDIA = sum(taxa for _, _, taxa in ARESTAS) / len(ARESTAS)
