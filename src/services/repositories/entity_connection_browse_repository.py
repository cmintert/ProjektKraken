"""Targeted, schema-free reads for the human direct-connection browser."""

import json
from typing import Any

from src.services.repositories.base_repository import BaseRepository


def _casefold_compare(first: str, second: str) -> int:
    left, right = first.casefold(), second.casefold()
    return (left > right) - (left < right)


class EntityConnectionBrowseRepository(BaseRepository):
    """Read canonical edges in display order without restricting predicates."""

    def candidates(
        self, entity_id: str, after: list[str] | None, limit: int
    ) -> list[dict[str, Any]]:
        """Return a bounded candidate batch, not an eligible-result page."""
        connection = self._require_connection()
        connection.create_collation("context_casefold", _casefold_compare)
        key = (
            "sort_source COLLATE context_casefold, "
            "rel_type COLLATE context_casefold, "
            "sort_target COLLATE context_casefold, id"
        )
        predicate = f"WHERE ({key}) > (?, ?, ?, ?)" if after else ""
        sql = f"""
            WITH touching AS (
                SELECT r.*,
                    COALESCE(se.name, sv.name, r.source_id) AS sort_source,
                    COALESCE(te.name, tv.name, r.target_id) AS sort_target,
                    CASE WHEN se.id IS NOT NULL THEN 'entity'
                         WHEN sv.id IS NOT NULL THEN 'event' END AS source_kind,
                    CASE WHEN te.id IS NOT NULL THEN 'entity'
                         WHEN tv.id IS NOT NULL THEN 'event' END AS target_kind
                FROM relations r
                LEFT JOIN entities se ON se.id = r.source_id
                LEFT JOIN events sv ON sv.id = r.source_id
                LEFT JOIN entities te ON te.id = r.target_id
                LEFT JOIN events tv ON tv.id = r.target_id
                WHERE r.source_id = ? OR r.target_id = ?
            )
            SELECT * FROM touching {predicate}
            ORDER BY {key} LIMIT ?
        """
        parameters: list[Any] = [entity_id, entity_id]
        if after:
            parameters.extend(after)
        parameters.append(limit)
        rows = []
        for row in connection.execute(sql, parameters):
            item = dict(row)
            item["attributes"] = json.loads(item["attributes"] or "{}")
            if not isinstance(item["attributes"], dict):
                raise ValueError("Connection metadata must be a JSON object")
            rows.append(item)
        return rows
