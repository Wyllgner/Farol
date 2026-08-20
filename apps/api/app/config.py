from functools import cached_property

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://farol:farol@localhost:5434/farol"

    # openai | anthropic | fallback
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Os dois papeis sao configuraveis em separado de proposito. Classificar
    # em 12 categorias e barato; a geracao ancorada e onde o sistema nao pode
    # inventar (secao 5.2), entao ela deve poder subir de modelo sozinha.
    llm_model_classificacao: str = "gpt-5-nano"
    llm_model_geracao: str = "gpt-5-nano"

    # Embeddings: openai = mesma chave do LLM; local = offline, sem custo.
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_model_local: str = "intfloat/multilingual-e5-base"
    # Precisa bater com o provedor:
    # text-embedding-3-small = 1536, multilingual-e5-base = 768.
    embedding_dim: int = 1536

    channel_adapter: str = "mirror"

    api_port: int = 8000
    # Aceita mais de uma origem separada por virgula: o mesmo backend serve
    # o dominio publico e o de homologacao sem precisar de outro deploy.
    web_origin: str = "http://localhost:5173"

    # === Seguranca ===
    # dev | producao. Nao e enfeite: em producao o boot recusa configuracao
    # insegura, /docs some e o token do administrador passa a ser obrigatorio.
    ambiente: str = "dev"

    # Protege o Console de Demonstracao e a tela "Como o FAROL decide".
    # Vazio em dev = superficies abertas na maquina local; vazio em
    # producao = o processo nao sobe.
    # Aceita FAROL_ADMIN_TOKEN (nome usado no deploy, sem colidir com outro
    # servico no mesmo host) ou ADMIN_TOKEN.
    admin_token: str = Field(
        default="",
        validation_alias=AliasChoices("FAROL_ADMIN_TOKEN", "ADMIN_TOKEN", "admin_token"),
    )

    # Entra no hash do IP na trilha de auditoria. Sem ele, o hash e
    # reversivel por forca bruta (o espaco de IPv4 e pequeno).
    sal_auditoria: str = Field(
        default="farol-dev",
        validation_alias=AliasChoices("FAROL_SAL_AUDITORIA", "SAL_AUDITORIA", "sal_auditoria"),
    )

    # Ligar somente quando houver um proxy reverso na frente (a hospedagem,
    # o Caddy, o nginx). Ver a nota em seguranca.identificar_ator: com isto
    # desligado, X-Forwarded-For e ignorado.
    confiar_proxy: bool = False

    # Hospedeiros aceitos no cabecalho Host, separados por virgula.
    # Vazio = qualquer um (util em dev e atras de proxy confiavel).
    hosts_confiaveis: str = ""

    # Teto de requisicoes por minuto, por origem.
    limite_req_min: int = 120
    # As rotas que chamam o provedor tem limite proprio, bem mais apertado:
    # sao as unicas que gastam credito.
    limite_llm_min: int = 12
    # Orcamento diario de chamadas ao provedor. Estourou, o motor degrada
    # para o fallback deterministico em vez de continuar gastando. 0 = sem teto.
    teto_llm_dia: int = 2000

    # Assinatura do webhook da Cloud API (X-Hub-Signature-256). Vazio =
    # sem verificacao, aceitavel so enquanto o canal e o espelho local.
    whatsapp_app_secret: str = ""

    # Modo Ensaio (F30): o motor gera a resposta mas nao envia; servidor aprova.
    # Comeca ligado por decisao de produto: nenhuma instituicao liga no dia 1
    # um sistema que fala em nome da Casa.
    modo_ensaio: bool = True

    @cached_property
    def url_do_banco(self) -> str:
        """Normaliza a URL para o driver que o projeto usa.

        As hospedagens entregam DATABASE_URL no formato historico
        `postgres://` ou `postgresql://`, que o SQLAlchemy resolve para o
        psycopg2 (nao instalado aqui). Corrigir no codigo evita depender de
        alguem lembrar de reescrever a variavel a cada deploy.
        """
        url = self.database_url
        for prefixo in ("postgresql+psycopg://", "postgresql+asyncpg://"):
            if url.startswith(prefixo):
                return url
        for antigo in ("postgresql://", "postgres://"):
            if url.startswith(antigo):
                return "postgresql+psycopg://" + url[len(antigo) :]
        return url

    @cached_property
    def producao(self) -> bool:
        return self.ambiente.strip().lower() in {"producao", "prod", "production"}

    @cached_property
    def origens_web(self) -> list[str]:
        return [o.strip() for o in self.web_origin.split(",") if o.strip()]

    @cached_property
    def hosts(self) -> list[str]:
        return [h.strip() for h in self.hosts_confiaveis.split(",") if h.strip()]


settings = Settings()
