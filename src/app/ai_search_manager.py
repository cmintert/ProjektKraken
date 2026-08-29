"""AISearchManager - Handles AI search and semantic indexing for MainWindow.

This module contains all AI search and semantic indexing functionality extracted
from MainWindow to reduce its size and improve maintainability.
"""

import datetime
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Slot

from src.app.constants import (
    AI_SEARCH_THREAD_SHUTDOWN_MS,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.qt_invocation import invoke_queued
from src.core.ai_generation import AIGenerationPreferences, TaskTemplate
from src.core.logging_config import get_logger
from src.services.prompt_builder import DEFAULT_SYSTEM_PROMPT
from src.services.semantic_search_worker import SemanticSearchWorker
from src.services.task_template_catalog import TaskTemplateCatalog

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
        self._task_template_catalog = TaskTemplateCatalog()
        self._custom_task_templates: tuple[TaskTemplate, ...] = ()
        self._task_templates = self._task_template_catalog.built_in_templates()
        self._search_thread: QThread | None = None
        self._search_worker: SemanticSearchWorker | None = None
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
            self.window.ai_settings_dialog.task_templates_changed.connect(
                self._on_task_templates_changed
            )
            self.window.ai_settings_dialog.set_task_templates(self._task_templates)
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
            invoke_queued(
                self.window.worker,
                "refresh_ai_settings",
            )

        # Refresh entity editor's LLM generation widget
        if hasattr(self.window, "entity_editor") and hasattr(
            self.window.entity_editor, "llm_generator"
        ):
            self.window.entity_editor.llm_generator.set_task_templates(
                self._task_templates
            )
            self.window.entity_editor.llm_generator.refresh_settings()
        if hasattr(self.window, "event_editor") and hasattr(
            self.window.event_editor, "llm_generator"
        ):
            self.window.event_editor.llm_generator.set_task_templates(
                self._task_templates
            )
            self.window.event_editor.llm_generator.refresh_settings()

    @Slot(object)
    def on_ai_preferences_loaded(self, raw_preferences: object) -> None:
        """Apply world preferences, or seed a new world from legacy settings."""
        dialog = getattr(self.window, "ai_settings_dialog", None)
        if isinstance(raw_preferences, dict):
            loaded = AIGenerationPreferences.from_dict(raw_preferences)
            preferences = self._task_template_catalog.migrate_preferences(loaded)
            self._custom_task_templates = preferences.custom_task_templates
            self._task_templates = self._task_template_catalog.merge(
                self._custom_task_templates
            )
            self._cache_world_preferences(preferences)
            if dialog is not None:
                dialog.set_task_templates(self._task_templates)
                dialog.apply_world_preferences(preferences)
            if preferences != loaded:
                self.window.worker_manager.save_ai_preferences_requested.emit(
                    preferences.to_dict()
                )
        else:
            self._save_current_world_preferences()

        for editor_name in ("entity_editor", "event_editor"):
            editor = getattr(self.window, editor_name, None)
            generator = getattr(editor, "llm_generator", None)
            if generator is not None:
                generator.set_task_templates(self._task_templates)
                generator.refresh_settings()

    @Slot(object)
    def _on_task_templates_changed(self, templates: object) -> None:
        """Validate and publish a serializable world-template snapshot."""
        if not isinstance(templates, (list, tuple)):
            return
        custom = tuple(
            template for template in templates if isinstance(template, TaskTemplate)
        )
        merged = self._task_template_catalog.merge(custom)
        for template in custom:
            self._task_template_catalog.validate_world_template(template, merged)
        self._custom_task_templates = custom
        self._task_templates = merged

        dialog = getattr(self.window, "ai_settings_dialog", None)
        if dialog is not None:
            dialog.set_task_templates(self._task_templates)
        for editor_name in ("entity_editor", "event_editor"):
            editor = getattr(self.window, editor_name, None)
            generator = getattr(editor, "llm_generator", None)
            if generator is not None:
                generator.set_task_templates(self._task_templates)
        self._save_current_world_preferences()

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
            "ai_gen_entity_template_id": preferences.selected_entity_template_id,
            "ai_gen_event_template_id": preferences.selected_event_template_id,
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
                selected_entity_template_id=str(
                    settings.value("ai_gen_entity_template_id", "") or ""
                ),
                selected_event_template_id=str(
                    settings.value("ai_gen_event_template_id", "") or ""
                ),
                entity_prompt_draft=str(
                    settings.value("ai_gen_entity_prompt", "") or ""
                ),
                event_prompt_draft=str(
                    settings.value("ai_gen_event_prompt", "") or ""
                ),
                custom_task_templates=self._custom_task_templates,
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
        if self._search_thread is not None and self._search_thread.isRunning():
            self.window.ai_search_panel.set_status("A search is already running.")
            return
        db_path = getattr(self.window, "db_path", "")
        if not db_path:
            self.window.ai_search_panel.set_status(
                "Search failed: no active world database is available"
            )
            return

        self.window.ai_search_panel.set_searching(True)
        thread = QThread(self)
        worker = SemanticSearchWorker(
            db_path,
            query,
            object_type_filter or None,
            top_k,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_search_completed)
        worker.failed.connect(self._on_search_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_search_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._search_thread = thread
        self._search_worker = worker
        thread.start()

    @Slot(list)
    def _on_search_completed(self, results: list[dict[str, object]]) -> None:
        """Display results returned by the background semantic worker."""
        self.window.ai_search_panel.set_results(results)
        self.window.ai_search_panel.set_searching(False)

    @Slot(str)
    def _on_search_failed(self, message: str) -> None:
        """Restore search controls and display a background-worker error."""
        self.window.ai_search_panel.set_status(f"Search failed: {message}")
        self.window.ai_search_panel.set_searching(False)

    @Slot()
    def _on_search_thread_finished(self) -> None:
        """Release references after a semantic-search thread exits."""
        self._search_worker = None
        self._search_thread = None

    def shutdown(self) -> None:
        """Stop an active semantic-search thread during application shutdown."""
        thread = self._search_thread
        if thread is None or not thread.isRunning():
            return
        thread.requestInterruption()
        thread.quit()
        if not thread.wait(AI_SEARCH_THREAD_SHUTDOWN_MS):
            logger.warning("Semantic search did not stop in time; terminating thread")
            thread.terminate()
            thread.wait()

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
            excluded_text = str(
                settings.value("ai_search_excluded_attrs", "", type=str) or ""
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

    @Slot(int, int, int)
    def on_index_rebuild_finished(
        self,
        indexed: int,
        unchanged: int,
        failed: int,
    ) -> None:
        """Handle rebuild completion from the worker thread.

        Args:
            indexed: Number of newly indexed or updated items.
            unchanged: Number of items whose existing index was current.
            failed: Number of failed items.

        """
        if failed:
            msg = (
                f"Index rebuilt: {indexed} indexed, "
                f"{unchanged} unchanged, {failed} failed"
            )
        else:
            msg = f"Index rebuilt: {indexed} indexed, {unchanged} unchanged"
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
        self.window.workspace.show_panel("project")
        self.window.unified_list.select_item(object_type, object_id)

    @Slot()
    def refresh_search_index_status(self) -> None:
        """Refresh the search index status display."""
        self.window.worker_manager.load_embedding_stats_requested.emit()

    @Slot(dict)
    def on_embedding_stats_loaded(self, stats: dict[str, object]) -> None:
        """Update the settings dialog with worker-loaded index statistics."""
        try:
            from src.services.search_service import get_llm_settings_from_qsettings

            qsettings = get_llm_settings_from_qsettings()
            provider = qsettings["provider"]
            model = qsettings.get("st_model") or qsettings.get("lm_model") or "default"
            count_value = stats.get("count", 0)
            count = (
                int(count_value)
                if isinstance(count_value, (int, float, str))
                else 0
            )
            last_time = stats.get("last_updated")
            last_indexed = (
                datetime.datetime.fromtimestamp(float(last_time)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if isinstance(last_time, (int, float))
                else "Never"
            )
            dialog = getattr(self.window, "ai_settings_dialog", None)
            if dialog is not None and dialog.isVisible():
                dialog.update_status(
                    model=f"{provider}:{model}",
                    counts=str(count),
                    last_updated=last_indexed,
                )
        except Exception:
            logger.exception("Failed to refresh index status")

    def _set_status(self, msg: str, duration: int = 5000) -> None:
        """Update the status bar and AI search panel with the same message."""
        self.window.status_bar.showMessage(msg, duration)
        self.window.ai_search_panel.set_status(msg)
