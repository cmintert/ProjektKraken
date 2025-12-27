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

    @app.get("/api/longform")
    def get_longform(doc_id: str = "default") -> dict[str, Any]:
        """
        Get the structured longform sequence as JSON.
        Includes rendered HTML content for each section.
        """
        db = get_db_service()
        try:
            # We reuse the logic from WikiTextEdit but we need a headless
            # version or similar logic.
            # Since WikiTextEdit is a QWidget, we can't easily run it in a
            # headless thread safely without QApplication.
            # However, looking at WikiTextEdit code, the rendering logic is
            # mostly string manipulation using the `markdown` library.
            # Let's reproduce the rendering pipeline here to avoid GUI
            # dependencies in the web thread.

            sequence = build_longform_sequence(db._connection, doc_id=doc_id)

            # Enrich items with rendered HTML
            # We'll need a simple markdown-to-html converter that mimics WikiTextEdit
            import markdown

            # Simple link resolver for server-side
            def resolve_links(text: str) -> str:
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
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()

    @app.get("/api/toc")
    def get_toc(doc_id: str = "default") -> list[dict[str, Any]]:
        """
        Get just the Table of Contents structure.
        """
        db = get_db_service()
        try:
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
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app
