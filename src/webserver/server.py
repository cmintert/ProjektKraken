"""Web Server Module for ProjektKraken.

Provides FastAPI-based REST API for serving longform documents and health checks. This
server is designed to run embedded within the main application via QThread.
"""

import html
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import markdown  # type: ignore[import-untyped]  # Package has no py.typed marker.
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.services.db_service import DatabaseService
from src.services.longform_builder import build_longform_sequence
from src.webserver.config import ServerConfig

logger = logging.getLogger(__name__)

logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

_config: ServerConfig = ServerConfig()


def get_db_service() -> DatabaseService:
    """Create a new DatabaseService instance for the current request."""
    service = DatabaseService(db_path=_config.db_path)
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


def _resolve_wikilinks(text: str) -> str:
    """Convert wiki-style links to HTML anchors with data-target for JS resolution.

    Args:
        text: Raw markdown text containing ``[[Target]]`` or ``[[Target|Label]]``.

    Returns:
        Text with wiki links replaced by ``<a class="wikilink" data-target=...>``.

    """

    def _piped(match: re.Match[str]) -> str:
        target = html.escape(match.group(1).strip(), quote=True)
        label = html.escape(match.group(2).strip(), quote=True)
        return f'<a class="wikilink" data-target="{target}">{label}</a>'

    def _plain(match: re.Match[str]) -> str:
        target = html.escape(match.group(1).strip(), quote=True)
        return f'<a class="wikilink" data-target="{target}">{target}</a>'

    text = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", _piped, text)
    text = re.sub(r"\[\[([^]]+)\]\]", _plain, text)
    return text


def create_app(config: ServerConfig) -> FastAPI:
    """Factory function to create the FastAPI app with the given configuration."""
    global _config
    _config = config

    app = FastAPI(title="ProjektKraken Longform Server")

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
        db = get_db_service()
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
            "active_theme": _config.theme_name,
            "themes": themes,
        }

    @app.get("/api/longform")
    def get_longform(
        doc_id: str = "default", filter_json: str | None = None
    ) -> dict[str, Any]:
        """Get the structured longform sequence as JSON with rendered HTML."""
        db = get_db_service()
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
                processed_body = _resolve_wikilinks(raw_content)

                full_markdown = header_md + processed_body

                html_content = markdown.markdown(
                    full_markdown, extensions=["extra", "nl2br"]
                )

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
        doc_id: str = "default", filter_json: str | None = None
    ) -> list[dict[str, Any]]:
        """Get just the Table of Contents structure, with optional filter."""
        db = get_db_service()
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
            {"initial_theme": _config.theme_name},
        )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring server status."""
        return {"status": "ok"}

    return app
