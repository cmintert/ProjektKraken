"""AISearchManager - Handles AI search and semantic indexing for MainWindow.

This module contains all AI search and semantic indexing functionality extracted
from MainWindow to reduce its size and improve maintainability.
"""

import datetime
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QMetaObject, QObject, QSettings, Qt, QTimer, Slot

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.ai_generation import AIGenerationPreferences
from src.core.logging_config import get_logger
from src.services.prompt_builder import DEFAULT_SYSTEM_PROMPT

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
        worker = getattr(self.window, "worker", None)
        if worker is not None:
            worker.ai_generation_preferences_loaded.connect(
                self.on_ai_preferences_loaded,
                Qt.ConnectionType.QueuedConnection,
            )
        self._preference_save_timer = QTimer(self)
        self._preference_save_timer.setSingleShot(True)
        self._preference_save_timer.setInterval(500)
        self._preference_save_timer.timeout.connect(
            self._save_current_world_preferences
        )
        for editor_name in ("entity_editor", "event_editor"):
            editor = getattr(self.window, editor_name, None)
            generator = getattr(editor, "llm_generator", None)
            if generator is not None:
                generator.preferences_changed.connect(
                    self._preference_save_timer.start
                )

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
            self.window.worker_manager.load_ai_preferences_requested.emit()
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

        dialog = getattr(self.window, "ai_settings_dialog", None)
        if dialog is not None:
            self._save_current_world_preferences()

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
        if hasattr(self.window, "event_editor") and hasattr(
            self.window.event_editor, "llm_generator"
        ):
            self.window.event_editor.llm_generator.refresh_settings()

    @Slot(object)
    def on_ai_preferences_loaded(self, raw_preferences: object) -> None:
        """Apply world preferences, or seed a new world from legacy settings."""
        dialog = getattr(self.window, "ai_settings_dialog", None)
        if isinstance(raw_preferences, dict):
            preferences = AIGenerationPreferences.from_dict(raw_preferences)
            self._cache_world_preferences(preferences)
            if dialog is not None:
                dialog.apply_world_preferences(preferences)
        else:
            self._save_current_world_preferences()

        for editor_name in ("entity_editor", "event_editor"):
            editor = getattr(self.window, editor_name, None)
            generator = getattr(editor, "llm_generator", None)
            if generator is not None:
                generator.refresh_settings()

    @staticmethod
    def _cache_world_preferences(
        preferences: AIGenerationPreferences,
    ) -> None:
        """Cache active-world preferences for existing UI consumers."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        values = {
            "ai_gen_system_prompt": preferences.persona,
            "ai_gen_max_tokens": preferences.max_tokens,
            "ai_gen_temperature": preferences.temperature_percent,
            "ai_gen_rag_enabled": preferences.rag_enabled,
            "ai_gen_rag_limit": preferences.rag_limit,
            "ai_gen_spatial_enabled": preferences.spatial_enabled,
            "ai_gen_filter_reasoning": preferences.filter_reasoning,
            "ai_gen_audit_log": preferences.audit_enabled,
            "ai_gen_template_id": preferences.selected_template_id,
            "ai_gen_entity_prompt": preferences.entity_prompt_draft,
            "ai_gen_event_prompt": preferences.event_prompt_draft,
        }
        for key, value in values.items():
            settings.setValue(key, value)

    @Slot()
    def _save_current_world_preferences(self) -> None:
        """Persist current creative settings via the queued DB worker path."""
        dialog = getattr(self.window, "ai_settings_dialog", None)
        if dialog is not None:
            preferences = dialog.export_world_preferences()
        else:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            preferences = AIGenerationPreferences(
                persona=str(
                    settings.value("ai_gen_system_prompt", DEFAULT_SYSTEM_PROMPT)
                ),
                max_tokens=cast(
                    int,
                    settings.value("ai_gen_max_tokens", 512, type=int),
                ),
                temperature_percent=cast(
                    int,
                    settings.value("ai_gen_temperature", 70, type=int),
                ),
                rag_enabled=cast(
                    bool,
                    settings.value("ai_gen_rag_enabled", True, type=bool),
                ),
                rag_limit=cast(
                    int,
                    settings.value("ai_gen_rag_limit", 3, type=int),
                ),
                spatial_enabled=cast(
                    bool,
                    settings.value(
                        "ai_gen_spatial_enabled", False, type=bool
                    ),
                ),
                filter_reasoning=cast(
                    bool,
                    settings.value(
                        "ai_gen_filter_reasoning", True, type=bool
                    ),
                ),
                audit_enabled=cast(
                    bool,
                    settings.value("ai_gen_audit_log", False, type=bool),
                ),
                selected_template_id=str(
                    settings.value("ai_gen_template_id", "") or ""
                ),
                entity_prompt_draft=str(
                    settings.value("ai_gen_entity_prompt", "") or ""
                ),
                event_prompt_draft=str(
                    settings.value("ai_gen_event_prompt", "") or ""
                ),
            )
        self.window.worker_manager.save_ai_preferences_requested.emit(
            preferences.to_dict()
        )

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
        """Dispatch index rebuild to the worker thread.

        Args:
            object_type: Type to rebuild ('all', 'entity', 'event').

        """
        try:
            worker = getattr(self.window, "worker", None)
            if worker is None:
                logger.warning("Worker not ready for rebuild.")
                return

            self.window.status_bar.showMessage(
                f"Rebuilding {object_type} index...", 0
            )

            # Disable the rebuild button in the dialog while running
            dlg = getattr(self.window, "ai_settings_dialog", None)
            if dlg is not None:
                dlg.set_rebuild_in_progress(True)

            # Get excluded attributes from QSettings
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            excluded_text = settings.value(
                "ai_search_excluded_attrs", "", type=str
            )
            excluded = [
                attr.strip()
                for attr in excluded_text.split(",")
                if attr.strip()
            ]

            # Dispatch to worker thread via WorkerManager signal
            self.window.worker_manager.rebuild_index_requested.emit(
                object_type, excluded
            )

        except Exception as e:
            logger.error(f"Failed to dispatch index rebuild: {e}")
            self._set_status(f"Rebuild failed: {e}")

    @Slot(int, int, int)
    def on_index_rebuild_progress(
        self, done: int, total: int, pct: int
    ) -> None:
        """Handle progress updates from the worker thread.

        Args:
            done: Items processed so far.
            total: Total items.
            pct: Percentage complete.

        """
        self.window.status_bar.showMessage(
            f"Indexing {done}/{total} ({pct}%)...", 0
        )
        dlg = getattr(self.window, "ai_settings_dialog", None)
        if dlg is not None:
            dlg.update_rebuild_progress(done, total, pct)

    @Slot(int, int)
    def on_index_rebuild_finished(self, succeeded: int, failed: int) -> None:
        """Handle rebuild completion from the worker thread.

        Args:
            succeeded: Number of successfully indexed items.
            failed: Number of failed items.

        """
        if failed:
            msg = (
                f"Index rebuilt: {succeeded} indexed, {failed} failed"
            )
        else:
            msg = f"Index rebuilt: {succeeded} objects indexed"
        self._set_status(msg)

        dlg = getattr(self.window, "ai_settings_dialog", None)
        if dlg is not None:
            dlg.set_rebuild_in_progress(False)

        self.refresh_search_index_status()

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

            from src.services.search_service import get_llm_settings_from_qsettings

            qsettings = get_llm_settings_from_qsettings()
            provider = qsettings["provider"]
            model = qsettings.get("st_model") or qsettings.get("lm_model") or "default"

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

    def _set_status(self, msg: str, duration: int = 5000) -> None:
        """Update the status bar and AI search panel with the same message."""
        self.window.status_bar.showMessage(msg, duration)
        self.window.ai_search_panel.set_status(msg)
