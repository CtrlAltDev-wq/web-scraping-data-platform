"""SQLAlchemy engine and session factory.

SQLite is the default because it needs no server and keeps the project runnable with
one command. ``APP_DATABASE_URL`` can point at another database later without touching
the repository code.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings

# NullPool keeps no connections open between sessions. That matters on Windows: a
# lingering SQLite handle would stop tests from deleting their temporary directory.
ENGINE_OPTIONS: dict[str, object] = {"poolclass": NullPool, "future": True}


def create_db_engine(settings: Settings) -> Engine:
    """Build an engine for the configured database URL."""
    url = settings.resolved_database_url
    options = dict(ENGINE_OPTIONS)
    if url.startswith("sqlite"):
        # FastAPI runs sync endpoints in worker threads; SQLite otherwise refuses to
        # reuse a connection created on another thread.
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory producing short-lived sessions."""
    return sessionmaker(bind=engine, expire_on_commit=False)
