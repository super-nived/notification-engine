"""
SQL Server data source connector.

Connects to a SQL Server database via SQLAlchemy + pyodbc and executes
raw SQL queries. Install ``pyodbc`` to use this connector.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)


class SqlServerDataSource(BaseDataSource):
    """Executes raw SQL queries against a SQL Server database.

    Args:
        connection_string: SQLAlchemy-compatible connection string,
            e.g. ``mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17``.
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._engine = None

    def connect(self) -> None:
        """Create the SQLAlchemy engine for SQL Server.

        Raises:
            DataSourceError: If the engine cannot be created or pinged.

        Returns:
            None
        """
        try:
            from sqlalchemy import create_engine, text
            self._engine = create_engine(self.connection_string)
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise DataSourceError(
                "sqlserver", f"Connection failed: {exc}"
            ) from exc

        logger.info("SQL Server connected via %s", self.connection_string[:30])

    def fetch(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a raw SQL query and return rows as dicts.

        Supported ``query`` keys:
            sql    (str):   Required. Raw SQL string to execute.
            params (dict):  Optional. Bind parameters for the query.

        Args:
            query: Dict with the keys described above.

        Returns:
            List of row dicts, one per result row.

        Raises:
            DataSourceError: If the query fails.
        """
        if not self._engine:
            self.connect()

        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(query["sql"]),
                    query.get("params", {}),
                )
                return [dict(row._mapping) for row in result]
        except Exception as exc:
            raise DataSourceError(
                "sqlserver", f"Query failed: {exc}"
            ) from exc
