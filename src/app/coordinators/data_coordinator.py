"""Data Coordinator Module.

Manages data loading from the worker thread and signal handler dispatch
to UI widgets. Extracted from MainWindow to reduce its responsibilities.

Handles:
- Loading events, entities, and details from the worker thread
- Dispatching data-ready signals to UI widgets (list, timeline, map, graph)
- Graph data loading and debounced refresh
- Completer data updates for editor auto-completion
- Summary generation result routing
- Filter result handling
"""

import logging
from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import Q_ARG, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from src.app.constants import (
    SEMANTIC_COMPLETION_DEBOUNCE_MS,
    SEMANTIC_COMPLETION_ENABLE_EMBEDDING,
    SEMANTIC_COMPLETION_MIN_SCORE,
    SEMANTIC_COMPLETION_TOP_K,
)
from src.app.coordinators.base_coordinator import BaseCoordinator
from src.app.qt_invocation import invoke_queued

if TYPE_CHECKING:
    from src.app.main_window import MainWindow
    from src.core.entities import Entity
    from src.core.events import Event

logger = logging.getLogger(__name__)


class DataCoordinator(BaseCoordinator):
    """Coordinates data loading and signal dispatch between worker and UI.

    Manages cached data (events, entities) and routes data-ready signals
    from the DataHandler to the appropriate UI widgets.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the data coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(main_window)
        self._cached_events: list = []
        self._cached_entities: list = []
        self._cached_longform_sequence: list = []
        self._graph_reload_timer: Optional[QTimer] = None

        # Semantic completion debounce
        self._pending_semantic_prefix: str = ""
        self._semantic_debounce = QTimer(self)
        self._semantic_debounce.setSingleShot(True)
        self._semantic_debounce.setInterval(SEMANTIC_COMPLETION_DEBOUNCE_MS)
        self._semantic_debounce.timeout.connect(self._fire_semantic_query)

    # ------------------------------------------------------------------
    # Cached Data Properties
    # ------------------------------------------------------------------

    @property
    def cached_events(self) -> list:
        """Returns the cached list of events."""
        return self._cached_events

    @property
    def cached_entities(self) -> list:
        """Returns the cached list of entities."""
        return self._cached_entities

    @property
    def cached_longform_sequence(self) -> list:
        """Returns the cached longform sequence."""
        return self._cached_longform_sequence

    @cached_longform_sequence.setter
    def cached_longform_sequence(self, value: list) -> None:
        """Sets the cached longform sequence."""
        self._cached_longform_sequence = value

    # ------------------------------------------------------------------
    # Data Loading Methods (Worker Thread Communication)
    # ------------------------------------------------------------------

    def load_data(self) -> None:
        """Refreshes all data and active editors."""
        self.load_events()
        self.load_entities()
        self.main_window.longform_manager.load_longform_sequence()
        self.load_graph_data()
        self.load_completer_data()

        # Reload active editors to ensure they reflect current state
        if (
            hasattr(self.main_window.event_editor, "_current_event_id")
            and self.main_window.event_editor._current_event_id
        ):
            self.load_event_details(self.main_window.event_editor._current_event_id)

        if (
            hasattr(self.main_window.entity_editor, "_current_entity_id")
            and self.main_window.entity_editor._current_entity_id
        ):
            self.load_entity_details(self.main_window.entity_editor._current_entity_id)

    def load_events(self) -> None:
        """Requests loading of all events from the worker thread."""
        invoke_queued(
            self.main_window.worker,
            "load_events",
        )

    def load_entities(self) -> None:
        """Requests loading of all entities from the worker thread."""
        invoke_queued(
            self.main_window.worker,
            "load_entities",
        )

    def load_event_details(self, event_id: str) -> None:
        """Requests loading details for a specific event.

        Args:
            event_id: The ID of the event to load.

        """
        invoke_queued(
            self.main_window.worker,
            "load_event_details",
            Q_ARG(str, event_id),
        )

    def load_entity_details(self, entity_id: str) -> None:
        """Requests loading details for a specific entity.

        Args:
            entity_id: The ID of the entity to load.

        """
        invoke_queued(
            self.main_window.worker,
            "load_entity_details",
            Q_ARG(str, entity_id),
        )

    def load_completer_data(self) -> None:
        """Requests loading of completer data from the worker thread."""
        invoke_queued(
            self.main_window.worker,
            "load_completer_data",
        )

    def load_graph_data(self, filter_config: Optional[dict] = None) -> None:
        """Requests loading of graph data, optionally filtered.

        Args:
            filter_config: Optional dictionary with 'tags' and 'rel_types'.
                           If not provided, uses current widget config.

        """
        if filter_config is None and self.main_window.graph_widget:
            filter_config = self.main_window.graph_widget.get_filter_config()

        tags = filter_config.get("tags") if filter_config else None
        rel_types = filter_config.get("rel_types") if filter_config else None

        self.main_window.load_graph_data_requested.emit(tags, rel_types)

    # ------------------------------------------------------------------
    # Signal Handlers (Data Ready)
    # ------------------------------------------------------------------

    @Slot(list)
    def on_events_ready(self, events: list) -> None:
        """Handle events ready signal from DataHandler.

        Args:
            events: List of Event objects.

        """
        self._cached_events = events
        logger.info(f"on_events_ready received {len(events)} events")
        self.main_window.unified_list.set_data(
            self._cached_events, self._cached_entities
        )
        self.main_window.timeline.set_events(events)
        self.main_window.map_widget.set_cached_items(
            self._cached_entities, self._cached_events
        )

        self._schedule_graph_refresh()

    @Slot(list)
    def on_entities_ready(self, entities: list) -> None:
        """Handle entities ready signal from DataHandler.

        Args:
            entities: List of Entity objects.

        """
        self._cached_entities = entities
        self.main_window.unified_list.set_data(
            self._cached_events, self._cached_entities
        )
        self.main_window.map_widget.set_cached_items(
            self._cached_entities, self._cached_events
        )

        self._schedule_graph_refresh()

    @Slot(list)
    def on_suggestions_update(self, items: list) -> None:
        """Handle suggestions update request from DataHandler.

        Args:
            items: List of (id, name, type) tuples for completion.

        """
        self.main_window.event_editor.update_suggestions(items=items)
        self.main_window.entity_editor.update_suggestions(items=items)

    @Slot(object, list, list)
    def on_event_details_ready(
        self, event: object, relations: list, incoming: list
    ) -> None:
        """Handle event details ready signal from DataHandler.

        Args:
            event: The Event object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.

        """
        map_widget = getattr(self.main_window, "map_widget", None)
        maps_data = map_widget.maps_data if map_widget is not None else []
        self.main_window.event_editor.load_event(
            cast("Event | None", event), relations, incoming, maps_data=maps_data
        )

    @Slot(object, list, list)
    def on_entity_details_ready(
        self, entity: object, relations: list, incoming: list
    ) -> None:
        """Handle entity details ready signal from DataHandler.

        Args:
            entity: The Entity object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.

        """
        map_widget = getattr(self.main_window, "map_widget", None)
        maps_data = map_widget.maps_data if map_widget is not None else []
        self.main_window.entity_editor.load_entity(
            cast("Entity | None", entity), relations, incoming, maps_data=maps_data
        )

    @Slot(list, list)
    def on_graph_data_ready(self, nodes: list, edges: list) -> None:
        """Updates the graph widget with loaded data.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.

        """
        if self.main_window.graph_widget:
            focus_id = self.main_window.navigation_coordinator.selected_id
            self.main_window.graph_widget.display_graph(
                nodes, edges, focus_node_id=focus_id
            )

    @Slot(list, list)
    def on_graph_metadata_ready(self, tags: list, rel_types: list) -> None:
        """Updates the graph widget with available metadata.

        Args:
            tags: List of available tags.
            rel_types: List of available relation types.

        """
        if self.main_window.graph_widget:
            self.main_window.graph_widget.set_available_tags(tags)
            self.main_window.graph_widget.set_available_relation_types(rel_types)

    @Slot(dict, dict)
    def on_graph_lexicon_ready(self, raw_lexicon: dict, resolved_lexicon: dict) -> None:
        """Updates the graph widget with the visual lexicon configuration.

        Also sets the available entity types and world assets directory
        for the lexicon editor dialog.

        Args:
            raw_lexicon: Raw lexicon config with file paths.
            resolved_lexicon: Resolved lexicon config with Base64 URIs.

        """
        if self.main_window.graph_widget:
            self.main_window.graph_widget.set_lexicon_config(
                raw_lexicon, resolved_lexicon
            )
            # Set entity types from the raw lexicon's node keys + any from
            # completer data (entity_types come from graph_metadata_loaded)
            from src.services.graph_data_service import GraphDataService

            try:
                # Use gui_db_service which is initialized on MainWindow
                db = self.main_window.gui_db_service
                if db:
                    service = GraphDataService()
                    entity_types = service.get_all_entity_types(db)
                    self.main_window.graph_widget.set_available_entity_types(
                        entity_types
                    )
            except Exception:
                logger.debug(
                    "Could not load entity types for lexicon editor",
                    exc_info=True,
                )

            # Set world assets dir from DB path
            try:
                from pathlib import Path

                # Use gui_db_service
                db = self.main_window.gui_db_service
                if db and db.db_path != ":memory:":
                    assets_dir = str(Path(db.db_path).parent / "assets")
                    self.main_window.graph_widget.set_world_assets_dir(assets_dir)
            except Exception:
                logger.debug(
                    "Could not resolve world assets directory",
                    exc_info=True,
                )

    @Slot(list, list)
    def on_filter_results_ready(self, events: list, entities: list) -> None:
        """Handler for filter results.

        Updates the Unified List with filtered data.

        Args:
            events: Filtered list of events.
            entities: Filtered list of entities.

        """
        self.main_window.unified_list.set_data(events, entities)
        count = len(events) + len(entities)
        self.main_window.status_bar.showMessage(f"Filter applied. Found {count} items.")

    @Slot(str)
    def on_dock_raise_requested(self, dock_name: str) -> None:
        """Handle dock raise request from DataHandler.

        Args:
            dock_name: Name of the dock to raise ("event", "entity", etc).

        """
        ui_manager = getattr(self.main_window, "ui_manager")
        if dock_name in ui_manager.docks:
            ui_manager.docks[dock_name].raise_()

    @Slot(str, str)
    def on_selection_requested(self, item_type: str, item_id: str) -> None:
        """Handle selection request from DataHandler.

        Args:
            item_type: Type of item ("event" or "entity").
            item_id: ID of the item to select.

        """
        self.main_window.unified_list.select_item(item_type, item_id)

    @Slot(str)
    def on_command_failed(self, message: str) -> None:
        """Handle command failure notification from DataHandler.

        Args:
            message: Error message from the failed command.

        """
        QMessageBox.warning(self.main_window, "Command Failed", message)

    @Slot()
    def on_reload_active_editor_relations(self) -> None:
        """Reload relations for whichever editor is currently active.

        This is called after relation or wiki link commands complete.
        """
        logger.debug(
            f"on_reload_active_editor_relations: "
            f"event_id={self.main_window.event_editor._current_event_id}, "
            f"entity_id={self.main_window.entity_editor._current_entity_id}, "
            f"active_type="
            f"{self.main_window.navigation_coordinator.selected_type}"
        )

        if (
            self.main_window.navigation_coordinator.selected_type == "event"
            and self.main_window.event_editor._current_event_id
        ):
            logger.debug("Reloading active event details")
            self.load_event_details(self.main_window.event_editor._current_event_id)

        elif (
            self.main_window.navigation_coordinator.selected_type == "entity"
            and self.main_window.entity_editor._current_entity_id
        ):
            logger.debug("Reloading active entity details")
            self.load_entity_details(self.main_window.entity_editor._current_entity_id)

    def on_completer_data_loaded(
        self,
        tags: list[str],
        rel_types: list[str],
        attr_keys: list[str],
        entity_types: list[str],
    ) -> None:
        """Handler for completer data loaded from worker.

        Updates suggestions in both Entity and Event editors.

        Args:
            tags: List of available tags.
            rel_types: List of available relation types.
            attr_keys: List of available attribute keys.
            entity_types: List of available entity types.

        """
        self.main_window.entity_editor.update_tag_suggestions(tags)
        self.main_window.entity_editor.update_attribute_suggestions(attr_keys)
        self.main_window.entity_editor.update_relation_type_suggestions(rel_types)
        self.main_window.entity_editor.update_entity_type_suggestions(entity_types)

        self.main_window.event_editor.update_tag_suggestions(tags)
        self.main_window.event_editor.update_attribute_suggestions(attr_keys)
        self.main_window.event_editor.update_relation_type_suggestions(rel_types)

    @Slot(str, object)
    def on_summary_generated_result(self, item_id: str, summary_data: object) -> None:
        """Handles asynchronous summary generation result.

        Routes the generated summary to the correct editor.

        Args:
            item_id: The ID of the item the summary is for.
            summary_data: The generated SummaryData object.

        """
        if self.main_window.entity_editor._current_entity_id == item_id:
            self.main_window.entity_editor.on_summary_generated(summary_data)
            return

        if self.main_window.event_editor._current_event_id == item_id:
            self.main_window.event_editor.on_summary_generated(summary_data)
            return

        logger.warning(
            f"Summary generated for {item_id}, but item is no longer active in editor."
        )

    @Slot(str)
    def on_summary_generation_failed(self, item_id: str) -> None:
        """Handles summary generation failure.

        Routes the failure event to the correct editor to reset the UI state.

        Args:
            item_id: The ID of the item the summary generation failed for.

        """
        if self.main_window.entity_editor._current_entity_id == item_id:
            self.main_window.entity_editor.on_summary_generation_failed()
            return

        if self.main_window.event_editor._current_event_id == item_id:
            self.main_window.event_editor.on_summary_generation_failed()
            return

        logger.warning(
            f"Summary generation failed for {item_id}, but item is no longer active in editor."
        )

    # ------------------------------------------------------------------
    # Semantic Completion
    # ------------------------------------------------------------------

    def request_semantic_completions(self, prefix: str) -> None:
        """Request semantic suggestions for a wiki-link prefix (debounced).

        Restarts the debounce timer so only the last prefix typed in a
        burst is actually sent to the worker thread.

        Args:
            prefix: The typed text after ``[[``.

        """
        if not SEMANTIC_COMPLETION_ENABLE_EMBEDDING:
            return
        self._pending_semantic_prefix = prefix
        self._semantic_debounce.start()

    def _fire_semantic_query(self) -> None:
        """Send the pending prefix to the worker (called by debounce timer)."""
        if not SEMANTIC_COMPLETION_ENABLE_EMBEDDING:
            return
        prefix = self._pending_semantic_prefix
        if not prefix:
            return
        invoke_queued(
            self.main_window.worker,
            "query_semantic_suggestions",
            Q_ARG(str, prefix),
            Q_ARG(int, SEMANTIC_COMPLETION_TOP_K),
            Q_ARG(float, SEMANTIC_COMPLETION_MIN_SCORE),
        )

    @Slot(str, list)
    def on_semantic_suggestions(self, prefix: str, names: list) -> None:
        """Handle semantic suggestions from the worker and route to the active editor.

        Args:
            prefix: The original query prefix.
            names: Suggested display names filtered by similarity score.

        """
        if not names:
            return
        active = self.main_window.navigation_coordinator.selected_type
        if active == "event":
            self.main_window.event_editor.merge_wiki_completions(names)
        elif active == "entity":
            self.main_window.entity_editor.merge_wiki_completions(names)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _schedule_graph_refresh(self) -> None:
        """Schedules a debounced graph refresh to avoid double-loading."""
        if self._graph_reload_timer is None:
            self._graph_reload_timer = QTimer(self)
            self._graph_reload_timer.setSingleShot(True)
            self._graph_reload_timer.timeout.connect(self.load_graph_data)
        self._graph_reload_timer.start(100)  # 100ms debounce

    def stop_graph_reload_timer(self) -> None:
        """Stops the graph reload timer. Called during shutdown."""
        if self._graph_reload_timer is not None:
            self._graph_reload_timer.stop()

    def stop_semantic_debounce_timer(self) -> None:
        """Stops the semantic debounce timer. Called during shutdown."""
        self._semantic_debounce.stop()
