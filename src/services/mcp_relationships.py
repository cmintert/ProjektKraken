"""Global saved-edge inventory, distinct from date-qualified context."""

from typing import Any

from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_sections import Continuation, page_limit
from src.services.repositories.mcp_relationship_repository import (
    McpRelationshipRepository,
)


def browse_relationships(
    db: DatabaseService,
    request: dict[str, Any],
    revision: str,
    resume: Continuation,
    remember: Continuation,
) -> dict[str, Any]:
    """Enumerate directed relation IDs, including Event-only and unresolved edges."""
    args = request["arguments"]
    limit = page_limit(args)
    for key in ("source_kind", "target_kind"):
        if args.get(key) not in {None, "entity", "event", "unresolved", "ambiguous"}:
            raise McpFailure("INVALID_INPUT")
    if args.get("predicate") is not None and not isinstance(args["predicate"], str):
        raise McpFailure("INVALID_INPUT")
    after = resume(args, request, revision) or ""
    saved = McpRelationshipRepository(db.require_connection()).page(after, limit, args)
    more, saved = len(saved) > limit, saved[:limit]
    rows = [
        {
            "id": row["id"],
            "kind": "relation",
            "predicate": row["rel_type"],
            "source": {"id": row["source_id"], "kind": row["source_kind"]},
            "target": {"id": row["target_id"], "kind": row["target_kind"]},
        }
        for row in saved
    ]
    return {
        "rows": rows,
        "done": not more,
        "partial": more,
        "next_cursor": remember(saved[-1]["id"], args, request, revision)
        if more
        else None,
        "provenance": {"kind": "saved_relation_rows", "temporal_filter": "none"},
        "attributes_included": False,
        "excluded_sections": ["attributes"],
        "omitted_counts": {},
    }
