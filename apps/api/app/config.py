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
    web_origin: str = "http://localhost:5173"

    # Modo Ensaio (F30): o motor gera a resposta mas nao envia; servidor aprova.
    # Comeca ligado por decisao de produto: nenhuma instituicao liga no dia 1
    # um sistema que fala em nome da Casa.
    modo_ensaio: bool = True


settings = Settings()
