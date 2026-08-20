from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# pool_size baixo de proposito: os planos gratuitos de Postgres limitam
# conexoes com folga pequena, e estourar o limite derruba o servico inteiro
# de um jeito que parece bug de aplicacao.
engine = create_engine(
    settings.url_do_banco,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
