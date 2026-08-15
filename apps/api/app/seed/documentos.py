"""Base de conhecimento publica da SECOEAD.

Conteudo ficticio, conforme a regra do desafio, mas modelado sobre as
orientacoes que o setor de fato publica.

Todo documento tem dono e validade (secao 7.2): conteudo com data expira
ao fim do curso, e fonte vencida nao responde. Um documento aqui esta
deliberadamente vencido — e o caso que prova que o filtro de vigencia
funciona, e nao apenas que existe.
"""

from datetime import date

# (titulo, dono, dias_de_validade_a_partir_de_hoje, conteudo)
# dias = None  -> sem data de validade (procedimento atemporal)
# dias < 0     -> ja vencido
DOCUMENTOS: list[tuple[str, str, int | None, str]] = [
    (
        "Primeiro acesso ao AVA",
        "Coordenacao SECOEAD",
        None,
        "O acesso ao Ambiente Virtual de Aprendizagem da EMERON e feito pelo "
        "endereco ava.emeron.jus.br. O login e o seu CPF, sem pontos ou traco. "
        "A senha inicial e enviada para o e-mail informado na inscricao, no "
        "assunto 'Bem-vindo a EMERON'. No primeiro acesso o sistema pede a "
        "troca da senha inicial por uma de sua escolha. Se o e-mail de boas-"
        "vindas nao aparecer na caixa de entrada, verifique a pasta de spam "
        "antes de solicitar reenvio.",
    ),
    (
        "Redefinicao de senha",
        "Suporte SECOEAD",
        None,
        "Para redefinir a senha, use o link 'Esqueci minha senha' na tela de "
        "login do AVA. Informe o CPF cadastrado e o sistema enviara um link de "
        "redefinicao para o e-mail da inscricao. O link vale por 2 horas. A "
        "SECOEAD nao redefine senha de participante: a redefinicao e sempre "
        "feita pelo proprio usuario atraves desse fluxo, por seguranca. Se o "
        "e-mail cadastrado estiver desatualizado, e necessario abrir chamado "
        "com a Secretaria Academica para atualizacao do cadastro.",
    ),
    (
        "Configuracao da autenticacao em dois fatores (2FA)",
        "Suporte SECOEAD",
        None,
        "A autenticacao em dois fatores e obrigatoria para acesso ao AVA. Para "
        "configurar: entre em Meu Perfil, clique em Seguranca e depois em "
        "Ativar autenticacao em dois fatores. A tela exibira um QR Code. Abra "
        "um aplicativo autenticador no celular (Google Authenticator, Microsoft "
        "Authenticator ou similar), escolha 'Ler QR Code' e aponte a camera "
        "para a tela. O aplicativo passara a exibir um codigo de 6 digitos que "
        "muda a cada 30 segundos. Digite o codigo exibido no campo de "
        "confirmacao do AVA para concluir. Guarde os codigos de recuperacao "
        "exibidos ao final: eles sao a unica forma de entrar se voce perder o "
        "acesso ao celular.",
    ),
    (
        "Codigo do 2FA recusado",
        "Suporte SECOEAD",
        None,
        "Se o codigo de 6 digitos for recusado, a causa mais comum e o relogio "
        "do celular fora de sincronia. Ative o ajuste automatico de data e hora "
        "nas configuracoes do aparelho e tente novamente. O codigo tambem expira "
        "em 30 segundos: se o contador estiver quase no fim, espere o proximo "
        "codigo antes de digitar. Se o problema persistir apos essas duas "
        "verificacoes, use um codigo de recuperacao e reconfigure o "
        "autenticador do zero.",
    ),
    (
        "Onde encontrar os cursos em que estou inscrito",
        "Coordenacao SECOEAD",
        None,
        "Apos entrar no AVA, os cursos em que voce esta inscrito aparecem no "
        "Painel, na secao 'Meus cursos'. Se o painel estiver vazio, verifique "
        "o filtro no topo da lista: por padrao ele mostra apenas cursos em "
        "andamento, e cursos futuros ou ja encerrados ficam ocultos. Cursos "
        "aparecem no painel somente apos a homologacao da inscricao, que ocorre "
        "em ate 2 dias uteis apos o encerramento do periodo de inscricoes.",
    ),
    (
        "Acesso as webconferencias",
        "Coordenacao SECOEAD",
        None,
        "As webconferencias sao realizadas dentro do proprio AVA. O link de "
        "acesso fica na pagina do curso, dentro do modulo correspondente a data "
        "do encontro, identificado pelo icone de camera. A sala abre 15 minutos "
        "antes do horario marcado. Recomenda-se usar navegador Chrome ou Edge "
        "atualizado e testar microfone e camera antes do inicio. As sessoes sao "
        "gravadas e a gravacao fica disponivel no mesmo local em ate 48 horas "
        "apos o encontro.",
    ),
    (
        "Emissao do certificado",
        "Secretaria Academica",
        None,
        "O certificado e liberado automaticamente quando duas condicoes sao "
        "atendidas: frequencia minima de 75% nas atividades e conclusao de "
        "todas as atividades avaliativas obrigatorias do curso. Uma vez "
        "liberado, acesse a pagina do curso e clique em 'Emitir certificado'. "
        "O documento e gerado em PDF com codigo de validacao. Se o botao nao "
        "aparecer, ha pendencia em alguma atividade: consulte o Relatorio de "
        "Progresso na pagina do curso para identificar qual.",
    ),
    (
        "Certificado nao aparece apos a conclusao",
        "Secretaria Academica",
        None,
        "Se voce concluiu todas as atividades e o botao de emitir certificado "
        "nao aparece, a causa mais comum e uma atividade marcada como concluida "
        "mas nao enviada — rascunhos salvos nao contam como entrega. Verifique "
        "no Relatorio de Progresso se todas as atividades estao com situacao "
        "'Enviado'. O processamento da liberacao tambem pode levar ate 24 horas "
        "apos a ultima entrega. Passado esse prazo com todas as atividades "
        "enviadas, o caso precisa de analise da Secretaria Academica.",
    ),
    (
        "Prazos e entregas",
        "Coordenacao SECOEAD",
        None,
        "Cada curso tem um prazo final de conclusao informado na pagina inicial "
        "do curso e no e-mail de boas-vindas. Atividades enviadas apos o prazo "
        "nao sao computadas para fins de certificacao. O sistema encerra o envio "
        "automaticamente na data limite, as 23h59 do horario de Rondonia. "
        "Prorrogacao de prazo individual e excecao e depende de analise da "
        "coordenacao mediante justificativa.",
    ),
    (
        "Inscricao em cursos",
        "Secretaria Academica",
        None,
        "As inscricoes sao abertas pelo portal da EMERON e divulgadas por edital "
        "e por e-mail institucional. Cada edital informa publico-alvo, numero de "
        "vagas, criterios de selecao e periodo de inscricao. Magistrados e "
        "servidores do TJRO usam o login unico institucional. Publico externo "
        "faz cadastro previo no portal antes de se inscrever. A confirmacao da "
        "inscricao chega por e-mail apos a homologacao.",
    ),
    (
        "Materiais e videoaulas",
        "Coordenacao SECOEAD",
        None,
        "Os materiais de cada curso ficam organizados por modulo na pagina do "
        "curso. Textos e apostilas estao em PDF e podem ser baixados. As "
        "videoaulas sao hospedadas na plataforma Emeron Play e reproduzidas "
        "dentro do proprio AVA, sem necessidade de login adicional. Se o video "
        "nao carregar, atualize a pagina e verifique se ha bloqueador de "
        "anuncios ativo, que pode impedir a reproducao.",
    ),
    (
        "Registro de frequencia e progresso",
        "Coordenacao SECOEAD",
        None,
        "O progresso e calculado automaticamente pelo AVA conforme voce conclui "
        "as atividades de cada modulo. O Relatorio de Progresso, na pagina do "
        "curso, mostra o que ja foi concluido e o que falta. A leitura de "
        "material so e computada quando o arquivo e efetivamente aberto no "
        "sistema — baixar o PDF sem abrir nao registra progresso.",
    ),
    (
        "Atualizacao de dados cadastrais",
        "Secretaria Academica",
        None,
        "Nome, e-mail e telefone podem ser atualizados pelo proprio participante "
        "em Meu Perfil no AVA. Alteracao de CPF ou de nome civil exige envio de "
        "documento comprobatorio a Secretaria Academica, por se tratar de dado "
        "que consta no certificado. O e-mail cadastrado e o canal oficial de "
        "comunicacao do curso: mantenha-o atualizado.",
    ),
    (
        "Canais de atendimento da SECOEAD",
        "Coordenacao SECOEAD",
        None,
        "O atendimento da SECOEAD funciona de segunda a sexta, das 7h as 13h, "
        "pelo WhatsApp institucional, pelo e-mail secoead@emeron.jus.br e por "
        "telefone. Solicitacoes recebidas fora do horario sao respondidas no "
        "proximo dia util. Questoes sobre conteudo do curso devem ser dirigidas "
        "ao docente pelo forum do proprio curso.",
    ),
    (
        "Calendario de webconferencias do semestre anterior",
        "Coordenacao SECOEAD",
        -30,  # vencido de proposito: prova que fonte vencida nao responde
        "As webconferencias do semestre anterior ocorreram as tercas-feiras, as "
        "19h, na sala virtual do modulo 2. O encontro de encerramento foi "
        "realizado no ultimo dia util do semestre. Este calendario vale apenas "
        "para o semestre encerrado.",
    ),
]


def resolver_validade(dias: int | None, hoje: date) -> date | None:
    """Converte a validade relativa do seed em data absoluta."""
    if dias is None:
        return None
    return date.fromordinal(hoje.toordinal() + dias)
