"""Recoverable bounded sections of public saved facts."""

import json
from collections.abc import Callable
from typing import Any

from src.core.mcp_access import PAGE_SIZE, McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_facts import object_key, saved_object
from src.services.mcp_public import public_projection
from src.services.mcp_temporal import McpTemporalReader
from src.services.repositories.mcp_read_repository import McpReadRepository

Continuation = Callable[..., Any]
SECTION_BYTES = 40000


def page_limit(args: dict[str, Any]) -> int:
    """Validate page limits at the service boundary, including boolean rejection."""
    limit = args.get("limit", PAGE_SIZE)
    if type(limit) is not int or not 1 <= limit <= PAGE_SIZE:
        raise McpFailure("INVALID_INPUT")
    return limit


def section_page(
    value: Any, offset: int, limit: int
) -> tuple[dict[str, Any], int | None]:
    """Budget complete records or exact Unicode text; never split structured values."""
    if isinstance(value, str):
        end = min(len(value), offset + 8000)
        while len(json.dumps(value[offset:end]).encode()) > SECTION_BYTES:
            end = offset + (end - offset) // 2
        return {
            "text": value[offset:end],
            "offset": offset,
            "until": end,
            "total_length": len(value),
        }, end if end < len(value) else None
    rows = value if isinstance(value, list) else [value]
    selected: list[Any] = []
    end = offset
    for row in rows[offset : offset + limit]:
        if len(json.dumps([*selected, row], allow_nan=False).encode()) > SECTION_BYTES:
            if not selected:
                raise McpFailure("RESULT_TOO_LARGE")
            break
        selected.append(row)
        end += 1
    return {"rows": selected, "offset": offset, "total_length": len(rows)}, (
        end if end < len(rows) else None
    )


class McpSections:
    """Reuse the adapter's session-bound continuation store for section reads."""

    def __init__(self, resume: Continuation, remember: Continuation) -> None:
        """Borrow bounded session cursor operations from the read adapter."""
        self._resume, self._remember = resume, remember

    @staticmethod
    def supports(tool: str) -> bool:
        """Identify only fixed factual section operations."""
        return tool in {
            "get_object_summary",
            "read_object_section",
            "read_context_section",
            "browse_facets",
        }

    def execute(
        self,
        db: DatabaseService,
        request: dict[str, Any],
        revision: str,
        context: Callable[..., dict[str, Any]],
        expired: Callable[[], bool],
    ) -> dict[str, Any]:
        """Read a bounded factual section after the enclosing revision checks."""
        args, tool = request["arguments"], request["tool"]
        limit = page_limit(args)
        metadata: dict[str, Any] = {}
        if tool == "browse_facets":
            value = self._facets(db, args)
            provenance = {"kind": "saved_facets"}
        else:
            kind, identifier = object_key(args)
            data = (
                public_projection(context(db, {**args, "unbounded": True}))
                if tool == "read_context_section"
                else public_projection(
                    saved_object(db, kind, identifier, McpTemporalReader(db, expired))
                )
            )
            if tool == "get_object_summary":
                return self._summary(data)
            section = args.get("section")
            allowed = (
                set(data)
                if tool == "read_context_section"
                else {"description", "attributes", "tags"}
            )
            if not isinstance(section, str) or section not in allowed:
                raise McpFailure("INVALID_INPUT")
            value = data[section]
            if section == "effective_description" and isinstance(value, dict):
                metadata = {key: item for key, item in value.items() if key != "value"}
                value = value["value"]
            metadata["omitted_counts"] = data.get("omitted_counts", {})
            if isinstance(value, dict) and section == "attributes":
                value = [{"name": key, "value": item} for key, item in value.items()]
            provenance = data["provenance"]
        offset = self._resume(args, request, revision) or 0
        data, continuation = section_page(value, offset, limit)
        data.update(metadata)
        data.update(
            provenance=provenance,
            done=continuation is None,
            partial=continuation is not None,
            next_cursor=self._remember(continuation, args, request, revision)
            if continuation is not None
            else None,
        )
        return data

    @staticmethod
    def _summary(data: dict[str, Any]) -> dict[str, Any]:
        result = {
            key: data[key]
            for key in ("id", "kind", "name", "type", "provenance", "temporal")
            if key in data
        }
        result["sections"] = {
            key: {
                "length": len(data[key]),
                "encoded_bytes": len(json.dumps(data[key]).encode()),
            }
            for key in ("description", "attributes", "tags")
        }
        result["omitted_counts"] = data.get("omitted_counts", {})
        return result

    @staticmethod
    def _facets(db: DatabaseService, args: dict[str, Any]) -> list[dict[str, str]]:
        category = args.get("category")
        kinds = args.get("kinds") or ["entity", "event"]
        if category not in {"types", "tags"} or any(
            kind not in {"entity", "event"} for kind in kinds
        ):
            raise McpFailure("INVALID_INPUT")
        names: set[str] = set()
        if category == "tags":
            return [
                {"name": name}
                for name in McpReadRepository(db.require_connection()).tag_facet_names(
                    kinds
                )
            ]
        for kind in set(kinds):
            table = "entities" if kind == "entity" else "events"
            if category == "types":
                names.update(
                    row[0]
                    for row in db.require_connection().execute(
                        f"SELECT DISTINCT type FROM {table}"
                    )
                )
        return [
            {"name": name} for name in sorted(names, key=lambda n: (n.casefold(), n))
        ]
