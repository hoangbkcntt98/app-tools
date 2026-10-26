"""Small parameterized CRUD helpers for PostgreSQL and MySQL."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import section_config

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _identifier(value: str, driver: str) -> str:
    parts = value.split(".")
    if not parts or any(not _IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError(f"invalid SQL identifier: {value!r}")
    quote = "`" if driver == "mysql" else '"'
    return ".".join(f"{quote}{part}{quote}" for part in parts)


def _where(where: Mapping[str, Any], params: list[Any], driver: str) -> str:
    if not where:
        raise ValueError("where must not be empty")
    terms = []
    for key, value in where.items():
        column = _identifier(key, driver)
        if value is None:
            terms.append(f"{column} IS NULL")
        else:
            terms.append(f"{column} = %s")
            params.append(value)
    return " AND ".join(terms)


class DatabasePool:
    """Connection pool and safe table CRUD for PostgreSQL or MySQL.

    Configure `database.driver` as `postgresql` or `mysql`; credentials can
    live in config or be supplied to `create_database_pool`.
    """

    def __init__(self, pool: Any, driver: str) -> None:
        self.pool = pool
        self.driver = driver

    @classmethod
    def create(
        cls,
        config: Mapping[str, Any] | str | Path | None = None,
        *,
        settings: Mapping[str, Any] | None = None,
    ) -> "DatabasePool":
        options = dict(settings or section_config(config, "database"))
        driver = str(options.get("driver", "")).lower()
        if driver in {"postgres", "postgresql", "psql"}:
            try:
                from psycopg_pool import ConnectionPool
            except ImportError as exc:
                raise RuntimeError("Install psycopg[binary,pool] for PostgreSQL") from exc
            pool = ConnectionPool(
                conninfo=str(options.get("connection_string", "")),
                kwargs={k: options[k] for k in ("host", "port", "dbname", "user", "password", "sslmode") if k in options},
                min_size=int(options.get("min_size", 1)),
                max_size=int(options.get("max_size", 10)),
                open=True,
            )
            return cls(pool, "postgresql")
        if driver == "mysql":
            try:
                from mysql.connector.pooling import MySQLConnectionPool
            except ImportError as exc:
                raise RuntimeError("Install mysql-connector-python for MySQL") from exc
            kwargs = {k: options[k] for k in ("host", "port", "database", "user", "password") if k in options}
            pool = MySQLConnectionPool(
                pool_name=str(options.get("pool_name", "common_tools_pool")),
                pool_size=int(options.get("max_size", 5)),
                **kwargs,
            )
            return cls(pool, "mysql")
        raise ValueError("database.driver must be 'postgresql' or 'mysql'")

    def _execute(self, sql: str, params: Sequence[Any] = (), *, returning: bool = False) -> Any:
        connection = self.pool.getconn() if self.driver == "postgresql" else self.pool.get_connection()
        try:
            if self.driver == "postgresql":
                from psycopg.rows import dict_row
                cursor = connection.cursor(row_factory=dict_row)
            else:
                cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(sql, tuple(params))
                result = cursor.fetchall() if cursor.description else {
                    "rowcount": cursor.rowcount,
                    "lastrowid": getattr(cursor, "lastrowid", None),
                }
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
        finally:
            if self.driver == "postgresql":
                self.pool.putconn(connection)
            else:
                connection.close()

    def select(
        self, table: str, *, where: Mapping[str, Any] | None = None,
        columns: Sequence[str] = ("*",), limit: int | None = None,
    ) -> list[dict[str, Any]]:
        selected = "*" if list(columns) == ["*"] else ", ".join(
            _identifier(c, self.driver) for c in columns
        )
        sql = f"SELECT {selected} FROM {_identifier(table, self.driver)}"
        params: list[Any] = []
        if where:
            sql += " WHERE " + _where(where, params, self.driver)
        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be positive")
            sql += " LIMIT %s"
            params.append(limit)
        return self._execute(sql, params)

    def insert(self, table: str, values: Mapping[str, Any]) -> Any:
        if not values:
            raise ValueError("values must not be empty")
        columns = list(values)
        sql = (
            f"INSERT INTO {_identifier(table, self.driver)} "
            f"({', '.join(_identifier(c, self.driver) for c in columns)}) "
            f"VALUES ({', '.join(['%s'] * len(columns))})"
        )
        if self.driver == "postgresql":
            sql += " RETURNING *"
        result = self._execute(sql, list(values.values()), returning=True)
        return result[0] if self.driver == "postgresql" and result else result

    def update(self, table: str, values: Mapping[str, Any], *, where: Mapping[str, Any]) -> Any:
        if not values:
            raise ValueError("values must not be empty")
        params = list(values.values())
        assignments = ", ".join(f"{_identifier(k, self.driver)} = %s" for k in values)
        sql = (
            f"UPDATE {_identifier(table, self.driver)} SET {assignments} "
            f"WHERE {_where(where, params, self.driver)}"
        )
        return self._execute(sql, params)

    def delete(self, table: str, *, where: Mapping[str, Any]) -> Any:
        params: list[Any] = []
        sql = (
            f"DELETE FROM {_identifier(table, self.driver)} "
            f"WHERE {_where(where, params, self.driver)}"
        )
        return self._execute(sql, params)

    def close(self) -> None:
        close = getattr(self.pool, "close", None)
        if close:
            close()


def create_database_pool(
    config: Mapping[str, Any] | str | Path | None = None,
    *,
    settings: Mapping[str, Any] | None = None,
) -> DatabasePool:
    return DatabasePool.create(config, settings=settings)
