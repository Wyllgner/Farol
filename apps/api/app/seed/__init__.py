"""Semeadura do mundo ficticio.

Dados 100% ficticios, conforme a regra do desafio.

A distribuicao dos 60 participantes nao e aleatoria: ela e desenhada para
que cada um dos cinco gatilhos proativos tenha populacao real para agir,
e para que os tres niveis de identidade aparecam na demonstracao. Um seed
que gera 60 pessoas em estado saudavel nao exercita nada.
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Canal, NivelIdentidade, Perfil, SituacaoCertificado, SituacaoDocumento
from app.models import (
    ArestaJornada,
    Curso,
    DocumentoConhecimento,
    Matricula,
    Participante,
)
from app.seed.documentos import DOCUMENTOS, resolver_validade
from app.seed.jornada import ARESTAS
from app.services.conhecimento import indexar

# Semente fixa: a demonstracao precisa ser reproduzivel. Uma demo que muda
# a cada reset e uma demo que pode falhar na frente da banca.
random.seed(42)

NOMES = [
    "Ana Beatriz Moraes", "Carlos Eduardo Lima", "Mariana Souza Rocha",
    "Joao Pedro Alencar", "Fernanda Ribeiro Dias", "Rafael Augusto Pinto",
    "Juliana Campos Neves", "Marcos Vinicius Barros", "Patricia Gomes Freitas",
    "Bruno Henrique Castro", "Camila Andrade Nunes", "Diego Martins Oliveira",
    "Larissa Fonseca Melo", "Thiago Cardoso Ramos", "Aline Teixeira Braga",
    "Gustavo Henrique Sa", "Renata Peixoto Cunha", "Felipe Moreira Duarte",
    "Beatriz Carvalho Pires", "Leonardo Vieira Matos", "Tatiane Correia Lopes",
    "Rodrigo Antunes Reis", "Vanessa Coelho Prado", "Andre Luiz Bastos",
    "Priscila Xavier Amorim", "Eduardo Tavares Nogueira", "Simone Barbosa Leal",
    "Vitor Hugo Macedo", "Carolina Esteves Pontes", "Alexandre Faria Guedes",
    "Natalia Siqueira Rangel", "Paulo Cesar Mendonca", "Isabela Fontes Aragao",
    "Ricardo Novaes Quirino", "Debora Lacerda Vilela", "Fabio Junqueira Salles",
    "Luciana Prates Bittencourt", "Sergio Murilo Caldas", "Amanda Rezende Portela",
    "Otavio Bandeira Coutinho", "Cristiane Valadares Pimenta", "Henrique Assis Boaventura",
    "Sabrina Loureiro Feitosa", "Danilo Estrela Marinho", "Roberta Cintra Magalhaes",
    "Emerson Padilha Tavora", "Michele Arruda Sampaio", "Wagner Trindade Bezerra",
    "Aline Cristina Verissimo", "Murilo Paiva Fontenele", "Elisa Monteiro Wanderley",
    "Caio Bernardes Ferraz", "Rosana Aguiar Espindola", "Nelson Batista Queiroz",
    "Bianca Toledo Sarmento", "Igor Vasconcelos Pedrosa", "Silvia Rocha Albuquerque",
    "Arthur Nascimento Bulhoes", "Milena Drummond Sobral", "Cesar Augusto Linhares",
]

CURSOS = [
    ("Direito Digital e Protecao de Dados na Atividade Judiciaria", 60, 45),
    ("Gestao Processual e Produtividade em Varas Civeis", 45, 30),
    ("Linguagem Simples em Decisoes Judiciais", 30, 20),
]


def _limpar(db) -> None:
    """Reset idempotente: a demonstracao nunca pode falhar por estado sujo."""
    for modelo in (Matricula, Participante, Curso, DocumentoConhecimento, ArestaJornada):
        for registro in db.scalars(select(modelo)).all():
            db.delete(registro)
    db.flush()


def _semear_jornada(db) -> dict[str, ArestaJornada]:
    arestas = {}
    for origem, destino, taxa in ARESTAS:
        aresta = ArestaJornada(
            origem=origem, destino=destino, taxa_travamento=Decimal(str(taxa)), volume=0
        )
        db.add(aresta)
        arestas[origem] = aresta
    db.flush()
    return arestas


def _semear_cursos(db, hoje: date) -> list[Curso]:
    cursos = []
    for indice, (titulo, dias_duracao, dias_decorridos) in enumerate(CURSOS):
        inicio = hoje - timedelta(days=dias_decorridos)
        fim = inicio + timedelta(days=dias_duracao)
        curso = Curso(
            titulo=titulo,
            data_inicio=inicio,
            data_fim=fim,
            prazo_conclusao=fim,
            modulos=[
                {"ordem": n, "titulo": f"Modulo {n}"} for n in range(1, 5)
            ],
            webconferencias=[
                {
                    "titulo": "Encontro sincrono de abertura",
                    "quando": (inicio + timedelta(days=7)).isoformat(),
                    "modulo": 2,
                },
                {
                    "titulo": "Encontro sincrono de encerramento",
                    # O primeiro curso tem uma webconferencia proxima, para
                    # que o gatilho de "webconferencia em 1 hora" tenha alvo.
                    "quando": (
                        hoje + timedelta(days=0 if indice == 0 else 12)
                    ).isoformat(),
                    "modulo": 4,
                },
            ],
        )
        db.add(curso)
        cursos.append(curso)
    db.flush()
    return cursos


def _perfil_de(indice: int) -> Perfil:
    if indice % 10 == 0:
        return Perfil.MAGISTRADO
    if indice % 7 == 0:
        return Perfil.DOCENTE
    if indice % 5 == 0:
        return Perfil.EXTERNO
    if indice % 2 == 0:
        return Perfil.SERVIDOR
    return Perfil.ESTUDANTE


def _semear_participantes(db, cursos: list[Curso], arestas, hoje: date) -> dict:
    """Distribui os 60 participantes pelos estados que os gatilhos observam."""
    agora = datetime.now(UTC)
    contagem = {
        "nunca_acessou": 0,
        "sem_2fa": 0,
        "prazo_apertado": 0,
        "webconferencia_proxima": 0,
        "certificado_parado": 0,
        "saudavel": 0,
    }

    for indice, nome in enumerate(NOMES):
        perfil = _perfil_de(indice)
        primeiro = nome.split()[0].lower()
        ultimo = nome.split()[-1].lower()

        # Publico externo entra anonimo: o produto continua util sem cadastro,
        # e um dado pessoal nunca sai nesse nivel.
        if perfil is Perfil.EXTERNO:
            nivel = NivelIdentidade.ANONIMO
        elif indice % 6 == 0:
            nivel = NivelIdentidade.VERIFICADO
        else:
            nivel = NivelIdentidade.RECONHECIDO

        participante = Participante(
            nome=nome,
            email=f"{primeiro}.{ultimo}@exemplo.jus.br",
            telefone=f"+5569{90000000 + indice:08d}",
            perfil=perfil,
            canal_preferido=Canal.WIDGET_AVA if indice % 9 == 0 else Canal.WHATSAPP,
            nivel_identidade=nivel,
            saldo_atencao=4,
            aceita_avisos=indice % 17 != 0,  # alguns ja optaram por nao receber
        )
        db.add(participante)
        db.flush()

        curso = cursos[indice % len(cursos)]
        estado = indice % 6
        ultimo_acesso = agora - timedelta(days=random.randint(0, 6))
        progresso = Decimal(str(round(random.uniform(35, 95), 2)))
        tem_2fa = True
        certificado = SituacaoCertificado.NAO_ELEGIVEL
        prazo = curso.prazo_conclusao
        aresta = arestas["consumo_conteudo"]

        if estado == 0:
            # Gatilho 1: inscrito ha mais de 2 dias e nunca acessou.
            ultimo_acesso = None
            progresso = Decimal("0.00")
            tem_2fa = False
            aresta = arestas["inscricao"]
            contagem["nunca_acessou"] += 1
        elif estado == 1:
            # Gatilho 2: acessou mas nao configurou o 2FA.
            tem_2fa = False
            progresso = Decimal(str(round(random.uniform(5, 25), 2)))
            aresta = arestas["primeiro_acesso"]
            contagem["sem_2fa"] += 1
        elif estado == 2:
            # Gatilho 3: faltam 3 dias para o prazo e progresso abaixo de 70%.
            prazo = hoje + timedelta(days=3)
            progresso = Decimal(str(round(random.uniform(20, 65), 2)))
            aresta = arestas["atividades"]
            contagem["prazo_apertado"] += 1
        elif estado == 3:
            # Gatilho 4: webconferencia proxima (curso 0 tem encontro hoje).
            curso = cursos[0]
            aresta = arestas["consumo_conteudo"]
            contagem["webconferencia_proxima"] += 1
        elif estado == 4:
            # Gatilho 5: certificado liberado e nao retirado ha mais de 2 dias.
            progresso = Decimal("100.00")
            certificado = SituacaoCertificado.LIBERADO
            ultimo_acesso = agora - timedelta(days=random.randint(3, 9))
            aresta = arestas["certificado"]
            contagem["certificado_parado"] += 1
        else:
            certificado = (
                SituacaoCertificado.EMITIDO if progresso >= 90 else SituacaoCertificado.NAO_ELEGIVEL
            )
            contagem["saudavel"] += 1

        db.add(
            Matricula(
                participante_id=participante.id,
                curso_id=curso.id,
                data_inscricao=curso.data_inicio,
                ultimo_acesso=ultimo_acesso,
                progresso=progresso,
                dois_fatores_configurado=tem_2fa,
                prazo_pessoal=prazo,
                situacao_certificado=certificado,
                aresta_atual_id=aresta.id,
            )
        )

    db.flush()
    return contagem


async def _semear_conhecimento(db, hoje: date) -> tuple[int, int]:
    total_trechos = 0
    vencidos = 0
    for titulo, dono, dias, conteudo in DOCUMENTOS:
        valido_ate = resolver_validade(dias, hoje)
        expirado = valido_ate is not None and valido_ate < hoje
        if expirado:
            vencidos += 1

        documento = DocumentoConhecimento(
            titulo=titulo,
            conteudo=conteudo,
            dono=dono,
            valido_ate=valido_ate,
            situacao=SituacaoDocumento.VENCIDO if expirado else SituacaoDocumento.VIGENTE,
            aprovado_por_servidor=True,
        )
        db.add(documento)
        db.flush()
        # O vencido tambem e indexado de proposito: o filtro precisa provar
        # que exclui uma fonte que existe e casa semanticamente, nao uma
        # fonte que simplesmente nao esta no banco.
        total_trechos += await indexar(db, documento)

    return total_trechos, vencidos


async def semear() -> dict:
    hoje = datetime.now(UTC).date()
    with SessionLocal() as db:
        _limpar(db)
        arestas = _semear_jornada(db)
        cursos = _semear_cursos(db, hoje)
        contagem = _semear_participantes(db, cursos, arestas, hoje)
        trechos, vencidos = await _semear_conhecimento(db, hoje)
        db.commit()

    return {
        "cursos": len(cursos),
        "participantes": len(NOMES),
        "arestas_jornada": len(ARESTAS),
        "documentos": len(DOCUMENTOS),
        "documentos_vencidos": vencidos,
        "trechos_indexados": trechos,
        "distribuicao": contagem,
    }


def main() -> None:
    resultado = asyncio.run(semear())
    print("Semeadura concluida:")
    for chave, valor in resultado.items():
        print(f"  {chave}: {valor}")


if __name__ == "__main__":
    main()
