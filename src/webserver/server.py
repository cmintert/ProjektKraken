"""Web Server Module for ProjektKraken.

Provides FastAPI-based REST API for serving longform documents and health checks. This
server is designed to run embedded within the main application via QThread.
"""

import json
import logging
import os
import secrets
import sys
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import Receive, Scope, Send

from src.services.db_service import DatabaseService
from src.services.longform_builder import (
    DOC_ID_DEFAULT,
    DOC_ID_MAX_LENGTH,
    build_longform_sequence,
)
from src.webserver.config import ServerConfig
from src.webserver.markdown_renderer import render_longform_markdown

logger = logging.getLogger(__name__)

logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "img-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

_DOC_ID_QUERY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
DocId = Annotated[
    str,
    Query(
        min_length=1,
        max_length=DOC_ID_MAX_LENGTH,
        pattern=_DOC_ID_QUERY_PATTERN,
    ),
]


def _host_from_header(host_header: str) -> str:
    """Return the normalized hostname from an HTTP Host header."""
    normalized = host_header.strip().lower()
    if not normalized.startswith("["):
        return normalized.split(":", maxsplit=1)[0]

    address, separator, port = normalized[1:].partition("]")
    if not separator or (port and (not port.startswith(":") or not port[1:].isdigit())):
        return ""
    return address


class _KrakenTrustedHostMiddleware(TrustedHostMiddleware):
    """Trusted Host middleware with correct bracketed IPv6 Host parsing."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.allow_any or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        host = _host_from_header(Headers(scope=scope).get("host", ""))
        is_valid_host = any(
            host == pattern
            or (pattern.startswith("*") and host.endswith(pattern[1:]))
            for pattern in self.allowed_hosts
        )
        if is_valid_host:
            await self.app(scope, receive, send)
            return

        response = PlainTextResponse("Invalid host header", status_code=400)
        await response(scope, receive, send)


class _AccessCodeRateLimiter:
    """Bound failed LAN authentication attempts in a rolling time window."""

    _WINDOW_SECONDS = 60.0
    _CLIENT_LIMIT = 5
    _GLOBAL_LIMIT = 30

    def __init__(self) -> None:
        self._client_failures: dict[str, deque[float]] = defaultdict(deque)
        self._global_failures: deque[float] = deque()
        self._lock = threading.Lock()

    def record_failure(self, client: str) -> int | None:
        """Record a failed attempt and return a retry delay when limited."""
        now = time.monotonic()
        with self._lock:
            client_failures = self._client_failures[client]
            self._prune(client_failures, now)
            self._prune(self._global_failures, now)
            client_failures.append(now)
            self._global_failures.append(now)
            return self._retry_after(client_failures, now)

    def retry_after(self, client: str) -> int | None:
        """Return the active retry delay for a client, if any."""
        now = time.monotonic()
        with self._lock:
            client_failures = self._client_failures[client]
            self._prune(client_failures, now)
            self._prune(self._global_failures, now)
            return self._retry_after(client_failures, now)

    def _retry_after(self, client_failures: deque[float], now: float) -> int | None:
        limited_at: float | None = None
        if len(client_failures) >= self._CLIENT_LIMIT:
            limited_at = client_failures[0]
        if len(self._global_failures) >= self._GLOBAL_LIMIT:
            global_limited_at = self._global_failures[0]
            limited_at = (
                global_limited_at
                if limited_at is None
                else min(limited_at, global_limited_at)
            )
        if limited_at is None:
            return None
        return max(1, int(self._WINDOW_SECONDS - (now - limited_at)) + 1)

    def _prune(self, failures: deque[float], now: float) -> None:
        cutoff = now - self._WINDOW_SECONDS
        while failures and failures[0] <= cutoff:
            failures.popleft()


def get_db_service(config: ServerConfig) -> DatabaseService:
    """Create a new DatabaseService instance for the current request."""
    service = DatabaseService(db_path=config.db_path, read_only=True)
    service.connect()
    return service


def _project_root() -> Path:
    """Resolve the project root, supporting PyInstaller's _MEIPASS bundling."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent.parent


def _resolve_filter(filter_json: str | None, db: DatabaseService) -> set[str] | None:
    """Parse a filter_json query parameter into a set of allowed item IDs.

    Args:
        filter_json: JSON string with include/exclude/mode/case_sensitive keys.
        db: Active DatabaseService for executing the tag query.

    Returns:
        A set of allowed item IDs, or None if no filter should be applied.

    """
    if not filter_json:
        return None
    try:
        filter_config = json.loads(filter_json)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON filter string provided to API")
        return None
    if not filter_config:
        return None
    try:
        result_tuples = db.filter_ids_by_tags(
            object_type=filter_config.get("object_type"),
            include=filter_config.get("include"),
            include_mode=filter_config.get("include_mode", "any"),
            exclude=filter_config.get("exclude"),
            exclude_mode=filter_config.get("exclude_mode", "any"),
            case_sensitive=filter_config.get("case_sensitive", False),
        )
        return {item_id for _, item_id in result_tuples}
    except Exception as e:
        logger.error(f"Error applying filter in API: {e}")
        return None


