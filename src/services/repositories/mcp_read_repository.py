"""Narrow bounded lexical reads for the optional world-sharing adapter."""

import sqlite3
from typing import Any


class McpReadRepository:
    """Own fixed-table SQL without accepting identifiers or SQL from clients."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Borrow the existing worker-owned connection for one read operation."""
        self._connection = connection

    def counts(self) -> dict[str, Any]:
        """Aggregate saved objects without materializing their authored contents."""
        result = {}
        for kind, table in (("entity", "entities"), ("event", "events")):
            rows = self._connection.execute(
                f"SELECT type, count(*) AS total FROM {table} GROUP BY type ORDER BY type"
            ).fetchall()
            result[kind] = {
                "total": sum(row["total"] for row in rows),
                "by_type": [
                    {"type": row["type"], "count": row["total"]} for row in rows
                ],
            }
        return result

    def candidates(
        self, kinds: list[str], types: list[str], after: str, limit: int
    ) -> list[Any]:
        """Read a fixed-size kind/ID batch, without unsafe temporal prefiltering."""
        tables = {"entity": "entities", "event": "events"}
        parts, parameters = [], []
        for kind in sorted(set(kinds)):
            clause = ""
            if types:
                clause = " WHERE type IN (" + ",".join("?" for _ in types) + ")"
            parts.append(
                f"SELECT '{kind}' AS kind, id, '{kind}:' || id AS ordering "
                f"FROM {tables[kind]}{clause}"
            )
            parameters.extend(types)
        return list(
            self._connection.execute(
                "SELECT * FROM ("
                + " UNION ALL ".join(parts)
                + ") WHERE ordering > ? ORDER BY ordering LIMIT ?",
                [*parameters, after, limit + 1],
            ).fetchall()
        )

    def context_within_limit(self, maximum: int) -> bool:
        """Reject unbounded context construction before materializing world rows."""
        for table in ("entities", "events", "relations"):
            count = self._connection.execute(
                f"SELECT count(*) FROM (SELECT id FROM {table} LIMIT ?)",
                (maximum + 1,),
            ).fetchone()[0]
            if count > maximum:
                return False
        return True

    def search(
        self,
        query: str,
        kinds: list[str],
        after: str,
        limit: int,
    ) -> list[Any]:
        """Return a page plus one continuation sentinel using literal text search."""
        pattern = (
            "%"
            + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        tables = {"entity": "entities", "event": "events"}
        parts, parameters = [], []
        for kind in sorted(set(kinds)):
            table = tables[kind]
            parts.append(
                f"SELECT '{kind}' AS kind, id, name, substr(description,1,400) AS snippet,"
                f" '{kind}:' || id AS ordering FROM {table} "
                "WHERE (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')"
            )
            parameters.extend([pattern, pattern])
        return list(
            self._connection.execute(
                "SELECT * FROM ("
                + " UNION ALL ".join(parts)
                + ") WHERE ordering > ? ORDER BY ordering LIMIT ?",
                [*parameters, after, limit + 1],
            ).fetchall()
        )
