"""Bounded read-only tools over worker-owned Kraken query capabilities."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from src.core.authoring_context import EntityAuthoringContext, EventAuthoringContext
from src.core.entity_context_mode import EntityContextMode
from src.core.events import Event
from src.core.mcp_access import MAX_RESULT_BYTES, PAGE_SIZE, McpFailure
from src.services.authoring_context_builder import AuthoringContextBuilder
from src.services.context_read_inputs import relevant_inputs, timing_component_ids
from src.services.db_service import DatabaseService
from src.services.entity_connection_browse_service import (
    EntityConnectionBrowseService,
    StaleConnectionCursor,
)
from src.services.mcp_browse import browse_arguments, browse_batch
from src.services.mcp_calendars import calendar_read
from src.services.mcp_compact import compact_data
from src.services.mcp_contracts import capabilities, check_preconditions
from src.services.mcp_facts import (
    enrich_context,
    object_key,
    saved_object,
    world_overview,
)
from src.services.mcp_images import image_job
from src.services.mcp_public import public_projection
from src.services.mcp_relationships import browse_relationships
from src.services.mcp_sections import McpSections
from src.services.mcp_shared_search import shared_search
from src.services.mcp_temporal import McpTemporalReader
from src.services.mcp_time import time_context
from src.services.mcp_world_reads import McpWorldReads
from src.services.repositories.mcp_read_repository import McpReadRepository

_MAX_CURSORS = 200
_MAX_QUERY_CHARS = 256
_MAX_CONTEXT_INPUT_ROWS = 5000


@contextmanager
def read_guard(
    connection: sqlite3.Connection, expired: Callable[[], bool]
) -> Iterator[None]:
    """Deny writes during this worker slot and interrupt overdue SQL work."""
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_SAVEPOINT,
        sqlite3.SQLITE_RECURSIVE,
    }

    def authorize(
        action: int,
        first: str | None,
        second: str | None,
        database: str | None,
        trigger: str | None,
    ) -> int:
        if action == sqlite3.SQLITE_PRAGMA:
            return (
                sqlite3.SQLITE_OK
                if first == "data_version" and second is None
                else sqlite3.SQLITE_DENY
            )
        if action == sqlite3.SQLITE_FUNCTION and second in {
            "load_extension",
            "writefile",
            "readfile",
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    connection.set_authorizer(authorize)
    connection.set_progress_handler(lambda: int(expired()), 1000)
    try:
        yield
    finally:
        connection.set_progress_handler(None, 0)
        connection.set_authorizer(None)


class McpReadService:
    """Adapt saved facts without exposing arbitrary DB or command operations."""

    def __init__(self) -> None:
        """Own bounded, session-local opaque continuation handles."""
        self._cursors: dict[str, dict[str, Any]] = {}
        self._sections = McpSections(self._continue, self._remember)
        self._world_reads = McpWorldReads(self._continue, self._remember)

    @staticmethod
    def revision(db: DatabaseService) -> str:
        """Hash local revision markers without publishing connection identities."""
        raw = EntityConnectionBrowseService(db).revision()
        return hashlib.sha256(json.dumps(raw).encode()).hexdigest()

    def reset(self) -> None:
        """Release query bindings and continuation handles when sharing ends."""
        self._cursors.clear()

    def execute(
        self,
        db: DatabaseService,
        request: dict[str, Any],
        expired: Callable[[], bool],
    ) -> dict[str, Any]:
        """Execute one bounded query against the active worker connection."""
        if expired():
            raise McpFailure("TIMEOUT")
        self._expired = expired
        args = request["arguments"]
        tool = request["tool"]
        detail = args.get("detail", "full")
        if not isinstance(detail, str) or detail not in {"full", "compact"}:
            raise McpFailure("INVALID_INPUT")
        with read_guard(db.require_connection(), expired):
            revision = self.revision(db)
            check_preconditions(args, request, revision)
            with db.transaction():
                data = self._dispatch(db, tool, args, request, revision)
            if expired():
                raise McpFailure("TIMEOUT")
            if self.revision(db) != revision:
                raise McpFailure("WORLD_CHANGED")
        pending_image = data.pop("image_job", None)
        if tool in {"get_context", "read_context_section"}:
            data["attachment_access"] = {
                "included_by_this_tool": False,
                "reason_code": "CONTEXT_TOOL_EXCLUDES_ATTACHMENTS",
                "session_metadata_scope_enabled": "attachments"
                in request.get("scopes", []),
                "session_attachment_images_enabled": all(
                    key in request.get("scopes", [])
                    for key in ("attachments", "images")
                ),
                "metadata_tool": "list_attachments",
                "image_tool": "get_image_preview",
                "legacy_flag": "omitted_counts.attachment_access_disabled",
                "legacy_flag_is_count": False,
            }
        data = public_projection(data)
        if detail == "compact":
            data = compact_data(data)
        if expired():
            raise McpFailure("TIMEOUT")
        result = {
            "schema_version": 1,
            "status": "OK",
            "world_id": request["world_id"],
            "revision": revision,
            "session_generation": request["generation"],
            "evaluation": args,
            "data": data,
        }
        if detail == "compact":
            result["detail"] = detail
        if len(json.dumps(result, allow_nan=False).encode()) > MAX_RESULT_BYTES:
            raise McpFailure("RESULT_TOO_LARGE")
        with read_guard(db.require_connection(), expired):
            if expired():
                raise McpFailure("TIMEOUT")
            if self.revision(db) != revision:
                raise McpFailure("WORLD_CHANGED")
        if pending_image is not None:
            result["_image_job"] = pending_image
        return result

    def _dispatch(
        self,
        db: DatabaseService,
        tool: str,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
        if tool in {
            "list_calendars",
            "read_calendar_section",
            "browse_relationships",
            "get_time_context",
            "get_capabilities",
        }:
            return self._audit_read(db, request, revision)
        if tool == "search_shared_content":
            return shared_search(db, request, revision, self._continue, self._remember)
        if tool == "semantic_search":
            data = self._search(
                db, {**args, "ranking": "relevance"}, request, revision, paged=False
            )
            data.update(
                truncated=data["partial"],
                effective_search="lexical",
                fallback_reason=(
                    "index_not_ready"
                    if "semantic" in request.get("scopes", [])
                    else "scope_disabled"
                ),
            )
            return data
        if tool == "get_image_preview":
            # Kept outside public data; only the worker task consumes this job.
            return {"image_job": image_job(db, request)}
        if self._sections.supports(tool):
            return self._sections.execute(
                db, request, revision, self._context, self._expired
            )
        if self._world_reads.supports(tool):
            return self._world_reads.execute(db, request, revision, self._expired)
        if tool == "get_active_world":
            return {
                "id": request["world_id"],
                "name": request["world_name"],
                "read_only": True,
            }
        if tool == "search_world":
            return self._search(db, args, request, revision)
        if tool == "list_connections":
            return self._connections(db, args, request, revision)
        if tool == "get_world_overview":
            return world_overview(db, request)
        if tool == "get_objects":
            return self._objects(db, args)
        if tool == "browse_world":
            filters = browse_arguments(args)
            after = self._continue(args, request, revision) or ""
            data, continuation = browse_batch(db, filters, after, self._expired)
            data["next_cursor"] = (
                self._remember(continuation, args, request, revision)
                if continuation is not None
                else None
            )
            return data
        if tool not in {"get_object", "get_context"}:
            raise McpFailure("INVALID_TOOL")
        kind, identifier = object_key(args)
        reader = McpTemporalReader(db, self._expired)
        if tool == "get_object":
            return saved_object(db, kind, identifier, reader)
        return self._context(db, args)

    def _audit_read(
        self, db: DatabaseService, request: dict[str, Any], revision: str
    ) -> dict[str, Any]:
        """Route feature-owned audit readers without expanding the original dispatcher."""
        if request["tool"] == "get_capabilities":
            return capabilities(request)
        if request["tool"] in {"list_calendars", "read_calendar_section"}:
            return calendar_read(db, request, revision, self._continue, self._remember)
        if request["tool"] == "browse_relationships":
            return browse_relationships(
                db, request, revision, self._continue, self._remember
            )
        return time_context(db, request)

    def _context(self, db: DatabaseService, args: dict[str, Any]) -> dict[str, Any]:
        kind, identifier = object_key(args)
        reader = McpTemporalReader(db, self._expired)
        item = (
            db.get_entity(identifier) if kind == "entity" else db.get_event(identifier)
        )
        if item is None:
            raise McpFailure("NOT_FOUND")
        mode, day = self._date(args, require_date=kind == "entity")
        if isinstance(item, Event) and day is None:
            projected = reader.projected(item)
            if projected is None or projected.lore_date is None:
                raise McpFailure("INVALID_DATE")
            day = projected.lore_date
        bounded = not args.get("unbounded", False)
        inputs = None
        if not McpReadRepository(db.require_connection()).context_within_limit(
            _MAX_CONTEXT_INPUT_ROWS
        ):
            effective_day = day if day is not None else getattr(item, "lore_date", None)
            inputs = relevant_inputs(
                db, kind, identifier, self._expired, day=effective_day, bounded=bounded
            )
        builder = AuthoringContextBuilder(
            db,
            inputs=inputs,
            bounded=bounded,
            cancel=self._expired,
            complete_anchors=True,
        )
        context: EntityAuthoringContext | EventAuthoringContext | None
        if kind == "entity":
            context = builder.build_entity_context(
                identifier, mode=EntityContextMode(mode), context_date=day
            )
        else:
            context = builder.build_event_context(identifier, context_date=day)
        if context is None:
            raise McpFailure("INVALID_DATE")
        data = context.to_dict()
        enrich_context(db, data, kind, identifier, reader)
        data.pop("attachments", None)
        data["omitted_counts"] = dict(data.get("omitted_counts", {}))
        data["omitted_counts"]["attachment_access_disabled"] = 1
        return data

    def _objects(self, db: DatabaseService, args: dict[str, Any]) -> dict[str, Any]:
        objects = args.get("objects")
        if (
            not isinstance(objects, list)
            or not 1 <= len(objects) <= PAGE_SIZE
            or any(not isinstance(item, dict) for item in objects)
        ):
            raise McpFailure("INVALID_INPUT")
        keys = [object_key(item) for item in objects]
        results: list[dict[str, Any]] = []
        reader = McpTemporalReader(db, self._expired)
        for kind, identifier in keys:
            try:
                data = saved_object(db, kind, identifier, reader)
                results.append(
                    {"kind": kind, "id": identifier, "status": "OK", "data": data}
                )
            except McpFailure as exc:
                if exc.code != "NOT_FOUND":
                    raise
                results.append(
                    {
                        "kind": kind,
                        "id": identifier,
                        "status": "NOT_FOUND",
                        "data": None,
                    }
                )
        return {"results": results}

    @staticmethod
    def _date(
        args: dict[str, Any], *, require_date: bool = True
    ) -> tuple[str, float | None]:
        mode = args.get("mode", "all_history")
        if mode not in {item.value for item in EntityContextMode}:
            raise McpFailure("INVALID_INPUT")
        day = args.get("lore_day")
        if day is not None and (
            isinstance(day, bool)
            or not isinstance(day, (int, float))
            or not math.isfinite(day)
        ):
            raise McpFailure("INVALID_DATE")
        if require_date and mode != "all_history" and day is None:
            raise McpFailure("INVALID_DATE", "LORE_DAY_REQUIRED")
        return mode, day

    def _continue(
        self,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
    ) -> Any:
        token = args.get("cursor")
        if token is None:
            return None
        if not isinstance(token, str):
            raise McpFailure("STALE_CURSOR", "INVALID_CURSOR")
        saved = self._cursors.get(token)
        if saved is None:
            raise McpFailure("STALE_CURSOR", "INVALID_CURSOR")
        if saved["expires"] < time.monotonic():
            raise McpFailure("STALE_CURSOR", "CURSOR_EXPIRED")
        binding = {key: value for key, value in args.items() if key != "cursor"}
        if any(
            (
                saved["binding"] != binding,
                saved["tool"] != request["tool"],
                saved["world_id"] != request["world_id"],
                saved["revision"] != revision,
                saved["generation"] != request["generation"],
            )
        ):
            raise McpFailure("STALE_CURSOR", "CURSOR_BINDING_MISMATCH")
        return saved["value"]

    def _remember(
        self,
        value: Any,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
    ) -> str:
        if len(self._cursors) >= _MAX_CURSORS:
            self._cursors.pop(next(iter(self._cursors)))
        token = secrets.token_urlsafe(24)
        self._cursors[token] = {
            "binding": {key: val for key, val in args.items() if key != "cursor"},
            "tool": request["tool"],
            "world_id": request["world_id"],
            "revision": revision,
            "generation": request["generation"],
            "expires": time.monotonic() + 600,
            "value": value,
        }
        return token

    def _search(
        self,
        db: DatabaseService,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
        *,
        paged: bool = True,
    ) -> dict[str, Any]:
        from src.services.mcp_search import lexical_page

        after = self._continue(args, request, revision)
        rows, continuation = lexical_page(db.require_connection(), args, after)
        return {
            "rows": rows,
            "partial": continuation is not None,
            "done": not paged or continuation is None,
            "next_cursor": self._remember(continuation, args, request, revision)
            if paged and continuation is not None
            else None,
            "omitted_counts": {},
        }

    def _connections(
        self,
        db: DatabaseService,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
        mode, day = self._date(args)
        cursor = self._continue(args, request, revision)
        try:
            result = EntityConnectionBrowseService(
                db,
                event_loader=lambda ids: self._connection_events(db, ids),
                cancel=self._expired,
            ).step(
                {
                    "query": {
                        "entity_id": args["entity_id"],
                        "mode": mode,
                        "date": day,
                    },
                    "cursor": cursor,
                    "remaining": PAGE_SIZE,
                }
            )
        except StaleConnectionCursor as exc:
            raise McpFailure("STALE_CURSOR") from exc
        except LookupError as exc:
            raise McpFailure("NOT_FOUND") from exc
        continuation = result.pop("cursor")
        result["next_cursor"] = (
            self._remember(continuation, args, request, revision)
            if not result["done"]
            else None
        )
        result["partial"] = not result["done"]
        result["omitted_counts"] = {
            key: continuation[key] for key in ("excluded", "unreadable")
        }
        return result

    def _connection_events(self, db: DatabaseService, seeds: set[str]) -> list[Event]:
        if not seeds:
            return []
        ids = timing_component_ids(db, seeds, self._expired)
        return [
            event
            for identifier in sorted(ids)
            if (event := db.get_event(identifier)) is not None
        ]
