"""Explicitly scoped read-only Longform, map and attachment projections."""

from collections.abc import Callable
from typing import Any

from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService
from src.services.longform_builder import build_longform_sequence, validate_doc_id
from src.services.mcp_contracts import require_scope
from src.services.mcp_facts import object_key
from src.services.mcp_map_facts import feature_page, read_map_facts
from src.services.mcp_public import public_projection
from src.services.mcp_sections import Continuation, page_limit, section_page


class McpWorldReads:
    """Read saved records without changing outline metadata or loading image bodies."""

    def __init__(self, resume: Continuation, remember: Continuation) -> None:
        """Borrow bounded session cursor operations from the read adapter."""
        self._resume, self._remember = resume, remember

    @staticmethod
    def supports(tool: str) -> bool:
        """Only these fixed tools can access broader world content."""
        return tool in {"read_longform", "browse_maps", "read_map", "list_attachments"}

    def execute(
        self,
        db: DatabaseService,
        request: dict[str, Any],
        revision: str,
        expired: Callable[[], bool],
    ) -> dict[str, Any]:
        """Require the applicable permission before reading any scoped records."""
        tool, args = request["tool"], request["arguments"]
        scope = {"read_longform": "longform", "list_attachments": "attachments"}.get(
            tool, "maps"
        )
        require_scope(request, scope)
        self._expired = expired
        limit = page_limit(args)
        offset = self._resume(args, request, revision) or 0
        if tool == "read_map" and args.get("section") in {
            "markers",
            "paths",
            "regions",
        }:
            data, continuation = feature_page(db, args, expired, offset, limit)
            data = public_projection(data)
        else:
            rows = self._read(db, tool, args)
            data, continuation = section_page(public_projection(rows), offset, limit)
        data.update(
            done=continuation is None,
            partial=continuation is not None,
            next_cursor=self._remember(continuation, args, request, revision)
            if continuation is not None
            else None,
            provenance={"kind": "saved", "section": tool},
        )
        return data

    def _read(self, db: DatabaseService, tool: str, args: dict[str, Any]) -> Any:
        if tool == "read_longform":
            return self._longform(db, args)
        if tool == "list_attachments":
            kind, identifier = object_key(args)
            owner = (
                db.get_entity(identifier)
                if kind == "entity"
                else db.get_event(identifier)
            )
            if owner is None:
                raise McpFailure("NOT_FOUND")
            return [
                {
                    "id": item.id,
                    "owner_kind": kind,
                    "owner_id": identifier,
                    "caption": item.caption,
                    "order_index": item.order_index,
                    "dimensions": item.resolution,
                    "image_available": True,
                }
                for item in db.get_attachment_repo().list_by_owner(kind, identifier)
            ]
        if tool == "browse_maps":
            return [
                {"id": row["id"], "name": row["name"]}
                for row in db.require_connection().execute(
                    "SELECT id, name FROM maps ORDER BY name COLLATE NOCASE, id"
                )
            ]
        return self._map(db, args)

    @staticmethod
    def _longform(db: DatabaseService, args: dict[str, Any]) -> list[dict[str, Any]]:
        doc_id = args.get("doc_id", "default")
        try:
            validate_doc_id(doc_id)
            rows = build_longform_sequence(
                db.require_connection(), doc_id, include_content=False
            )
        except (ValueError, TypeError, RecursionError) as exc:
            raise McpFailure("INVALID_DOCUMENT") from exc
        return [
            {
                "id": row["id"],
                "kind": "entity" if row["table"] == "entities" else "event",
                "name": row["name"],
                "heading_level": row["heading_level"],
                "parent_id": row["meta"].get("parent_id"),
                "title_override": row["meta"].get("title_override"),
                "position": row["meta"].get("position"),
                "doc_id": doc_id,
            }
            for row in rows
        ]

    def _map(self, db: DatabaseService, args: dict[str, Any]) -> Any:
        return read_map_facts(db, args, self._expired)
