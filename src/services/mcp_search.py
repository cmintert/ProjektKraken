"""Deterministic Unicode lexical matching with excerpts at original offsets."""

import sqlite3
import unicodedata
from typing import Any

from src.core.mcp_access import McpFailure
from src.services.mcp_browse import _strings
from src.services.mcp_sections import page_limit

MAX_QUERY_CHARS = 256


def normalize(value: str) -> str:
    """Use compatibility decomposition and Unicode case folding, without translation."""
    return unicodedata.normalize("NFKD", value).casefold()


def excerpt(text: str, query: str) -> dict[str, Any]:
    """Locate a normalized match while returning only untouched authored characters."""
    expanded, offsets = [], []
    for index, char in enumerate(text):
        piece = normalize(char)
        expanded.append(piece)
        offsets.extend([index] * len(piece))
    match = "".join(expanded).find(normalize(query))
    offset = max(0, offsets[match] - 120) if match >= 0 else 0
    return {
        "snippet": text[offset : offset + 400],
        "snippet_offset": offset,
        "snippet_until": min(len(text), offset + 400),
    }


def lexical_page(
    connection: sqlite3.Connection, args: dict[str, Any], after: Any
) -> tuple[list[dict[str, Any]], Any]:
    """Filter in fixed-table SQL and page a deterministic relevance or identity order."""
    query = args.get("query")
    kinds = _strings(args.get("kinds"), ["entity", "event"])
    types = _strings(args.get("types"), [])
    tags = _strings(args.get("tags"), [])
    limit = page_limit(args)
    ranking = args.get("ranking", "stable")
    if (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > MAX_QUERY_CHARS
        or not kinds
        or any(kind not in {"entity", "event"} for kind in kinds)
        or ranking not in {"stable", "relevance"}
    ):
        raise McpFailure("INVALID_INPUT")
    connection.create_function(
        "mcp_normalize",
        1,
        lambda value: normalize(value) if isinstance(value, str) else "",
        deterministic=True,
    )
    parts, params = [], []
    needle = normalize(query)
    for kind in sorted(set(kinds)):
        table = "entities" if kind == "entity" else "events"
        clauses = [
            "(instr(mcp_normalize(name), ?) > 0 OR "
            "instr(mcp_normalize(description), ?) > 0)"
        ]
        values: list[Any] = [needle, needle]
        if types:
            clauses.append("type IN (" + ",".join("?" for _ in types) + ")")
            values.extend(types)
        for tag in tags:
            clauses.append(
                f"(EXISTS(SELECT 1 FROM {kind}_tags j JOIN tags t ON t.id=j.tag_id "
                f"WHERE j.{kind}_id={table}.id AND mcp_normalize(t.name)=?) OR "
                "EXISTS(SELECT 1 FROM json_each(json_extract(attributes,'$._tags')) "
                "WHERE mcp_normalize(value)=?))"
            )
            values.extend([normalize(tag.strip()), normalize(tag.strip())])
        parts.append(
            f"SELECT '{kind}' kind, id, name, description FROM {table} WHERE "
            + " AND ".join(clauses)
        )
        params.extend(values)
    rank = (
        "CASE WHEN mcp_normalize(name)=? THEN 0 "
        "WHEN instr(mcp_normalize(name),?)=1 THEN 1 "
        "WHEN instr(mcp_normalize(name),?)>0 THEN 2 ELSE 3 END"
        if ranking == "relevance"
        else "0"
    )
    prefix = [needle] * 3 if ranking == "relevance" else []
    name = "mcp_normalize(name)" if ranking == "relevance" else "''"
    sql = (
        f"SELECT *, {rank} rank, {name} normalized_name FROM ("
        + " UNION ALL ".join(parts)
        + ")"
    )
    sql = "SELECT * FROM (" + sql + ") WHERE (rank,normalized_name,kind,id)>(?,?,?,?) "
    cursor = after or [-1, "", "", ""]
    try:
        rows = connection.execute(
            sql + "ORDER BY rank,normalized_name,kind,id LIMIT ?",
            [*prefix, *params, *cursor, limit + 1],
        ).fetchall()
    finally:
        connection.create_function("mcp_normalize", 1, None)
    more, rows = len(rows) > limit, rows[:limit]
    results = [
        {
            "kind": row["kind"],
            "id": row["id"],
            "name": row["name"],
            **excerpt(row["description"] or "", query),
        }
        for row in rows
    ]
    continuation = (
        [rows[-1][key] for key in ("rank", "normalized_name", "kind", "id")]
        if more
        else None
    )
    return results, continuation
