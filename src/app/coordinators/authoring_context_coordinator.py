"""Application orchestration for Event and Entity authoring context."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import Q_ARG, QObject, QTimer, Slot

from src.app.qt_invocation import invoke_queued
from src.core.authoring_context import EntityAuthoringContext, EventAuthoringContext
from src.core.entity_context_mode import EntityContextMode

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)

_REFRESH_DEBOUNCE_MS = 250


class AuthoringContextCoordinator(QObject):
    """Request and validate Event context snapshots across thread boundaries."""

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize request identity and debounce state."""
        super().__init__(parent=main_window)
        self.main_window = main_window
        self._active_request_id = ""
        self._active_entity_request_id = ""
        self.entity_mode = EntityContextMode.AT_PLAYHEAD
        self._entity_world = ""
        self._entity_inputs: tuple[str, str, float | None, str] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_REFRESH_DEBOUNCE_MS)
        self._timer.timeout.connect(self.refresh_now)
        self._entity_timer = QTimer(self)
        self._entity_timer.setSingleShot(True)
        self._entity_timer.setInterval(_REFRESH_DEBOUNCE_MS)
        self._entity_timer.timeout.connect(self.refresh_entity_now)

    def bind_session(self) -> None:
        """Bind after widget creation without extending shell signal registries."""
        window = self.main_window
        editor = window.entity_editor
        for selector in (
            editor.authoring_context.mode_selector,
            editor.llm_generator.entity_context_mode,
        ):
            selector.mode_changed.connect(self.set_entity_mode)
        window.time_coordinator.viewing_time_changed.connect(
            self.on_viewing_time_changed
        )
        window.data_coordinator.lore_mutation_applied.connect(
            self.schedule_entity_refresh
        )
        window.worker.calendar_config_loaded.connect(
            lambda _config: self.schedule_entity_refresh()
        )
        window.map_widget.map_selected.connect(self.schedule_entity_refresh)

    @Slot(float)
    def on_viewing_time_changed(self, _date: float) -> None:
        """Refresh only after accepted navigation and its draft guards."""
        self.schedule_entity_refresh()

    @Slot(str)
    def set_entity_mode(self, mode: str) -> None:
        """Synchronize both read-only selectors without changing authored state."""
        self.entity_mode = EntityContextMode(mode)
        editor = self.main_window.entity_editor
        for selector in (
            editor.authoring_context.mode_selector,
            editor.llm_generator.entity_context_mode,
        ):
            selector.set_mode(mode)
        self.schedule_entity_refresh()

    def _entity_query(self) -> tuple[str, str, float | None, str]:
        window = self.main_window
        world = str(getattr(window, "db_path", ""))
        if self._entity_world and world != self._entity_world:
            self._entity_world = world
            self.entity_mode = EntityContextMode.AT_PLAYHEAD
            self._active_entity_request_id = ""
            self._entity_inputs = None
            self.set_entity_mode(self.entity_mode.value)
        self._entity_world = world
        date = None
        if self.entity_mode != EntityContextMode.ALL_HISTORY:
            time = getattr(window, "time_coordinator", None)
            date = getattr(time, "current_playhead_time", None)
        return world, self.entity_mode.value, date, self._active_map_id()

    @Slot()
    @Slot(str)
    def schedule_refresh(self, _unused: str = "") -> None:
        """Debounce a refresh after an Event, date, or map change."""
        editor = self.main_window.event_editor
        if not editor.current_event_id:
            self._timer.stop()
            self._active_request_id = ""
            editor.clear_authoring_context()
            return
        editor.set_authoring_context_loading()
        self._timer.start()

    @Slot()
    def refresh_now(self) -> None:
        """Capture current inputs and queue a database-worker lookup."""
        editor = self.main_window.event_editor
        event_id = editor.current_event_id or ""
        if not event_id:
            editor.clear_authoring_context()
            return
        context_date = float(editor.temporal_widget.get_start())
        map_id = self._active_map_id()
        request_id = str(uuid.uuid4())
        self._active_request_id = request_id
        invoke_queued(
            self.main_window.worker,
            "load_event_authoring_context",
            Q_ARG(str, request_id),
            Q_ARG(str, event_id),
            Q_ARG(float, context_date),
            Q_ARG(str, map_id),
        )

    @Slot()
    @Slot(str)
    def schedule_entity_refresh(self, _unused: str = "") -> None:
        """Debounce a fresh saved-facts projection and invalidate older results."""
        self._active_entity_request_id = ""
        self._entity_inputs = None
        self._entity_query()
        generator = self.main_window.entity_editor.llm_generator
        generator.invalidate_context_preview()
        editor = self.main_window.entity_editor
        if not editor.current_entity_id:
            self._entity_timer.stop()
            self._active_entity_request_id = ""
            editor.clear_authoring_context()
            return
        editor.set_authoring_context_loading()
        self._entity_timer.start()

    @Slot()
    def refresh_entity_now(self) -> None:
        """Capture the current Entity and queue a database-worker lookup."""
        editor = self.main_window.entity_editor
        entity_id = editor.current_entity_id or ""
        if not entity_id:
            editor.clear_authoring_context()
            return
        self._entity_inputs = self._entity_query()
        _world, mode, date, _map_id = self._entity_inputs
        if mode != "all_history" and date is None:
            editor.set_authoring_context_unavailable()
            return
        request_id = str(uuid.uuid4())
        self._active_entity_request_id = request_id
        invoke_queued(
            self.main_window.worker,
            "load_entity_authoring_context",
            Q_ARG(str, request_id),
            Q_ARG(str, entity_id),
            Q_ARG(str, mode),
            Q_ARG(float, date if date is not None else 0.0),
        )

    @Slot(str, str, float, str, dict)
    def on_context_loaded(
        self,
        request_id: str,
        event_id: str,
        context_date: float,
        map_id: str,
        snapshot: dict,
    ) -> None:
        """Accept only the result matching the current editor inputs."""
        editor = self.main_window.event_editor
        if (
            request_id != self._active_request_id
            or event_id != (editor.current_event_id or "")
            or context_date != float(editor.temporal_widget.get_start())
            or map_id != self._active_map_id()
        ):
            logger.debug("Discarded stale Event authoring context %s", request_id)
            return
        if not snapshot:
            editor.set_authoring_context_unavailable()
            return
        try:
            context = EventAuthoringContext.from_dict(snapshot)
        except (KeyError, TypeError, ValueError):
            logger.error("Invalid Event authoring-context snapshot", exc_info=True)
            editor.set_authoring_context_unavailable()
            return
        editor.set_authoring_context(context)

    @Slot(str, str, dict)
    def on_entity_context_loaded(
        self, request_id: str, entity_id: str, snapshot: dict
    ) -> None:
        """Accept only the result matching the current Entity selection."""
        editor = self.main_window.entity_editor
        if (
            request_id != self._active_entity_request_id
            or entity_id != (editor.current_entity_id or "")
            or self._entity_inputs != self._entity_query()
        ):
            logger.debug("Discarded stale Entity authoring context %s", request_id)
            return
        if not snapshot:
            editor.set_authoring_context_unavailable()
            return
        try:
            context = EntityAuthoringContext.from_dict(snapshot)
        except (KeyError, TypeError, ValueError):
            logger.error("Invalid Entity authoring-context snapshot", exc_info=True)
            editor.set_authoring_context_unavailable()
            return
        if (context.mode, context.context_date) != (
            self.entity_mode.value,
            self._entity_query()[2],
        ):
            editor.set_authoring_context_unavailable()
            return
        editor.set_authoring_context(context)

    def _active_map_id(self) -> str:
        map_widget = getattr(self.main_window, "map_widget", None)
        if map_widget is None:
            return ""
        return str(map_widget.get_selected_map_id() or "")
