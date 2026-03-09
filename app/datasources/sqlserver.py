"""
SQL Server data source connector.

Connects to a SQL Server database via SQLAlchemy + pyodbc and executes
raw SQL queries. Install ``pyodbc`` and ``sqlalchemy`` to use this connector.

Implements the full ``BaseDataSource`` interface including
``test_connection``, ``list_collections`` (tables), and ``list_fields``
so the dashboard can show a live table/field picker to users.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)

# SQL Server data_type → normalised type string
_SQLSERVER_TYPE_MAP: dict[str, str] = {
    "varchar":    "text",
    "nvarchar":   "text",
    "char":       "text",
    "nchar":      "text",
    "text":       "text",
    "ntext":      "text",
    "uniqueidentifier": "text",
    "int":        "number",
    "bigint":     "number",
    "smallint":   "number",
    "tinyint":    "number",
    "decimal":    "number",
    "numeric":    "number",
    "float":      "number",
    "real":       "number",
    "money":      "number",
    "smallmoney": "number",
    "bit":        "bool",
    "datetime":   "date",
    "datetime2":  "date",
    "date":       "date",
    "time":       "date",
    "smalldatetime": "date",
    "datetimeoffset": "date",
    "xml":        "json",
}


class SqlServerDataSource(BaseDataSource):
    """Executes queries against a SQL Server database.

    Args:
        connection_string: SQLAlchemy-compatible connection string,
            e.g. ``mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17``.
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._engine = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Create the SQLAlchemy engine and verify the connection.

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

        logger.info("SQL Server connected via %s", self.connection_string[:40])

    def test_connection(self) -> bool:
        """Ping SQL Server with SELECT 1.

        Returns:
            ``True`` if the query succeeds.

        Raises:
            DataSourceError: If the connection or query fails.
        """
        self.connect()
        return True

    # ── Schema discovery ──────────────────────────────────────────────────────

    def list_collections(self) -> list[str]:
        """Return all user table names in the current database.

        Returns:
            Sorted list of table name strings.

        Raises:
            DataSourceError: If the query fails.
        """
        if not self._engine:
            self.connect()

        sql = (
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
        )
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                rows = conn.execute(text(sql))
                return [row[0] for row in rows]
        except Exception as exc:
            raise DataSourceError(
                "sqlserver", f"list_collections failed: {exc}"
            ) from exc

    def list_fields(self, collection: str) -> list[dict[str, str]]:
        """Return column names and normalised types for a table.

        Args:
            collection: Table name to inspect.

        Returns:
            List of ``{"name": ..., "type": ...}`` dicts.

        Raises:
            DataSourceError: If the query fails.
        """
        if not self._engine:
            self.connect()

        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = :table "
            "ORDER BY ORDINAL_POSITION"
        )
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                rows = conn.execute(text(sql), {"table": collection})
                return [
                    {
                        "name": row[0],
                        "type": _SQLSERVER_TYPE_MAP.get(row[1].lower(), "text"),
                    }
                    for row in rows
                ]
        except Exception as exc:
            raise DataSourceError(
                "sqlserver", f"list_fields for '{collection}' failed: {exc}"
            ) from exc

    # ── Data fetching ─────────────────────────────────────────────────────────

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
