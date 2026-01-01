"""
Web Server Module for ProjektKraken.

Provides FastAPI-based REST API for serving longform documents and health checks.
This server is designed to run embedded within the main application via QThread.
"""

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.services.db_service import DatabaseService
from src.services.longform_builder import build_longform_sequence
from src.webserver.config import ServerConfig

# Configure logging
logger = logging.getLogger(__name__)

# Suppress noisy markdown logs
logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

# Global config (set on startup)
_config: ServerConfig = ServerConfig()


def get_db_service() -> DatabaseService:
    """
    Create a new DatabaseService instance for the current request.
    This ensures thread safety by creating a fresh connection per request/thread.
    """
    service = DatabaseService(db_path=_config.db_path)
    service.connect()
    # Ensure WAL mode (should be set by service.connect, but no harm checking)
    return service


def create_app(config: ServerConfig) -> FastAPI:
    """
    Factory function to create the FastAPI app with the given configuration.
    """
    global _config
    _config = config

    app = FastAPI(title="ProjektKraken Longform Server")

    # Mount static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Setup Templates
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    templates = Jinja2Templates(directory=templates_dir)

    # -------------------------------------------------------------------------
    # API Endpoints
    # -------------------------------------------------------------------------

    @app.get("/api/tags")
    def get_tags() -> dict[str, Any]:
        """
        Get all available tags.

        Returns:
            JSON object with "tags": list[str].
        """
        db = get_db_service()
        try:
            # db.get_active_tags() returns List[Dict] with 'id', 'name', etc.
            # We want the human-readable names of tags that actually have content.
            tags_data = db.get_active_tags()
            # Extract 'name' for display.
            tags = sorted([t["name"] for t in tags_data])
            return {"tags": tags}
        except Exception as e:
            logger.error(f"Error fetching tags: {e}")
            return {"tags": []}

    @app.get("/api/longform")
    def get_longform(
        doc_id: str = "default", filter_json: str | None = None
    ) -> dict[str, Any]:
        """
        Get the structured longform sequence as JSON.
        Includes rendered HTML content for each section.

        Args:
            doc_id: Document ID.
            filter_json: Optional JSON string configuring filters.
        """
        db = get_db_service()
        try:
            allowed_ids = None
            if filter_json:
                try:
                    import json

                    filter_config = json.loads(filter_json)
                    if filter_config:
                        # Use DRY compliance: Reuse existing filter logic
                        # filter_ids_by_tags returns List[tuple[str, str]] of (type, id)
                        result_tuples = db.filter_ids_by_tags(
                            object_type=filter_config.get("object_type"),
                            include=filter_config.get("include"),
                            include_mode=filter_config.get("include_mode", "any"),
                            exclude=filter_config.get("exclude"),
                            exclude_mode=filter_config.get("exclude_mode", "any"),
                            case_sensitive=filter_config.get("case_sensitive", False),
                        )
                        # Extract just the IDs (second element of each tuple)
                        allowed_ids = {item_id for _, item_id in result_tuples}
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON filter string provided to API")
                except Exception as e:
                    logger.error(f"Error applying filter in API: {e}")
                    print(f"DEBUG EXCEPTION: {e}")

            assert db._connection is not None, "Database not connected"
            sequence = build_longform_sequence(
                db._connection, doc_id=doc_id, allowed_ids=allowed_ids
            )

            # Since WikiTextEdit is a QWidget, we can't easily run it in a
            # headless thread safely without QApplication.
            # However, looking at WikiTextEdit code, the rendering logic is
            # mostly string manipulation using the `markdown` library.
            import markdown

            def resolve_links(text: str) -> str:
                """Convert wiki-style links to plain text or HTML anchors.

                Args:
                    text: Text containing wiki-style [[links]].

                Returns:
                    Text with links resolved/stripped for display.
                """
                # Basic [[Link]] -> [Link](Link) or similar logic
                # For the web view, we might want [[Link]] to jump to anchors or
                # just be plain text.
                # Logic: [[id:123|Label]] -> <a href="#item-index">Label</a>?
                # For V1 read-only, we might just strip wiki links or make them bold.
                import re

                # Replace [[Target|Label]] -> Label
                text = re.sub(r"\[\[[^]|]+\|([^]]+)\]\]", r"\1", text)
                # Replace [[Target]] -> Target
                text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
                return text

            data = []
            for item in sequence:
                # Construct Markdown with Header
                title = item["meta"].get("title_override") or item["name"]
                heading_level = item["heading_level"]
                header_md = f"{'#' * heading_level} {title}\n\n"

                # Pre-process links in content
                raw_content = item.get("content", "")
                processed_body = resolve_links(raw_content)

                # Combine
                full_markdown = header_md + processed_body

                # Convert to HTML
                html_content = markdown.markdown(
                    full_markdown, extensions=["extra", "nl2br"]
                )

                data.append(
                    {
                        "id": item["id"],
                        "table": item["table"],
                        "title": item["meta"].get("title_override") or item["name"],
                        "heading_level": item["heading_level"],
                        "html": html_content,
                        "updated_at": item.get("updated_at"),  # Not always present
                    }
                )

            return {"title": doc_id, "sections": data}

        except Exception as e:
            logger.error(f"Error fetching longform: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            db.close()

    @app.get("/api/toc")
    def get_toc(doc_id: str = "default") -> list[dict[str, Any]]:
        """
        Get just the Table of Contents structure.
        """
        db = get_db_service()
        try:
            assert db._connection is not None, "Database not connected"
            sequence = build_longform_sequence(db._connection, doc_id=doc_id)
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
    # HTML View
    # -------------------------------------------------------------------------

    @app.get("/longform", response_class=HTMLResponse)
    def view_longform(request: Request) -> HTMLResponse:
        """Render the longform viewer page.

        Args:
            request: The FastAPI request object.

        Returns:
            HTML response with the longform viewer interface.
        """
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring server status.

        Returns:
            Dictionary with status indicator.
        """
        return {"status": "ok"}

    return app
