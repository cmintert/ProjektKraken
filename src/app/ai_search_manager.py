"""AISearchManager - Handles AI search and semantic indexing for MainWindow.

This module contains all AI search and semantic indexing functionality extracted
from MainWindow to reduce its size and improve maintainability.
"""

import datetime
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QMetaObject, QObject, QSettings, Qt, Slot

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class AISearchManager(QObject):
    """Manages AI search and semantic indexing operations for the MainWindow.

    This class encapsulates all functionality related to:
    - AI settings dialog management
    - Semantic search queries
    - Search index rebuilding
    - Search result handling
    - Index status monitoring
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the AISearchManager.

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
            self.window.ai_settings_dialog.settings_saved.connect(
                self._on_settings_saved
            )
            # Initial status update
            self.refresh_search_index_status()

        self.window.ai_settings_dialog.show()
        self.window.ai_settings_dialog.raise_()
        self.window.ai_settings_dialog.activateWindow()

    @Slot()
    def _on_settings_saved(self) -> None:
        """Handle settings saved from AI Settings dialog.

        Propagates settings refresh to:
        - DatabaseWorker (clears cached LLM provider in SummaryService)
        - EntityEditor's LLMGenerationWidget (reloads templates/settings)
        """
        logger.info("AI settings saved — propagating refresh")

        # Refresh worker-thread services (cross-thread call)
        if hasattr(self.window, "worker") and self.window.worker:
            QMetaObject.invokeMethod(
                self.window.worker,
                "refresh_ai_settings",
                Qt.ConnectionType.QueuedConnection,
            )

        # Refresh entity editor's LLM generation widget
        if hasattr(self.window, "entity_editor") and hasattr(
            self.window.entity_editor, "llm_generator"
        ):
            self.window.entity_editor.llm_generator.refresh_settings()

    @Slot(str)
    def on_ai_settings_rebuild_requested(self, object_type: str) -> None:
        """Handle rebuild request from dialog."""
        self.rebuild_search_index(object_type)

    @Slot(str, str, int)
    def perform_semantic_search(
        self, query: str, object_type_filter: str, top_k: int
    ) -> None:
        """Perform semantic search and display results.

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

            # Use RAGService for hybrid search (Name + Semantic)
            from src.services.rag_service import RAGService

            # We need the db_path from somewhere.
            # gui_db_service has a path attribute? Or we use connection?
            # RAGService takes db_path string currently.
            # The gui_db_service abstracts the connection.
            # Let's see if we can get the path.
            # Standard pattern: self.window.db_path usually exists or we get it
            # from UIManager?
            # MainWindow has self.db_path (passed to LongformEditorWidget in
            # main_window.py).
            # Let's assume self.window.db_path exists.

            if not (db_path := getattr(self.window, "db_path", None)):
                # Fallback to direct service creation if no path (but RAGService
                # needs path for isolation)
                # Actually, RAGService creates its own connection for thread safety.
                # If we can't get path, we can't use RAGService easily without refactor.
                # Let's check MainWindow init... yes it has db_path logic usually
                # (or active_world).
                # Wait, MainWindow.__init__ doesn't show self.db_path assignment
                # explicitly in the snippet I saw earlier (lines 100-300).
                # But LongformEditorWidget received self.db_path (line 215).
                # So it must exist.
                pass

            if db_path:
                rag_service = RAGService(db_path)
                results = rag_service.search(
                    query=query,
                    top_k=top_k,
                    object_type=object_type_filter or None,
                )
            else:
                # Fallback to old method if no db_path (unlikely)
                logger.warning(
                    "No db_path found for RAGService, falling back to direct connection"
                )
                from src.services.search_service import create_search_service

                assert self.window.gui_db_service._connection is not None
                search_service = create_search_service(
                    self.window.gui_db_service._connection
                )
                results = search_service.query(
                    text=query,
                    object_type=object_type_filter or None,
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
        """Rebuild the semantic search index.

        Args:
            object_type: Type to rebuild ('all', 'entity', 'event').

        """
        try:
            if not hasattr(self.window, "gui_db_service"):
                logger.warning("GUI DB Service not ready for rebuild.")
                return

            self.window.status_bar.showMessage(f"Rebuilding {object_type} index...", 0)

            # Import search service
            from src.services.search_service import create_search_service

            # Create search service with GUI thread connection
            assert self.window.gui_db_service._connection is not None
            search_service = create_search_service(
                self.window.gui_db_service._connection
            )

            # Determine object types to rebuild
            types = ["entity", "event"] if object_type == "all" else [object_type]

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
        """Handle selection of a search result.

        Args:
            object_type: 'entity' or 'event'.
            object_id: Object UUID.

        """
        # Select the item in the unified list via the dock widget
        if (
            hasattr(self.window, "ui_manager")
            and "list" in self.window.ui_manager.docks
        ):
            list_dock = self.window.ui_manager.docks["list"]
            list_widget = list_dock.widget()
            if list_widget and hasattr(list_widget, "select_item"):
                list_widget.select_item(object_type, object_id)

    @Slot()
    def refresh_search_index_status(self) -> None:
        """Refresh the search index status display."""
        try:
            if not hasattr(self.window, "gui_db_service"):
                return

            provider = os.getenv("EMBED_PROVIDER", "lmstudio")
            model = os.getenv("LMSTUDIO_MODEL", "Not configured")

            stats = self.window.gui_db_service.get_embedding_stats()
            count = stats["count"]

            if last_time := stats["last_updated"]:
                dt = datetime.datetime.fromtimestamp(last_time)
                last_indexed = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_indexed = "Never"

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
