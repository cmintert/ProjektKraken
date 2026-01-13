"""
AISearchManager - Handles AI search and semantic indexing for MainWindow.

This module contains all AI search and semantic indexing functionality extracted
from MainWindow to reduce its size and improve maintainability.
"""

import datetime
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSettings, Slot

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class AISearchManager(QObject):
    """
    Manages AI search and semantic indexing operations for the MainWindow.

    This class encapsulates all functionality related to:
    - AI settings dialog management
    - Semantic search queries
    - Search index rebuilding
    - Search result handling
    - Index status monitoring
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """
        Initialize the AISearchManager.

        Args:
            main_window: Reference to the MainWindow instance.
        """
        super().__init__()
        self.window = main_window

    @Slot()
    def show_ai_settings_dialog(self) -> None:
        """Shows the AI Settings dialog."""
        from src.gui.dialogs.ai_settings_dialog import AISettingsDialog

        if not self.window.ai_settings_dialog:
            self.window.ai_settings_dialog = AISettingsDialog(self.window)
            self.window.ai_settings_dialog.rebuild_index_requested.connect(
                self.on_ai_settings_rebuild_requested
            )
            self.window.ai_settings_dialog.index_status_requested.connect(
                self.refresh_search_index_status
            )
            # Initial status update
            self.refresh_search_index_status()

        self.window.ai_settings_dialog.show()
        self.window.ai_settings_dialog.raise_()
        self.window.ai_settings_dialog.activateWindow()

    @Slot(str)
    def on_ai_settings_rebuild_requested(self, object_type: str) -> None:
        """Handle rebuild request from dialog."""
        self.rebuild_search_index(object_type)

    @Slot(str, str, int)
    def perform_semantic_search(
        self, query: str, object_type_filter: str, top_k: int
    ) -> None:
        """
        Perform semantic search and display results.

        Args:
            query: Search query text.
            object_type_filter: Filter by 'entity' or 'event', or empty for all.
            top_k: Number of results to return.
        """
        try:
            if not hasattr(self.window, "gui_db_service"):
                logger.warning("GUI DB Service not ready for search.")
                return

            self.window.ai_search_panel.set_searching(True)

            # Import search service (requires optional dependencies)
            try:
                from src.services.search_service import create_search_service
            except ImportError as e:
                logger.error(
                    "Semantic search requires optional dependencies. "
                    "Install with: pip install -e .[search]"
                )
                self.window.ai_search_panel.set_searching(False)
                self.window.ai_search_panel.display_results([])
                self.window.set_status_message(
                    "Semantic search unavailable: missing dependencies", 5000
                )
                return

            # Create search service with GUI thread connection
            assert self.window.gui_db_service._connection is not None
            search_service = create_search_service(
                self.window.gui_db_service._connection
            )

            # Perform query
            results = search_service.query(
                text=query,
                object_type=object_type_filter if object_type_filter else None,
                top_k=top_k,
            )

            # Display results
            self.window.ai_search_panel.set_results(results)
            self.window.ai_search_panel.set_searching(False)

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            self.window.ai_search_panel.set_status(f"Search failed: {e}")
            self.window.ai_search_panel.set_searching(False)

    @Slot(str)
    def rebuild_search_index(self, object_type: str) -> None:
        """
        Rebuild the semantic search index.

        Args:
            object_type: Type to rebuild ('all', 'entity', 'event').
        """
        try:
            if not hasattr(self.window, "gui_db_service"):
                logger.warning("GUI DB Service not ready for rebuild.")
                return

            self.window.status_bar.showMessage(f"Rebuilding {object_type} index...", 0)

            # Import search service (requires optional dependencies)
            try:
                from src.services.search_service import create_search_service
            except ImportError:
                logger.error(
                    "Semantic search requires optional dependencies. "
                    "Install with: pip install -e .[search]"
                )
                self.window.set_status_message(
                    "Semantic search unavailable: missing dependencies", 5000
                )
                return

            # Create search service with GUI thread connection
            assert self.window.gui_db_service._connection is not None
            search_service = create_search_service(
                self.window.gui_db_service._connection
            )

            # Determine object types to rebuild
            if object_type == "all":
                types = ["entity", "event"]
            else:
                types = [object_type]

            # Get excluded attributes from QSettings
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            excluded_text = settings.value("ai_search_excluded_attrs", "", type=str)
            excluded = [
                attr.strip() for attr in excluded_text.split(",") if attr.strip()
            ]

            # Rebuild index
            counts = search_service.rebuild_index(
                object_types=types, excluded_attributes=excluded
            )

            # Show results
            total = sum(counts.values())
            msg = f"Rebuilt index: {total} objects indexed"
            self.window.status_bar.showMessage(msg, 5000)
            self.window.ai_search_panel.set_status(msg)

            # Refresh index status
            self.refresh_search_index_status()

        except Exception as e:
            logger.error(f"Index rebuild failed: {e}")
            self.window.status_bar.showMessage(f"Rebuild failed: {e}", 5000)
            self.window.ai_search_panel.set_status(f"Rebuild failed: {e}")

    @Slot(str, str)
    def on_search_result_selected(self, object_type: str, object_id: str) -> None:
        """
        Handle selection of a search result.

        Args:
            object_type: 'entity' or 'event'.
            object_id: Object UUID.
        """
        # Navigate to the selected item using centralized global selection
        self.window.set_global_selection(object_type, object_id)

    @Slot()
    def refresh_search_index_status(self) -> None:
        """Refresh the search index status display."""
        try:
            if not hasattr(self.window, "gui_db_service"):
                return

            # Get model configuration
            provider = os.getenv("EMBED_PROVIDER", "lmstudio")
            model = os.getenv("LMSTUDIO_MODEL", "Not configured")

            # Count indexed objects
            # Use gui_db_service connection (Main Thread)
            assert self.window.gui_db_service._connection is not None
            cursor = self.window.gui_db_service._connection.execute(
                "SELECT COUNT(*) FROM embeddings"
            )
            count = cursor.fetchone()[0]

            # Get last indexed time
            assert self.window.gui_db_service._connection is not None
            cursor = self.window.gui_db_service._connection.execute(
                "SELECT MAX(created_at) FROM embeddings"
            )
            last_time = cursor.fetchone()[0]

            if last_time:
                dt = datetime.datetime.fromtimestamp(last_time)
                last_indexed = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_indexed = "Never"

            # Update panel
            # Update dialog if visible
            if (
                hasattr(self.window, "ai_settings_dialog")
                and self.window.ai_settings_dialog
                and self.window.ai_settings_dialog.isVisible()
            ):
                self.window.ai_settings_dialog.update_status(
                    model=f"{provider}:{model}",
                    counts=str(count),
                    last_updated=last_indexed,
                )

        except Exception as e:
            logger.error(f"Failed to refresh index status: {e}")
