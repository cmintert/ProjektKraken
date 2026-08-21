"""Tests for Event authoring-context request orchestration."""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject

from src.app.coordinators.authoring_context_coordinator import (
    AuthoringContextCoordinator,
)
from src.core.authoring_context import EntityAuthoringContext, EventAuthoringContext
from src.services.worker import DatabaseWorker


class _TemporalWidget:
    def __init__(self, date: float) -> None:
        self.date = date

    def get_start(self) -> float:
        return self.date


class _Editor:
    def __init__(self) -> None:
        self.current_event_id = "event-id"
        self.temporal_widget = _TemporalWidget(10.0)
        self.set_authoring_context_loading = MagicMock()
        self.clear_authoring_context = MagicMock()
        self.set_authoring_context_unavailable = MagicMock()
        self.set_authoring_context = MagicMock()


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.event_editor = _Editor()
        self.entity_editor = MagicMock()
        self.entity_editor.current_entity_id = "entity-id"
        self.worker = QObject()
        self.map_widget = MagicMock()
        self.map_widget.get_selected_map_id.return_value = "map-id"


def test_date_refresh_is_debounced_and_captures_draft_inputs(qtbot) -> None:
    window = _Window()
    coordinator = AuthoringContextCoordinator(window)  # type: ignore[arg-type]

    with patch(
        "src.app.coordinators.authoring_context_coordinator.invoke_queued"
    ) as invoke, patch(
        "src.app.coordinators.authoring_context_coordinator.Q_ARG",
        side_effect=lambda _type, value: value,
    ):
        coordinator.schedule_refresh()
        coordinator.schedule_refresh()
        window.event_editor.temporal_widget.date = 12.0
        coordinator.schedule_refresh()
        qtbot.wait(300)

    assert invoke.call_count == 1
    args = invoke.call_args.args
    assert args[0] is window.worker
    assert args[1] == "load_event_authoring_context"
    assert args[3] == "event-id"
    assert args[4] == 12.0
    assert args[5] == "map-id"


def test_stale_result_cannot_replace_newer_context(qapp) -> None:
    window = _Window()
    coordinator = AuthoringContextCoordinator(window)  # type: ignore[arg-type]
    coordinator._active_request_id = "new-request"
    snapshot = EventAuthoringContext("event-id", 10.0).to_dict()

    coordinator.on_context_loaded(
        "old-request", "event-id", 10.0, "map-id", snapshot
    )

    window.event_editor.set_authoring_context.assert_not_called()


def test_matching_serialized_snapshot_is_rendered(qapp) -> None:
    window = _Window()
    coordinator = AuthoringContextCoordinator(window)  # type: ignore[arg-type]
    coordinator._active_request_id = "request-id"
    snapshot = EventAuthoringContext("event-id", 10.0).to_dict()

    coordinator.on_context_loaded(
        "request-id", "event-id", 10.0, "map-id", snapshot
    )

    rendered = window.event_editor.set_authoring_context.call_args.args[0]
    assert isinstance(rendered, EventAuthoringContext)
    assert rendered.event_id == "event-id"


def test_database_worker_emits_only_serialized_snapshot(qtbot) -> None:
    worker = DatabaseWorker("C:/world/world.kraken")
    worker.db_service = MagicMock()
    context = EventAuthoringContext("event-id", 10.0)

    with patch(
        "src.services.authoring_context_builder.AuthoringContextBuilder"
    ) as builder_type:
        builder_type.return_value.build_event_context.return_value = context
        with qtbot.waitSignal(worker.authoring_context_loaded) as signal:
            worker.load_event_authoring_context(
                "request-id", "event-id", 10.0, "map-id"
            )

    assert signal.args[:4] == ["request-id", "event-id", 10.0, "map-id"]
    assert signal.args[4] == context.to_dict()
    assert isinstance(signal.args[4], dict)


def test_entity_refresh_is_debounced_and_serialized(qtbot) -> None:
    window = _Window()
    coordinator = AuthoringContextCoordinator(window)  # type: ignore[arg-type]

    with patch(
        "src.app.coordinators.authoring_context_coordinator.invoke_queued"
    ) as invoke, patch(
        "src.app.coordinators.authoring_context_coordinator.Q_ARG",
        side_effect=lambda _type, value: value,
    ):
        coordinator.schedule_entity_refresh()
        coordinator.schedule_entity_refresh()
        qtbot.wait(300)

    assert invoke.call_count == 1
    assert invoke.call_args.args[1:] == (
        "load_entity_authoring_context",
        invoke.call_args.args[2],
        "entity-id",
    )


def test_stale_entity_result_cannot_replace_newer_context(qapp) -> None:
    window = _Window()
    coordinator = AuthoringContextCoordinator(window)  # type: ignore[arg-type]
    coordinator._active_entity_request_id = "new-request"
    snapshot = EntityAuthoringContext("entity-id").to_dict()

    coordinator.on_entity_context_loaded("old-request", "entity-id", snapshot)

    window.entity_editor.set_authoring_context.assert_not_called()


def test_database_worker_emits_serialized_entity_snapshot(qtbot) -> None:
    worker = DatabaseWorker("C:/world/world.kraken")
    worker.db_service = MagicMock()
    context = EntityAuthoringContext("entity-id")

    with patch(
        "src.services.authoring_context_builder.AuthoringContextBuilder"
    ) as builder_type:
        builder_type.return_value.build_entity_context.return_value = context
        with qtbot.waitSignal(worker.entity_authoring_context_loaded) as signal:
            worker.load_entity_authoring_context("request-id", "entity-id")

    assert signal.args == ["request-id", "entity-id", context.to_dict()]
    assert isinstance(signal.args[2], dict)
