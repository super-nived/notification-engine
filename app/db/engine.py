"""
Internal SQLite database engine setup.

Provides the SQLAlchemy engine, session factory, declarative base,
and FastAPI dependency. Call ``init_db()`` once at startup to create
all tables defined in ``app.db.models``.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from typing import Generator

from app.core.settings import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    Opens a session before the request and closes it after, even if
    an exception occurs.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables defined in ``app.db.models``.

    Imports models to ensure they are registered with ``Base`` before
    ``create_all`` is called. Safe to call multiple times — tables are
    only created if they do not already exist.

    Returns:
        None
    """
    import app.db.models  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised at %s", settings.DB_PATH)
