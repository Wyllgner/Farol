"""Fluxos guiados executaveis (secao 5.4).

Para procedimentos que ja falharam como texto — o 2FA e o caso
emblematico, com banner e video publicados e o volume intacto — o FAROL
ACOMPANHA em vez de orientar.

Orientar nao e o mesmo que acompanhar. Foi por isso que o video nao
funcionou: ele entrega os cinco passos de uma vez e vai embora. Aqui cada
passo tem verificacao, caminho alternativo e progresso visivel, e duas
falhas consecutivas escalam para humano automaticamente.

O FAROL nunca executa operacao de credencial: ele aciona o fluxo oficial
da plataforma e acompanha a pessoa ate o fim.
"""

from dataclasses import dataclass, field

from app.enums import Categoria

# Duas falhas consecutivas escalam. Insistir uma terceira vez e o erro
# que o proprio documento aponta: repetir a orientacao que ja falhou.
LIMITE_FALHAS = 2

SIM = "Consegui"
NAO = "Nao consegui"
OUTRA = "Estou vendo outra coisa"


@dataclass(slots=True)
class Passo:
    chave: str
    instrucao: str
    # A pergunta de verificacao e o que separa acompanhar de orientar.
    verificacao: str
    # O que dizer quando a pessoa responde que nao conseguiu. Repetir a
    # mesma instrucao seria o banner de novo, so que mais lento.
    alternativa: str
    opcoes: list[str] = field(default_factory=lambda: [SIM, NAO, OUTRA])


@dataclass(slots=True)
class Fluxo:
    chave: str
    titulo: str
    categoria: Categoria
    passos: list[Passo]

    @property
    def total(self) -> int:
        return len(self.passos)


FLUXO_2FA = Fluxo(
    chave="2fa",
    titulo="Configurar a autenticacao em dois fatores",
    categoria=Categoria.DOIS_FATORES,
    passos=[
        Passo(
            chave="perfil",
            instrucao=(
                "Vamos configurar juntos. No AVA, clique no seu nome no canto "
                "superior direito e escolha *Meu Perfil*. Depois, abra a aba "
                "*Seguranca*."
            ),
            verificacao="Encontrou a aba Seguranca?",
            alternativa=(
                "Sem problema. Se o menu do seu nome nao abrir, role a pagina "
                "ate o rodape: o link *Meu Perfil* tambem fica la. A aba "
                "Seguranca e a terceira da lista."
            ),
        ),
        Passo(
            chave="ativar",
            instrucao=(
                "Agora clique em *Ativar autenticacao em dois fatores*. Deve "
                "aparecer uma tela com um QR Code — aquele quadrado preto e "
                "branco."
            ),
            verificacao="A tela com o QR Code apareceu?",
            alternativa=(
                "Se o botao estiver cinza, o 2FA ja pode estar ativo nesta "
                "conta. Nesse caso a propria tela mostra a opcao "
                "*Reconfigurar*. Clique nela para gerar um QR Code novo."
            ),
        ),
        Passo(
            chave="aplicativo",
            instrucao=(
                "No celular, abra um aplicativo autenticador — Google "
                "Authenticator ou Microsoft Authenticator servem. Toque em "
                "*adicionar* e escolha *Ler QR Code*. Aponte a camera para a "
                "tela do computador."
            ),
            verificacao="O aplicativo passou a mostrar um codigo de 6 digitos?",
            alternativa=(
                "Se voce nao tem o aplicativo, baixe *Google Authenticator* na "
                "loja do seu celular — e gratuito. Se a camera nao le o codigo, "
                "a mesma tela do AVA mostra uma chave em texto logo abaixo do "
                "QR: escolha *inserir chave manualmente* no aplicativo."
            ),
        ),
        Passo(
            chave="confirmar",
            instrucao=(
                "Digite no AVA o codigo de 6 digitos que o aplicativo esta "
                "mostrando e confirme. Atencao: o codigo muda a cada 30 "
                "segundos."
            ),
            verificacao="O codigo foi aceito?",
            alternativa=(
                "Codigo recusado quase sempre e relogio do celular fora de "
                "hora. Ative *data e hora automaticas* nas configuracoes do "
                "aparelho e tente com o proximo codigo. Se o contador estiver "
                "acabando, espere o proximo antes de digitar."
            ),
        ),
        Passo(
            chave="recuperacao",
            instrucao=(
                "Ultimo passo: a tela mostra os *codigos de recuperacao*. "
                "Salve-os em lugar seguro — eles sao a unica forma de entrar "
                "se voce perder o acesso ao celular."
            ),
            verificacao="Conseguiu salvar os codigos?",
            alternativa=(
                "Se a tela ja fechou, os codigos podem ser gerados de novo em "
                "Meu Perfil, aba Seguranca, opcao *Codigos de recuperacao*."
            ),
        ),
    ],
)

