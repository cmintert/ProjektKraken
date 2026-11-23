"""Application Coordinator Facade.

Provides a single entry point to all coordinators, reducing the number of imports
and attributes that MainWindow manages directly. MainWindow creates AppCoordinator
and accesses individual coordinators through it.
"""

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Q_ARG, QObject

from src.app.qt_invocation import invoke_queued

if TYPE_CHECKING:
    from src.app.main_window import MainWindow
    from src.core.authoring_scope import AuthoringScope

logger = logging.getLogger(__name__)


class AppCoordinator(QObject):
    """Facade grouping all application coordinators.

    Instead of MainWindow importing and instantiating each coordinator separately,
    it creates a single AppCoordinator that owns and exposes them.

    Attributes:
        data: DataCoordinator for data loading orchestration.
        context_tags: ContextTagCoordinator for session creation tags and recovery.
        time: TimeCoordinator for time/playhead management.
        editor: EditorCoordinator for editor state management.
        navigation: NavigationCoordinator for item selection/navigation.
        backup: BackupCoordinator for backup operations.
        fast_inject: FastInjectCoordinator for template injection.
        import_coord: ImportCoordinator for file import operations.

    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize all coordinators with the main window reference.

        Args:
            main_window: The main window instance.

        """
        super().__init__(parent=main_window)

        from src.app.coordinators.authoring_context_coordinator import (
            AuthoringContextCoordinator,
        )
        from src.app.coordinators.backup_coordinator import BackupCoordinator
        from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
        from src.app.coordinators.data_coordinator import DataCoordinator
        from src.app.coordinators.editor_coordinator import EditorCoordinator
        from src.app.coordinators.fast_inject_coordinator import (
            FastInjectCoordinator,
        )
        from src.app.coordinators.feature_geometry_coordinator import (
            FeatureGeometryCoordinator,
        )
        from src.app.coordinators.import_coordinator import ImportCoordinator
        from src.app.coordinators.navigation_coordinator import (
            NavigationCoordinator,
        )
        from src.app.coordinators.time_coordinator import TimeCoordinator
        from src.app.coordinators.trajectory_edit_coordinator import (
            TrajectoryEditCoordinator,
        )

        self.context_tags = ContextTagCoordinator(main_window)
        self.authoring_context = AuthoringContextCoordinator(main_window)
        self.data = DataCoordinator(main_window)
        self.time = TimeCoordinator(main_window)
        self.editor = EditorCoordinator(main_window)
        self.navigation = NavigationCoordinator(main_window)
        self.backup = BackupCoordinator(main_window)
        self.fast_inject = FastInjectCoordinator(main_window)
        self.import_coord = ImportCoordinator(main_window)
        self.trajectory_edit = TrajectoryEditCoordinator(main_window)
        self.feature_geometry = FeatureGeometryCoordinator(main_window)

        self.main_window = main_window
        logger.debug("AppCoordinator initialized with 11 coordinators")

    def bind_map_edits(self) -> None:
        """Compose draft protection once widgets and session owners exist."""
        from PySide6.QtCore import Qt

        from src.app.coordinators.map_edit_transition_coordinator import (
            MapEditTransitionCoordinator,
        )
        from src.gui.dialogs.map_edit_transition_dialog import decide_map_transition

        window = self.main_window
        self.bind_neighbor_regions()
        from src.app.connected_map_composition import compose_connected_maps

        self.connected_maps = compose_connected_maps(window, self)
        hierarchy = window.map_handler.hierarchy_coordinator
        window.worker.command_finished.connect(
            hierarchy.on_command_finished, Qt.ConnectionType.QueuedConnection
        )
        self.map_edits: MapEditTransitionCoordinator = MapEditTransitionCoordinator(
            [
                self.trajectory_edit,
                self.feature_geometry,
                self.neighbor_regions,
                hierarchy,
            ],
            lambda: str(getattr(window.current_world, "id", "")),
            lambda reason, status: decide_map_transition(reason, status, window),
            lambda message: window.status_bar.showMessage(message, 5000),
            self,
        )
        window.map_widget.edit_transition_handler = self.map_edits.request_transition

    def bind_neighbor_regions(self) -> None:
        """Compose neighboring-region ownership with explicit UI/command ports."""
        if hasattr(self, "neighbor_regions"):
            return
        from PySide6.QtCore import Qt

        from src.app.coordinators.neighbor_region_coordinator import (
            NeighborRegionCoordinator,
            NeighborRegionPorts,
        )

        window = self.main_window
        widget = window.map_widget
        self.neighbor_regions = NeighborRegionCoordinator(
            NeighborRegionPorts(
                view=widget.view,
                controls=widget.neighbor_region_controls,
                map_id=widget.get_selected_map_id,
                world_id=lambda: str(getattr(window.current_world, "id", "")),
                date=window.timeline.get_playhead_time,
                format_date=lambda date: window.calendar_converter.format_date(date)
                if window.calendar_converter
                else f"lore day {date:g}",
                choose_object=lambda: widget._choose_map_object(
                    "Link Neighboring Region"
                ),
                create_entity=self.context_tags.create_entity_command,
                create_event=self.context_tags.create_event_command,
                submit=window.command_requested.emit,
                begin_drawing=widget._begin_region_drawing,
                set_date=window.timeline.set_playhead_time,
                transition=widget.request_edit_transition,
                reload_map=window.data_handler.reload_markers.emit,
                feedback=lambda message: window.status_bar.showMessage(message, 5000),
                pause_playback=lambda: window.timeline.toggle_playback()
                if window.timeline.view.is_playing()
                else None,
                refresh_source=self.refresh_neighbor_source,
            ),
            self,
        )
        self.time.playhead_guard = self.neighbor_regions.guard_playhead
        window.data_handler.markers_ready.connect(
            self.neighbor_regions.on_markers_ready
        )
        window.data_handler.feature_geometry_states_ready.connect(
            self.neighbor_regions.on_states_ready
        )
        window.worker.command_finished.connect(
            self.neighbor_regions.on_command_finished,
            Qt.ConnectionType.QueuedConnection,
        )

    def refresh_neighbor_source(self, map_id: str) -> None:
        """Reload saved input after a rejected neighbor creation without losing it."""
        for method in ("load_markers", "load_feature_geometry_states"):
            invoke_queued(self.main_window.worker, method, Q_ARG(str, map_id))

    def show_icon_library(self) -> None:
        """Open the active world's standalone icon manager."""
        if hasattr(self, "icon_library"):
            self.icon_library.show_manager(self.main_window)

    def bind_map_navigation(self) -> None:
        """Compose map navigation once its spatial view is available."""
        if not hasattr(self, "map_navigation"):
            from src.app.coordinators.map_navigation import MapNavigationController

            self.map_navigation = MapNavigationController(
                self.main_window.map_widget, self.navigation
            )

    def bind_date_navigation(self) -> None:
        """Compose selected-event time navigation after widget creation."""
        self.time.bind_date_navigation()
        self.authoring_context.bind_session()
        from PySide6.QtCore import Qt

        from src.app.coordinators.map_temporal_coordinator import MapTemporalCoordinator

        window = self.main_window
        self.map_temporal = MapTemporalCoordinator(
            lambda: self.data.cached_events,
            [
                window.map_widget.layer_panel.set_temporal_context,
                window.event_editor.set_temporal_context,
                window.entity_editor.set_temporal_context,
                window.timeline.view.set_temporal_context,
            ],
            self,
        )
        self.data.events_cache_changed.connect(self.map_temporal.refresh)
        window.worker.calendar_config_loaded.connect(
            self.map_temporal.set_calendar, Qt.ConnectionType.QueuedConnection
        )

    def bind_authoring_scope(self) -> None:
        """Compose the view scope and the temporary history presentation."""
        from src.app.coordinators.authoring_scope_coordinator import (
            AuthoringScopeCoordinator,
        )
        from src.app.coordinators.scoped_history import ScopedHistory

        window = self.main_window
        world_id = str(getattr(window.current_world, "id", "default"))
        self.scope = AuthoringScopeCoordinator(
            world_id, lambda: self.data.cached_tags, window
        )
        self.scoped_history = ScopedHistory(
            window.timeline, lambda: self.data.cached_events
        )
        self.data.bind_scoped_graph()
        window.status_bar.addPermanentWidget(self.scope.button)
        window.status_bar.addPermanentWidget(self.scope.outside_scope)
        self.data.scope_catalog_changed.connect(self._refresh_scope_catalog)
        self.data.events_cache_changed.connect(self.scoped_history.refresh)
        self.data.scope_items_changed.connect(self._refresh_scope_notice)
        self.data.scope_relations_ready.connect(self.scoped_history.relations)
        self.navigation.navigation_result.connect(self.scoped_history.selected)
        self.navigation.navigation_result.connect(self._refresh_scope_notice)
        window.data_handler.entity_state_resolved.connect(self.scoped_history.state)
        self.scope.changed.connect(self._apply_authoring_scope)
        self._apply_authoring_scope(self.scope.scope)

    def _refresh_scope_catalog(self) -> None:
        self.scope.tags_changed()
        self.context_tags.set_available_tags(self.data.cached_tags)

    def _apply_authoring_scope(self, scope: "AuthoringScope") -> None:
        window = self.main_window
        window.unified_list.set_authoring_scope(scope)
        self.scoped_history.scope_changed(scope)
        window.ai_search_manager.set_authoring_scope(scope)
        self.context_tags.set_scope_defaults(scope.creation_tags)
        self.data.on_graph_scope_changed(scope, self.scope.revision)
        self._refresh_scope_notice()

    def _refresh_scope_notice(self) -> None:
        identity = self.navigation.selected_id
        items = (
            self.data.cached_events
            if self.navigation.selected_type == "event"
            else self.data.cached_entities
        )
        item = next((item for item in items if item.id == identity), None)
        self.scope.show_outside_scope(
            item is not None and not self.scope.scope.matches(item.tags)
        )

    def bind_graph_authoring(self) -> None:
        """Compose direct graph authoring with the established command route."""
        from src.app.coordinators.graph_authoring import GraphAuthoring

        window = self.main_window
        self.graph_authoring = GraphAuthoring(
            window.graph_widget,
            self.data,
            self.scope,
            self.context_tags,
            window.command_coordinator,
            self.navigation,
            window.worker,
            lambda: str(getattr(window.current_world, "id", "")),
            window.timeline.get_playhead_time,
            lambda: window.calendar_converter,
        )
        self.event_timing.failed.connect(
            window.command_coordinator.on_graph_preflight_failure
        )

    def bind_event_timing(self) -> None:
        """Compose timing preparation after the command coordinator exists."""
        from PySide6.QtCore import Qt

        window = self.main_window
        from PySide6.QtWidgets import QApplication

        from src.app.coordinators.event_timing_coordinator import EventTimingCoordinator

        thread = window.worker_thread
        assert thread is not None
        self.event_timing = EventTimingCoordinator(
            window,
            thread,
            lambda: window.worker.db_service,
            lambda: str(window.db_path),
            window.command_coordinator.execute_command,
        )
        window.command_coordinator.defer_command = self.event_timing.intercept
        self.event_timing.failed.connect(self.editor.on_temporal_command_result)
        self.event_timing.resolution_prepared.connect(
            self.map_temporal.prime_resolution
        )
        self.event_timing.failed.connect(lambda _result: self.data.load_events())
        from src.app.coordinators.timeline_movement_coordinator import (
            TimelineMovementCoordinator,
        )

        self.timeline_movement = TimelineMovementCoordinator(
            window.timeline.view.movement,
            self.editor.command_requested.emit,
            self,
            lambda: str(window.db_path),
        )
        window.worker.initialized.connect(
            self.event_timing.cancel, Qt.ConnectionType.QueuedConnection
        )
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.event_timing.shutdown)
            application.aboutToQuit.connect(self.timeline_movement.shutdown)

    def bind_batch_metadata(self) -> None:
        """Compose Explorer batch edits after worker and command setup."""
        from PySide6.QtCore import Qt

        from src.app.coordinators.batch_metadata_coordinator import (
            BatchMetadataCoordinator,
        )

        window = self.main_window
        thread = window.worker_thread
        assert thread is not None
        self.batch_metadata = BatchMetadataCoordinator(
            window,
            thread,
            lambda: window.worker.db_service,
            lambda: str(window.db_path),
            window.unified_list.get_checked_items,
            self._batch_draft_warning,
            lambda: self.data.cached_tags,
            self.editor.command_requested.emit,
            self._refresh_batch_metadata,
            window.worker_manager._on_index_object_requested,
        )
        window.unified_list.batch_edit_requested.connect(self.batch_metadata.show)
        window.worker.command_finished.connect(
            self.batch_metadata.on_command_finished, Qt.ConnectionType.QueuedConnection
        )
        window.worker.initialized.connect(
            self.batch_metadata.cancel, Qt.ConnectionType.QueuedConnection
        )

    def _batch_draft_warning(self, targets: list) -> str:
        """Keep affected editor drafts and pending saves outside a batch."""
        window = self.main_window
        for kind, editor in (
            ("event", window.event_editor),
            ("entity", window.entity_editor),
        ):
            object_id = getattr(editor, f"current_{kind}_id")
            if (kind, object_id) in targets and (
                editor.has_unsaved_changes()
                or editor.save_pending
                or getattr(editor, "_temporal_save_pending", False)
                or getattr(editor, "_temporal_preparing", False)
            ):
                return (
                    f"Save or discard changes in the {kind.title()} Editor first "
                    "and wait for any pending save. Your draft and checks are retained."
                )
        return ""

    def _refresh_batch_metadata(self, effects: list) -> None:
        """Hydrate the affected clean inspector and refresh autocomplete data."""
        self.data.load_completer_data()
        kind = self.navigation.selected_type
        object_id = self.navigation.selected_id
        if not object_id:
            return
        if not any(
            effect["object_type"] == kind and effect["object_id"] == object_id
            for effect in effects
        ):
            return
        if self._batch_draft_warning([(kind, object_id)]):
            return
        if kind == "entity":
            self.data.load_entity_details(object_id)
        elif kind == "event":
            self.data.load_event_details(object_id)

    def bind_longform_navigation(self) -> None:
        """Compose Longform navigation once its view is available."""
        if not hasattr(self, "longform_navigation"):
            from src.app.coordinators.longform_navigation import (
                LongformNavigationController,
            )

            self.longform_navigation = LongformNavigationController(
                self.main_window.longform_editor, self.navigation
            )

    def bind_wiki_links(self) -> None:
        """Compose writing-link navigation with existing cache and guard inputs."""
        from src.app.coordinators.wiki_link_navigation import (
            WikiLinkNavigationController,
        )

        window = self.main_window
        self.wiki_links = WikiLinkNavigationController(
            {"event": window.event_editor, "entity": window.entity_editor},
            lambda: (self.navigation.selected_type, self.navigation.selected_id),
            lambda: str(getattr(window.current_world, "id", "") or ""),
            lambda: [
                (item.id, item.name, kind)
                for kind, collection in (
                    ("entity", self.data.cached_entities),
                    ("event", self.data.cached_events),
                )
                for item in collection
            ],
            self.navigation.set_global_selection,
            self.navigation.peek_target,
            lambda message: window.status_bar.showMessage(message, 5000),
            self,
        )
        self.navigation.navigation_result.connect(self.wiki_links.on_navigation_result)
        self.navigation.peek_started.connect(self.wiki_links.on_peek_started)
        self.navigation.peek_closed.connect(self.wiki_links.on_peek_closed)
        self.data.lore_mutation_applied.connect(self.wiki_links.refresh_return_label)
        self.data.editor_hydrated.connect(self.wiki_links.on_editor_hydrated)
        self.data.editor_hydration_failed.connect(
            self.wiki_links.on_editor_hydration_failed
        )

    def bind_icon_library(self) -> None:
        """Compose the icon feature using narrow command and view dependencies."""
        from PySide6.QtCore import Qt

        from src.app.coordinators.icon_library_coordinator import IconLibraryCoordinator

        window = self.main_window
        view = window.map_widget.view
        graph = window.graph_widget

        def context() -> tuple[str, str]:
            world = window.current_world
            if world is None:
                return ("", str(Path(window.db_path).resolve().parent))
            return (world.id, str(world.path))

        def refresh(payload: dict[str, Any]) -> None:
            view.apply_icon_library_snapshot(payload)
            graph.apply_icon_library_snapshot(payload)

        self.icon_library = IconLibraryCoordinator(
            window.command_coordinator.execute_command, context, refresh, self
        )
        view.icon_picker_created.connect(self.icon_library.attach_picker)
        graph.icon_picker_created.connect(self.icon_library.attach_picker)
        graph.lexicon_editor_created.connect(self.icon_library.attach_draft)
        window.command_coordinator.command_preparing.connect(
            self.icon_library.prepare_command
        )
        window.worker.command_finished.connect(
            self.icon_library.on_command_finished, Qt.ConnectionType.QueuedConnection
        )
        window.worker.initialized.connect(
            self.icon_library.on_initialized, Qt.ConnectionType.QueuedConnection
        )

    def bind_settings(self) -> None:
        """Compose settings after command infrastructure exists."""
        from src.app.settings_composition import compose_settings

        self.settings = compose_settings(self.main_window)
        from src.app.mcp_composition import compose_mcp

        self.mcp = compose_mcp(self.main_window, self.settings)
        from src.app.category_palette_composition import compose_category_palette

        self.category_palette = compose_category_palette(self.main_window)

    def validate_world(self, editorial_checks: bool = False) -> str:
        """Request world validation on the DatabaseWorker thread.

        The result is delivered asynchronously via the worker's
        ``validation_complete`` signal. Subscribe to that signal before
        calling this method to receive the
        :class:`~src.core.analysis.WorldValidationReport`.
        """
        job_id = str(uuid.uuid4())
        world = getattr(self.main_window, "current_world", None)
        world_id = str(getattr(world, "id", "") or "")
        invoke_queued(
            self.main_window.worker,
            "validate_world",
            Q_ARG(str, job_id),
            Q_ARG(str, world_id),
            Q_ARG(bool, editorial_checks),
        )
        return job_id

    def analyze_temporal(self) -> str:
        """Request temporal analysis on the DatabaseWorker thread.

        The result is delivered asynchronously via the worker's
        ``temporal_analysis_complete`` signal. Subscribe to that signal before
        calling this method to receive the
        :class:`~src.core.analysis.TemporalAnalysisReport`.
        """
        job_id = str(uuid.uuid4())
        world = getattr(self.main_window, "current_world", None)
        world_id = str(getattr(world, "id", "") or "")
        invoke_queued(
            self.main_window.worker,
            "analyze_temporal",
            Q_ARG(str, job_id),
            Q_ARG(str, world_id),
        )
        return job_id

    def run_intelligence_analysis(
        self,
        analysis_type: str = "all",
        options: dict[str, Any] | None = None,
    ) -> None:
        """Request non-blocking intelligence analysis from a world snapshot.

        The result is delivered asynchronously via the
        :class:`~src.app.intelligence_analysis_manager.IntelligenceAnalysisManager`.
        Subscribe to that manager before calling this method to receive the
        :class:`~src.core.analysis.IntelligenceReport`.

        Args:
            analysis_type: Scope of analysis — ``"all"``, ``"plot_holes"``,
                ``"relations"``, or ``"lore"``.  Defaults to ``"all"``.
        """
        self.main_window.intelligence_analysis_manager.start(analysis_type, options)

    def cancel_intelligence_analysis(self) -> None:
        """Request cooperative cancellation of the active AI analysis."""
        self.main_window.intelligence_analysis_manager.cancel()
