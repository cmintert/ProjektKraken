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
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from src.app.coordinators.base_coordinator import BaseCoordinator

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

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
            self.load_event_details(
                self.main_window.event_editor._current_event_id
            )

        if (
            hasattr(self.main_window.entity_editor, "_current_entity_id")
            and self.main_window.entity_editor._current_entity_id
        ):
            self.load_entity_details(
                self.main_window.entity_editor._current_entity_id
            )

    def load_events(self) -> None:
        """Requests loading of all events from the worker thread."""
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_events",
            Qt.ConnectionType.QueuedConnection,
        )

    def load_entities(self) -> None:
        """Requests loading of all entities from the worker thread."""
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_entities",
            Qt.ConnectionType.QueuedConnection,
        )

    def load_event_details(self, event_id: str) -> None:
        """Requests loading details for a specific event.

        Args:
            event_id: The ID of the event to load.

        """
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_event_details",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, event_id),
        )

    def load_entity_details(self, entity_id: str) -> None:
        """Requests loading details for a specific entity.

        Args:
            entity_id: The ID of the entity to load.

        """
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_entity_details",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, entity_id),
        )

    def load_completer_data(self) -> None:
        """Requests loading of completer data from the worker thread."""
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_completer_data",
            Qt.ConnectionType.QueuedConnection,
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
        self.main_window.event_editor.load_event(event, relations, incoming)

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
        self.main_window.entity_editor.load_entity(entity, relations, incoming)

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
    def on_graph_metadata_ready(
        self, tags: list, rel_types: list
    ) -> None:
        """Updates the graph widget with available metadata.

        Args:
            tags: List of available tags.
            rel_types: List of available relation types.

        """
        if self.main_window.graph_widget:
            self.main_window.graph_widget.set_available_tags(tags)
            self.main_window.graph_widget.set_available_relation_types(
                rel_types
            )

    @Slot(dict, dict)
    def on_graph_lexicon_ready(
        self, raw_lexicon: dict, resolved_lexicon: dict
    ) -> None:
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
                db = self.main_window.worker_manager.db_service
                if db:
                    service = GraphDataService()
                    entity_types = service.get_all_entity_types(db)
                    self.main_window.graph_widget.set_available_entity_types(
                        entity_types
                    )
            except Exception:
                pass  # Non-critical, editor will show no types

            # Set world assets dir from DB path
            try:
                from pathlib import Path

                db = self.main_window.worker_manager.db_service
                if db and db.db_path != ":memory:":
                    assets_dir = str(Path(db.db_path).parent / "assets")
                    self.main_window.graph_widget.set_world_assets_dir(
                        assets_dir
                    )
            except Exception:
                pass  # Non-critical

    @Slot(list, list)
    def on_filter_results_ready(
        self, events: list, entities: list
    ) -> None:
        """Handler for filter results.

        Updates the Unified List with filtered data.

        Args:
            events: Filtered list of events.
            entities: Filtered list of entities.

        """
        self.main_window.unified_list.set_data(events, entities)
        count = len(events) + len(entities)
        self.main_window.status_bar.showMessage(
            f"Filter applied. Found {count} items."
        )

    @Slot(str)
    def on_dock_raise_requested(self, dock_name: str) -> None:
        """Handle dock raise request from DataHandler.

        Args:
            dock_name: Name of the dock to raise ("event", "entity", etc).

        """
        if dock_name in self.main_window.ui_manager.docks:
            self.main_window.ui_manager.docks[dock_name].raise_()

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
            self.load_event_details(
                self.main_window.event_editor._current_event_id
            )

        elif (
            self.main_window.navigation_coordinator.selected_type == "entity"
            and self.main_window.entity_editor._current_entity_id
        ):
            logger.debug("Reloading active entity details")
            self.load_entity_details(
                self.main_window.entity_editor._current_entity_id
            )

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
        self.main_window.entity_editor.update_relation_type_suggestions(
            rel_types
        )
        self.main_window.entity_editor.update_entity_type_suggestions(
            entity_types
        )

        self.main_window.event_editor.update_tag_suggestions(tags)
        self.main_window.event_editor.update_attribute_suggestions(attr_keys)
        self.main_window.event_editor.update_relation_type_suggestions(
            rel_types
        )

    @Slot(str, object)
    def on_summary_generated_result(
        self, item_id: str, summary_data: object
    ) -> None:
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
            f"Summary generated for {item_id}, but item is no longer "
            f"active in editor."
        )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _schedule_graph_refresh(self) -> None:
        """Schedules a debounced graph refresh to avoid double-loading."""
        if self._graph_reload_timer is None:
            self._graph_reload_timer = QTimer()
            self._graph_reload_timer.setSingleShot(True)
            self._graph_reload_timer.timeout.connect(self.load_graph_data)
        self._graph_reload_timer.start(100)  # 100ms debounce

    def stop_graph_reload_timer(self) -> None:
        """Stops the graph reload timer. Called during shutdown."""
        if self._graph_reload_timer is not None:
            self._graph_reload_timer.stop()