FLUXOS: dict[str, Fluxo] = {FLUXO_2FA.chave: FLUXO_2FA}


@dataclass(slots=True)
class Estado:
    """Onde a pessoa esta no fluxo. Vive na conversa, nao em memoria."""

    fluxo: str
    passo: int = 0
    falhas_consecutivas: int = 0
    # True quando o passo ja foi apresentado e esperamos a verificacao.
    aguardando_verificacao: bool = False

    def como_json(self) -> dict:
        return {
            "fluxo": self.fluxo,
            "passo": self.passo,
            "falhas_consecutivas": self.falhas_consecutivas,
            "aguardando_verificacao": self.aguardando_verificacao,
        }

    @classmethod
    def de_json(cls, dados: dict | None) -> "Estado | None":
        if not dados:
            return None
        return cls(**dados)


@dataclass(slots=True)
class Passo_Resposta:
    texto: str
    acoes_rapidas: list[str]
    estado: Estado | None
    escalar: bool = False
    concluido: bool = False


def _cabecalho(fluxo: Fluxo, indice: int) -> str:
    """Progresso visivel: a pessoa precisa saber quanto falta."""
    return f"*Passo {indice + 1} de {fluxo.total}*"


def iniciar(chave: str) -> Passo_Resposta:
    fluxo = FLUXOS[chave]
    passo = fluxo.passos[0]
    return Passo_Resposta(
        texto=f"{_cabecalho(fluxo, 0)}\n{passo.instrucao}\n\n{passo.verificacao}",
        acoes_rapidas=passo.opcoes,
        estado=Estado(fluxo=chave, passo=0, aguardando_verificacao=True),
    )


def avancar(estado: Estado, resposta: str) -> Passo_Resposta:
    """Processa a verificacao de um passo e decide o que vem depois."""
    fluxo = FLUXOS[estado.fluxo]
    passo = fluxo.passos[estado.passo]
    conseguiu = resposta.strip().lower() == SIM.lower()

    if conseguiu:
        proximo = estado.passo + 1
        if proximo >= fluxo.total:
            return Passo_Resposta(
                texto=(
                    "Pronto, o dois fatores esta configurado. A partir de agora "
                    "o AVA vai pedir o codigo do aplicativo a cada acesso.\n\n"
                    "Foi util?"
                ),
                acoes_rapidas=["Sim, resolvido", "Ainda tenho duvida"],
                estado=None,
                concluido=True,
            )

        seguinte = fluxo.passos[proximo]
        return Passo_Resposta(
            texto=(
                f"{_cabecalho(fluxo, proximo)}\n{seguinte.instrucao}\n\n"
                f"{seguinte.verificacao}"
            ),
            acoes_rapidas=seguinte.opcoes,
            # Acertar zera o contador: duas falhas seguidas e o sinal, nao
            # duas falhas ao longo de todo o fluxo.
            estado=Estado(
                fluxo=estado.fluxo, passo=proximo, aguardando_verificacao=True
            ),
        )

    falhas = estado.falhas_consecutivas + 1

    if falhas >= LIMITE_FALHAS:
        # Escalonamento automatico. O FAROL nao repete pela terceira vez.
        return Passo_Resposta(
            texto=(
                "Esse passo nao esta destravando, e insistir aqui so tomaria "
                "mais o seu tempo. Ja encaminhei seu caso para um servidor da "
                "SECOEAD com tudo o que tentamos, e voce recebera retorno por "
                "este mesmo canal."
            ),
            acoes_rapidas=[],
            estado=None,
            escalar=True,
        )

    return Passo_Resposta(
        texto=f"{passo.alternativa}\n\n{passo.verificacao}",
        acoes_rapidas=passo.opcoes,
        estado=Estado(
            fluxo=estado.fluxo,
            passo=estado.passo,
            falhas_consecutivas=falhas,
            aguardando_verificacao=True,
        ),
    )


def deve_oferecer(categoria: Categoria, estado_participante: dict) -> str | None:
    """Decide se vale propor o fluxo em vez de so responder por texto.

    So oferece quando o estado individual mostra que a pessoa de fato nao
    configurou: propor a quem ja tem 2FA seria ruido.
    """
    if categoria is not Categoria.DOIS_FATORES:
        return None

    for curso in estado_participante.get("cursos", []):
        if not curso.get("dois_fatores_configurado"):
            return FLUXO_2FA.chave

    # Sem estado individual (anonimo), a oferta ainda faz sentido: o
    # procedimento e publico e nao revela nada.
    if not estado_participante:
        return FLUXO_2FA.chave

    return None
