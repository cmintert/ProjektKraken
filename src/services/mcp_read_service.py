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
from src.core.mcp_access import MAX_RESULT_BYTES, PAGE_SIZE, McpFailure
from src.services.authoring_context_builder import AuthoringContextBuilder
from src.services.db_service import DatabaseService
from src.services.entity_connection_browse_service import (
    EntityConnectionBrowseService,
    StaleConnectionCursor,
)
from src.services.mcp_browse import browse_arguments, browse_batch
from src.services.mcp_compact import compact_data
from src.services.mcp_facts import (
    enrich_context,
    object_key,
    saved_object,
    world_overview,
)
from src.services.mcp_temporal import McpTemporalReader
from src.services.repositories.mcp_read_repository import McpReadRepository

_HIDDEN_KEYS = frozenset(
    {
        "attachments",
        "path",
        "file_path",
        "assets_dir",
        "image_path",
        "api_key",
        "password",
        "token",
        "secret",
        "credentials",
    }
)
_MAX_CURSORS = 200
_MAX_QUERY_CHARS = 256
_MAX_CONTEXT_INPUT_ROWS = 5000


def _restricted_name(name: str) -> bool:
    normalized = name.casefold().replace(" ", "_").replace("-", "_")
    return (
        normalized.startswith("_")
        or normalized in _HIDDEN_KEYS
        or any(
            marker in normalized
            for marker in (
                "path",
                "credential",
                "api_key",
                "password",
                "secret",
                "token",
            )
        )
    )


def _restricted_attribute(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "value" in value
        and _restricted_name(str(value.get("name", "")))
    )


def public_projection(value: Any) -> Any:
    """Copy bounded factual values, removing internal and path-bearing metadata."""
    if isinstance(value, dict):
        if _restricted_attribute(value):
            return None
        return {
            str(key): public_projection(item)
            for key, item in value.items()
            if not _restricted_name(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [
            public_projection(item) for item in value if not _restricted_attribute(item)
        ]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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

    @staticmethod
    def revision(db: DatabaseService) -> str:
        """Hash local revision markers without publishing connection identities."""
        raw = EntityConnectionBrowseService(db).revision()
        return hashlib.sha256(json.dumps(raw).encode()).hexdigest()

    def execute(
        self,
        db: DatabaseService,
        request: dict[str, Any],
        expired: Callable[[], bool],
    ) -> dict[str, Any]:
        """Execute one bounded query against the active worker connection."""
        if expired():
            raise McpFailure("TIMEOUT")
        args = request["arguments"]
        tool = request["tool"]
        detail = args.get("detail", "full")
        if not isinstance(detail, str) or detail not in {"full", "compact"}:
            raise McpFailure("INVALID_INPUT")
        with read_guard(db.require_connection(), expired):
            revision = self.revision(db)
            with db.transaction():
                data = self._dispatch(db, tool, args, request, revision)
            if expired():
                raise McpFailure("TIMEOUT")
            if self.revision(db) != revision:
                raise McpFailure("WORLD_CHANGED")
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
        return result

    def _dispatch(
        self,
        db: DatabaseService,
        tool: str,
        args: dict[str, Any],
        request: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
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
            data, continuation = browse_batch(db, filters, after)
            data["next_cursor"] = (
                self._remember(continuation, args, request, revision)
                if continuation is not None
                else None
            )
            return data
        if tool not in {"get_object", "get_context"}:
            raise McpFailure("INVALID_TOOL")
        kind, identifier = object_key(args)
        reader = McpTemporalReader(db)
        if tool == "get_object":
            return saved_object(db, kind, identifier, reader)
        item = (
            db.get_entity(identifier) if kind == "entity" else db.get_event(identifier)
        )
        if item is None:
            raise McpFailure("NOT_FOUND")
        mode, day = self._date(args, require_date=kind == "entity")
        builder = AuthoringContextBuilder(db)
        if not McpReadRepository(db.require_connection()).context_within_limit(
            _MAX_CONTEXT_INPUT_ROWS
        ):
            raise McpFailure("CONTEXT_LIMIT")
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

    @staticmethod
    def _objects(db: DatabaseService, args: dict[str, Any]) -> dict[str, Any]:
        objects = args.get("objects")
        if (
            not isinstance(objects, list)
            or not 1 <= len(objects) <= PAGE_SIZE
            or any(not isinstance(item, dict) for item in objects)
        ):
            raise McpFailure("INVALID_INPUT")
        keys = [object_key(item) for item in objects]
        results: list[dict[str, Any]] = []
        reader = McpTemporalReader(db)
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
            raise McpFailure("INVALID_DATE")
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
            raise McpFailure("STALE_CURSOR")
        saved = self._cursors.get(token)
        binding = {key: value for key, value in args.items() if key != "cursor"}
        if saved is None or any(
            (
                saved["binding"] != binding,
                saved["tool"] != request["tool"],
                saved["world_id"] != request["world_id"],
                saved["revision"] != revision,
                saved["generation"] != request["generation"],
                saved["expires"] < time.monotonic(),
            )
        ):
            raise McpFailure("STALE_CURSOR")
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
    ) -> dict[str, Any]:
        query = args.get("query")
        kinds = args.get("kinds") or ["entity", "event"]
        limit = args.get("limit", PAGE_SIZE)
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > _MAX_QUERY_CHARS
            or not isinstance(limit, int)
            or not 1 <= limit <= PAGE_SIZE
            or not isinstance(kinds, list)
            or not kinds
            or any(k not in {"entity", "event"} for k in kinds)
        ):
            raise McpFailure("INVALID_INPUT")
        after = self._continue(args, request, revision) or ""
        rows = McpReadRepository(db.require_connection()).search(
            query, kinds, after, limit
        )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "rows": [
                {key: row[key] for key in ("kind", "id", "name", "snippet")}
                for row in rows
            ],
            "partial": more,
            "done": not more,
            "next_cursor": self._remember(rows[-1]["ordering"], args, request, revision)
            if more
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
            result = EntityConnectionBrowseService(db).step(
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
