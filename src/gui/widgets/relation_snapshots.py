"""Shared identity-based merge of inspector relation snapshots."""

from typing import Any


def distinct_relation_directions(
    outgoing: list[dict[str, Any]] | None,
    incoming: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retain direction and distinct IDs while displaying each UUID once."""
    seen: set[str] = set()
    result: list[list[dict[str, Any]]] = [[], []]
    for index, rows in enumerate((outgoing or [], incoming or [])):
        for row in rows:
            relation_id = row.get("id")
            if relation_id and relation_id in seen:
                continue
            if relation_id:
                seen.add(relation_id)
            result[index].append(row)
    return result[0], result[1]
