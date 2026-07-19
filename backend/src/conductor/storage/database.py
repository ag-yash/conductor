"""Database engine lifecycle and SQLite filesystem preparation."""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlmodel import Session


class Database:
    """Own one SQLAlchemy engine and create short-lived sessions."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._prepare_sqlite_directory(url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _configure_sqlite_connection)

    def session(self) -> Session:
        """Create a new transaction-scoped session."""

        return Session(self.engine)

    def check_connection(self) -> None:
        """Fail if the database cannot answer a trivial query."""

        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        """Release pooled database resources."""

        self.engine.dispose()

    @staticmethod
    def _prepare_sqlite_directory(url: str) -> None:
        parsed = make_url(url)
        if parsed.drivername != "sqlite" or not parsed.database or parsed.database == ":memory:":
            return
        Path(parsed.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enforce references and wait briefly for concurrent writers."""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
