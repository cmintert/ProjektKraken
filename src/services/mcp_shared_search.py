"""Lexical discovery of explicitly shared document, map and caption content."""

from typing import Any

from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService
from src.services.longform_builder import validate_doc_id
from src.services.mcp_contracts import require_scope
from src.services.mcp_search import MAX_QUERY_CHARS, excerpt, normalize
from src.services.mcp_sections import Continuation, page_limit


def shared_search(
    db: DatabaseService,
    request: dict[str, Any],
    revision: str,
    resume: Continuation,
    remember: Continuation,
) -> dict[str, Any]:
    """Search only selected scopes and return stable identities, never asset paths."""
    args = request["arguments"]
    query = args.get("query")
    scope_of = {"longform": "longform", "map": "maps", "attachment": "attachments"}
    kinds = args.get("kinds")
    if kinds is None:
        kinds = [
            kind
            for kind, scope in scope_of.items()
            if scope in request.get("scopes", [])
        ]
        if not kinds:
            raise McpFailure("SCOPE_DISABLED")
    if (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > MAX_QUERY_CHARS
        or not isinstance(kinds, list)
        or not kinds
        or any(kind not in {"longform", "map", "attachment"} for kind in kinds)
    ):
        raise McpFailure("INVALID_INPUT")
    limit = page_limit(args)
    for kind in kinds:
        require_scope(request, scope_of[kind])
    doc_id = args.get("doc_id", "default")
    try:
        validate_doc_id(doc_id)
    except (ValueError, TypeError) as exc:
        raise McpFailure("INVALID_INPUT") from exc
    connection = db.require_connection()
    connection.create_function(
        "mcp_normalize",
        1,
        lambda value: normalize(value) if isinstance(value, str) else "",
        deterministic=True,
    )
    parts, values = [], []
    if "map" in kinds:
        parts.append(
            "SELECT 'map' kind,id,name,description text,'map:'||id ordering,"
            "NULL owner_id,NULL object_kind FROM maps"
        )
    if "attachment" in kinds:
        parts.append(
            "SELECT 'attachment' kind,id,'Attachment' name,caption text,"
            "'attachment:'||id ordering,owner_id,owner_type object_kind "
            "FROM image_attachments"
        )
    if "longform" in kinds:
        for table, kind in (("entities", "entity"), ("events", "event")):
            parts.append(
                f"SELECT 'longform' kind,id,name,description text,"
                f"'longform:{kind}:'||id ordering,id owner_id,'{kind}' object_kind "
                f"FROM {table} WHERE json_type(attributes,?)='object' "
                "AND coalesce(json_extract(attributes,?),0)!=1"
            )
            values.extend(
                [f'$._longform."{doc_id}"', f'$._longform."{doc_id}".excluded']
            )
    after = resume(args, request, revision) or ""
    try:
        rows = connection.execute(
            "SELECT * FROM ("
            + " UNION ALL ".join(parts)
            + ") WHERE ordering>? AND (instr(mcp_normalize(name),?)>0 "
            "OR instr(mcp_normalize(text),?)>0) ORDER BY ordering LIMIT ?",
            [*values, after, normalize(query), normalize(query), limit + 1],
        ).fetchall()
    finally:
        connection.create_function("mcp_normalize", 1, None)
    more, rows = len(rows) > limit, rows[:limit]
    return {
        "rows": [
            {
                "kind": row["kind"],
                "id": row["id"],
                "name": row["name"],
                "owner_id": row["owner_id"],
                "object_kind": row["object_kind"],
                "doc_id": doc_id if row["kind"] == "longform" else None,
                **excerpt(row["text"] or "", query),
            }
            for row in rows
        ],
        "done": not more,
        "partial": more,
        "next_cursor": remember(rows[-1]["ordering"], args, request, revision)
        if more
        else None,
    }
