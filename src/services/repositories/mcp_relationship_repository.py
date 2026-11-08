"""Bounded, revision-scoped inventory of canonical saved relation rows."""

import sqlite3
from typing import Any

_EDGES = """
    SELECT r.id,r.source_id,r.target_id,r.rel_type,
        CASE WHEN se.id IS NOT NULL AND sv.id IS NOT NULL THEN 'ambiguous'
             WHEN se.id IS NOT NULL THEN 'entity'
             WHEN sv.id IS NOT NULL THEN 'event' ELSE 'unresolved' END source_kind,
        CASE WHEN te.id IS NOT NULL AND tv.id IS NOT NULL THEN 'ambiguous'
             WHEN te.id IS NOT NULL THEN 'entity'
             WHEN tv.id IS NOT NULL THEN 'event' ELSE 'unresolved' END target_kind
    FROM relations r
    LEFT JOIN entities se ON se.id=r.source_id
    LEFT JOIN events sv ON sv.id=r.source_id
    LEFT JOIN entities te ON te.id=r.target_id
    LEFT JOIN events tv ON tv.id=r.target_id
"""


class McpRelationshipRepository:
    """Count every saved relation ID once, without loading prose or attributes."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Borrow only the active worker connection."""
        self._connection = connection

    def counts(self) -> dict[str, Any]:
        """Partition all rows, including unresolved or ambiguous endpoint identities."""
        buckets = {
            f"{source}_to_{target}": 0
            for source in ("entity", "event")
            for target in ("entity", "event")
        }
        buckets["unresolved_or_ambiguous"] = 0
        for row in self._connection.execute(
            "SELECT source_kind,target_kind,count(*) total FROM ("
            + _EDGES
            + ") GROUP BY source_kind,target_kind"
        ):
            key = f"{row['source_kind']}_to_{row['target_kind']}"
            buckets[key if key in buckets else "unresolved_or_ambiguous"] += row[
                "total"
            ]
        return {
            "total_saved": sum(buckets.values()),
            "by_endpoint_kinds": buckets,
            "basis": "saved_relation_rows",
            "temporal_filter": "none",
        }

    def page(self, after: str, limit: int, args: dict[str, Any]) -> list[Any]:
        """Keyset-page fixed relation fields; do not materialize attribute bodies."""
        clauses, values = ["id > ?"], [after]
        for key in ("source_kind", "target_kind", "predicate"):
            value = args.get(key)
            if value is not None:
                column = "rel_type" if key == "predicate" else key
                clauses.append(f"{column}=?")
                values.append(value)
        return list(
            self._connection.execute(
                "SELECT * FROM ("
                + _EDGES
                + ") WHERE "
                + " AND ".join(clauses)
                + " ORDER BY id LIMIT ?",
                [*values, limit + 1],
            )
        )
