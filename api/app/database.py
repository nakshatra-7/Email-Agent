import os
from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine


DEFAULT_SQLITE_URL = "sqlite:///./data/email.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)


def _sqlite_connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_sqlite_connect_args(DATABASE_URL),
)


def init_db() -> None:
    """Create the database and tables if they do not exist."""
    if DATABASE_URL.startswith("sqlite"):
        Path("./data").mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Provide a scoped session for FastAPI dependencies."""
    with Session(engine) as session:
        yield session