def _install_lan_authentication(app: FastAPI, config: ServerConfig) -> None:
    """Install API authentication when the server is explicitly shared on LAN."""
    rate_limiter = _AccessCodeRateLimiter()

    @app.middleware("http")
    async def authenticate_lan_api(request: Request, call_next: Any) -> Any:
        """Require the ephemeral access code for every LAN API request."""
        if not config.lan_access or not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        retry_after = rate_limiter.retry_after(client)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many access-code attempts"},
                headers={"Retry-After": str(retry_after)},
            )

        authorization = request.headers.get("Authorization", "")
        scheme, _, supplied_code = authorization.partition(" ")
        expected_code = config.access_code or ""
        authenticated = scheme.lower() == "bearer" and secrets.compare_digest(
            supplied_code, expected_code
        )
        if authenticated:
            return await call_next(request)

        retry_after = rate_limiter.record_failure(client)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many access-code attempts"},
                headers={"Retry-After": str(retry_after)},
            )
        return JSONResponse(
            status_code=401,
            content={"detail": "A valid LAN access code is required"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _install_security_headers(app: FastAPI) -> None:
    """Apply browser security headers to successful and failed responses."""

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Any:
        """Add security headers, including when an endpoint raises unexpectedly."""
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled longform server request failure")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def create_app(config: ServerConfig) -> FastAPI:
    """Factory function to create the FastAPI app with the given configuration."""
    app = FastAPI(title="ProjektKraken Longform Server")
    app.add_middleware(
        _KrakenTrustedHostMiddleware,
        allowed_hosts=config.allowed_hosts,
        www_redirect=False,
    )
    _install_lan_authentication(app, config)
    _install_security_headers(app)

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    templates = Jinja2Templates(directory=templates_dir)

    # -------------------------------------------------------------------------
    # API Endpoints
    # -------------------------------------------------------------------------

    @app.get("/api/tags")
    def get_tags() -> dict[str, Any]:
        """Get all available tags.

        Returns:
            JSON object with ``tags`` list of tag name strings.

        """
        db = get_db_service(config)
        try:
            tags_data = db.get_active_tags()
            tags = sorted([t["name"] for t in tags_data])
            return {"tags": tags}
        except Exception as e:
            logger.error(f"Error fetching tags: {e}")
            return {"tags": []}
        finally:
            db.close()

    @app.get("/api/theme")
    def get_theme() -> dict[str, Any]:
        """Return all available themes plus the active theme name.

        The active theme is captured from the Qt ThemeManager at server start
        and passed via ``ServerConfig.theme_name``. The themes dict is read
        from ``themes.json`` at the project root.

        Returns:
            ``{"active_theme": str, "themes": {name: {key: value}}}``.

        """
        themes_path = _project_root() / "themes.json"
        try:
            with open(themes_path, encoding="utf-8") as f:
                themes = json.load(f)
        except Exception as e:
            logger.error(f"Could not load themes.json from {themes_path}: {e}")
            themes = {}
        return {
            "active_theme": config.theme_name,
            "themes": themes,
        }

    @app.get("/api/longform")
    def get_longform(
        doc_id: DocId = DOC_ID_DEFAULT, filter_json: str | None = None
    ) -> dict[str, Any]:
        """Get the structured longform sequence as JSON with rendered HTML."""
        db = get_db_service(config)
        try:
            allowed_ids = _resolve_filter(filter_json, db)

            assert db._connection is not None, "Database not connected"
            sequence = build_longform_sequence(
                db._connection, doc_id=doc_id, allowed_ids=allowed_ids
            )

            data = []
            for item in sequence:
                title = item["meta"].get("title_override") or item["name"]
                heading_level = item["heading_level"]
                header_md = f"{'#' * heading_level} {title}\n\n"

                raw_content = item.get("content", "")
                full_markdown = header_md + raw_content
                html_content = render_longform_markdown(full_markdown)

                data.append(
                    {
                        "id": item["id"],
                        "table": item["table"],
                        "title": title,
                        "heading_level": heading_level,
                        "html": html_content,
                        "updated_at": item.get("updated_at"),
                        "lore_date": item.get("lore_date"),
                        "lore_duration": item.get("lore_duration", 0.0),
                    }
                )

            return {"title": doc_id, "sections": data}

        except Exception as e:
            logger.error(f"Error fetching longform: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            db.close()

    @app.get("/api/toc")
    def get_toc(
        doc_id: DocId = DOC_ID_DEFAULT, filter_json: str | None = None
    ) -> list[dict[str, Any]]:
        """Get just the Table of Contents structure, with optional filter."""
        db = get_db_service(config)
        try:
            allowed_ids = _resolve_filter(filter_json, db)
            assert db._connection is not None, "Database not connected"
            sequence = build_longform_sequence(
                db._connection, doc_id=doc_id, allowed_ids=allowed_ids
            )
            toc = []
            for item in sequence:
                toc.append(
                    {
                        "id": item["id"],
                        "title": item["meta"].get("title_override") or item["name"],
                        "level": item["heading_level"],
                    }
                )
            return toc
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # HTML Views
    # -------------------------------------------------------------------------

    @app.get("/")
    def root_redirect() -> RedirectResponse:
        """Redirect the root path to the longform viewer."""
        return RedirectResponse(url="/longform")

    @app.get("/longform", response_class=HTMLResponse)
    def view_longform(request: Request) -> HTMLResponse:
        """Render the longform viewer page with the active theme name embedded."""
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "initial_theme": config.theme_name,
                "lan_access": config.lan_access,
            },
        )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring server status."""
        return {"status": "ok"}

    return app
