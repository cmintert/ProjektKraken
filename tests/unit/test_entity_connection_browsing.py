"""Complete direct discovery, temporal admission and revision-safe paging."""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from src.app.coordinators.entity_connection_browse_coordinator import (
    EntityConnectionBrowseCoordinator,
)
from src.commands.relation_commands import AddRelationCommand
from src.core.ai_generation import GenerationRequest, PreparedGeneration
from src.core.authoring_context import EntityAuthoringContext
from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.gui.widgets.llm_generation_widget import GenerationWorker
from src.services.authoring_context_builder import (
    AuthoringContextBuilder,
    format_entity_authoring_context,
)
from src.services.db_service import DatabaseService
from src.services.entity_connection_browse_service import (
    EntityConnectionBrowseService,
    StaleConnectionCursor,
)
from src.services.entity_connection_browse_task import EntityConnectionBrowseTask
from src.services.entity_context_reader import read_entity_context_snapshot

pytestmark = pytest.mark.ci_fast


def query(root, mode="all_history", date=None):
    return {
        "entity_id": root,
        "mode": mode,
        "date": date,
        "world": "test",
        "session": "session",
        "generation": 0,
    }


def collect(service, inputs):
    rows, responses = [], []
    cursor = None
    for _ in range(100):
        response = service.step({"query": inputs, "cursor": cursor})
        rows.extend(response["rows"])
        responses.append(response)
        cursor = response["cursor"]
        if response["done"]:
            return rows, responses
    pytest.fail("Candidate scan did not finish")


@pytest.mark.parametrize(
    "mode,date",
    [("all_history", None), ("at_playhead", 20.0), ("history_to_playhead", 20.0)],
)
def test_reconstructs_every_eligible_canonical_link(db_service, mode, date):
    root = Entity("Root", "character", attributes={"secret": "not evidence"})
    db_service.insert_entity(root)
    expected = set()
    for index in range(83):
        other = Entity(["Straße", "STRASSE", "Café", "Cafe\u0301"][index % 4], "place")
        db_service.insert_entity(other)
        source, target = (root.id, other.id) if index % 2 else (other.id, root.id)
        attrs = {"valid_from": 1.0, "valid_to": 30.0, "_private": "never expose"}
        expected.add(
            db_service.insert_relation(source, target, f"custom {index % 7}", attrs)
        )
    expected.add(db_service.insert_relation(root.id, root.id, "self", {}))
    service = EntityConnectionBrowseService(db_service)
    rows, responses = collect(service, query(root.id, mode, date))
    assert {row["id"] for row in rows} == expected
    assert len(rows) == len(expected)
    assert all(len(response["rows"]) <= 25 for response in responses)
    assert all(response["eligible_total"] is None for response in responses[:-1])
    assert responses[-1]["eligible_total"] == len(expected)
    assert "never expose" not in json.dumps(rows)
    assert "not evidence" not in json.dumps(rows)
    oracle = sorted(
        rows,
        key=lambda row: (
            row["source"]["name"].casefold(),
            row["rel_type"].casefold(),
            row["target"]["name"].casefold(),
            row["id"],
        ),
    )
    assert rows == oracle
    assert collect(service, query(root.id, mode, date))[0] == rows


def test_excluded_batches_do_not_claim_exhaustion(db_service):
    root, other = Entity("A", "person"), Entity("B", "place")
    for item in (root, other):
        db_service.insert_entity(item)
    for index in range(125):
        db_service.insert_relation(
            root.id, other.id, f"a future {index:03}", {"valid_from": 100.0}
        )
    last = db_service.insert_relation(root.id, other.id, "z eligible", {})
    rows, responses = collect(
        EntityConnectionBrowseService(db_service), query(root.id, "at_playhead", 20.0)
    )
    assert responses[0]["rows"] == []
    assert not responses[0]["done"]
    assert responses[0]["eligible_total"] is None
    assert [row["id"] for row in rows] == [last]
    assert responses[-1]["cursor"]["excluded"] == 125


def test_event_links_keep_custom_predicates_and_occurrence_policy(db_service):
    root = Entity("Person", "person")
    event = Event("Future gathering", 100.0)
    db_service.insert_entity(root)
    db_service.insert_event(event)
    custom = db_service.insert_relation(event.id, root.id, "witnessed", {})
    reverse = db_service.insert_relation(root.id, event.id, "involved", {})
    role = db_service.insert_relation(event.id, root.id, "involved", {})
    db_service.reconcile_mentions(
        event.id,
        "description",
        {
            root.id: [
                {
                    "field": "description",
                    "start_offset": 0,
                    "end_offset": 4,
                    "snippet": "Root",
                }
            ]
        },
    )
    reference = next(
        row["id"]
        for row in db_service.get_relations(event.id)
        if row["rel_type"] == "mentions"
    )
    service = EntityConnectionBrowseService(db_service)
    rows, _ = collect(service, query(root.id, "history_to_playhead", 20.0))
    assert {row["id"] for row in rows} == {custom, reverse}
    all_rows, _ = collect(service, query(root.id))
    assert {row["id"] for row in all_rows} == {custom, reverse, role, reference}


@pytest.mark.parametrize("change", ["own", "query", "policy"])
def test_cursor_restarts_after_revision_or_query_change(db_service, change):
    root = Entity("Root", "person")
    db_service.insert_entity(root)
    service = EntityConnectionBrowseService(db_service)
    inputs = query(root.id)
    cursor = service.step({"query": inputs})["cursor"]
    if change == "own":
        db_service.insert_entity(Entity("New", "place"))
    elif change == "query":
        inputs = inputs | {"mode": "at_playhead", "date": 3.0}
    else:
        cursor["binding"]["policy"] = "obsolete"
    with pytest.raises(StaleConnectionCursor):
        service.step({"query": inputs, "cursor": cursor})


def test_external_commit_invalidates_same_connection_cursor(tmp_path):
    database = DatabaseService(str(tmp_path / "external.kraken"))
    database.connect()
    try:
        root = Entity("Root", "person")
        database.insert_entity(root)
        service = EntityConnectionBrowseService(database)
        cursor = service.step({"query": query(root.id)})["cursor"]
        with sqlite3.connect(database.db_path) as external:
            external.execute(
                "UPDATE entities SET name = 'Changed' WHERE id = ?", (root.id,)
            )
        with pytest.raises(StaleConnectionCursor):
            service.step({"query": query(root.id), "cursor": cursor})
    finally:
        database.close()


def test_missing_endpoint_is_partial_not_complete(db_service, monkeypatch):
    root = Entity("Root", "person")
    db_service.insert_entity(root)
    db_service.insert_relation(root.id, root.id, "knows", {})
    service = EntityConnectionBrowseService(db_service)
    rows = service.repository.candidates(root.id, None, 100)
    rows[0]["target_kind"] = None
    monkeypatch.setattr(service.repository, "candidates", lambda *_args: rows)
    _, responses = collect(service, query(root.id))
    assert responses[-1]["done"]
    assert responses[-1]["eligible_total"] is None
    assert responses[-1]["cursor"]["unreadable"] == 1


def test_human_description_sidecar_excludes_attributes_before_budget(db_service, qtbot):
    root = Entity("Root", "person", attributes={f"stat {i}": i for i in range(60)})
    root.attributes["Description"] = "attribute masquerading as prose"
    db_service.insert_entity(root)
    event = Event("Unknown change", 10.0)
    db_service.insert_event(event)
    db_service.insert_relation(
        event.id,
        root.id,
        "changes_state",
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {"status": "unknown"},
                "end": {"status": "open"},
            },
            "payload": {
                "attributes": {f"stat {i}": i + 1 for i in range(60)},
                "description": "The city may be abandoned.",
            },
        },
    )
    builder = AuthoringContextBuilder(db_service)
    before = builder.build_entity_context(
        root.id, mode="at_playhead", context_date=20.0
    )
    prompt = format_entity_authoring_context(before)
    snapshot = read_entity_context_snapshot(
        db_service, db_service.db_path, root.id, "at_playhead", 20.0
    )
    assert (
        snapshot["human_description_changes"]["rows"][0]["value"]
        == "The city may be abandoned."
    )
    widget = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(widget)
    widget.set_description_changes(snapshot["human_description_changes"])
    widget.set_entity_context(EntityAuthoringContext.from_dict(snapshot))
    text = " ".join(
        section.browser.toPlainText() for section in widget.sections.values()
    )
    assert "abandoned" in text
    assert "stat 0" not in text
    assert "attribute masquerading" not in text
    assert "Attributes" not in widget.sections
    assert "additional attributes" not in text
    after = AuthoringContextBuilder(db_service).build_entity_context(
        root.id, mode="at_playhead", context_date=20.0
    )
    assert before.to_dict() == after.to_dict()
    assert prompt == format_entity_authoring_context(after)


def test_stale_response_cannot_append_or_continue(qtbot):
    view = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(view)
    view.enable_connection_browsing()
    inputs = query("first")
    coordinator = EntityConnectionBrowseCoordinator(view, lambda: inputs)
    requests = []
    coordinator.requested.connect(requests.append)
    coordinator.restart()
    old = requests[-1]["request_id"]
    coordinator.invalidate()
    coordinator.accept({"request_id": old, "kind": "page", "rows": [{"bad": "data"}]})
    assert len(requests) == 1
    coordinator.stop()


def test_browse_controls_preserve_focus_and_frozen_generation(db_service, qtbot):
    root, other = Entity("Root", "person"), Entity("Other", "place")
    for item in (root, other):
        db_service.insert_entity(item)
    for index in range(57):
        db_service.insert_relation(root.id, other.id, f"custom {index:02}", {})
    service = EntityConnectionBrowseService(db_service)
    view = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(view)
    view.enable_connection_browsing()
    view.set_entity_context(EntityAuthoringContext(root.id))
    view.resize(360, 300)
    view.show()
    coordinator = EntityConnectionBrowseCoordinator(view, lambda: query(root.id))
    coordinator.requested.connect(
        lambda request: coordinator.accept(
            {
                **service.step(request),
                "request_id": request["request_id"],
                "kind": "page",
            }
        )
    )
    frozen = PreparedGeneration(
        {"system": "unchanged", "user": "Selected attributes: strength=12"},
        "Bounded original context",
        "",
        "",
        (),
    )
    request = GenerationRequest({"system": "ignore", "user": "ignore"}, prepared=frozen)
    original_bytes = json.dumps(request.to_dict(), ensure_ascii=False).encode("utf-8")
    coordinator.restart()
    section = view.sections["Saved direct connections"]
    assert "25 loaded; total not yet known" in view.connection_status.text()
    assert len(section.visible_rows()) == 3
    section.disclosure.setChecked(True)
    view.activateWindow()
    qtbot.wait(10)
    view.load_connections.setFocus()
    assert view.load_connections.hasFocus()
    coordinator.load_more()
    assert view.load_connections.hasFocus()
    assert view.sections["Saved direct connections"] is section
    assert len(section.visible_rows()) == 50
    coordinator.load_more()
    assert "57 loaded; all eligible connections loaded" in view.connection_status.text()
    assert not view.load_connections.isEnabled()
    view.more_button.setChecked(False)
    assert len(section.visible_rows()) == 3
    assert (
        json.dumps(request.to_dict(), ensure_ascii=False).encode("utf-8")
        == original_bytes
    )
    worker = GenerationWorker(MagicMock(), "ignored", 100, 0.1, request=request)
    with patch.object(worker, "_apply_authoring_context_to_prompt") as lookup:
        worker.prepare_context()
    lookup.assert_not_called()
    assert worker.prompt == frozen.prompt
    coordinator.stop()


def test_date_uncertainty_retains_edge_evidence(db_service):
    root, other = Entity("Root", "person"), Entity("Other", "place")
    for item in (root, other):
        db_service.insert_entity(item)
    identifier = db_service.insert_relation(
        root.id,
        other.id,
        "custom uncertain",
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {"status": "unknown", "_private": "hidden"},
                "end": {"status": "open"},
            }
        },
    )
    rows, _ = collect(
        EntityConnectionBrowseService(db_service), query(root.id, "at_playhead", 20.0)
    )
    assert rows[0]["id"] == identifier
    assert rows[0]["temporal_status"] == "indeterminate"
    assert rows[0]["temporal_evidence"]["authored_boundaries"]["start"] == {
        "status": "unknown"
    }
    assert "hidden" not in json.dumps(rows)


def test_undo_and_redo_invalidate_page_sequences(db_service):
    root, other = Entity("Root", "person"), Entity("Other", "place")
    for item in (root, other):
        db_service.insert_entity(item)
    command = AddRelationCommand(root.id, other.id, "custom")
    service = EntityConnectionBrowseService(db_service)
    inputs = query(root.id)
    empty_cursor = service.step({"query": inputs})["cursor"]
    assert command.execute(db_service).success
    with pytest.raises(StaleConnectionCursor):
        service.step({"query": inputs, "cursor": empty_cursor})
    saved_cursor = service.step({"query": inputs})["cursor"]
    command.undo(db_service)
    with pytest.raises(StaleConnectionCursor):
        service.step({"query": inputs, "cursor": saved_cursor})
    undo_cursor = service.step({"query": inputs})["cursor"]
    assert command.execute(db_service).success
    with pytest.raises(StaleConnectionCursor):
        service.step({"query": inputs, "cursor": undo_cursor})


def test_matching_statblocks_do_not_discover_or_rank_connections(db_service):
    stats = {f"stat {index}": index for index in range(60)}
    root, other = (
        Entity("Root", "person", attributes=stats),
        Entity("Other", "person", attributes=dict(stats)),
    )
    for item in (root, other):
        db_service.insert_entity(item)
    rows, responses = collect(EntityConnectionBrowseService(db_service), query(root.id))
    assert not rows
    assert responses[-1]["eligible_total"] == 0
    context = AuthoringContextBuilder(db_service).build_entity_context(root.id)
    assert context.attributes
    assert not (context.co_appearances or context.shared_tags or context.shared_maps)


def test_referenced_event_rescheduling_invalidates_anchored_pages(db_service):
    root, other = Entity("Root", "person"), Entity("Other", "place")
    for item in (root, other):
        db_service.insert_entity(item)
    event = Event("Start", 10.0)
    db_service.insert_event(event)
    identifier = db_service.insert_relation(
        root.id,
        other.id,
        "custom",
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {
                    "anchor": {"anchor_id": f"event:{event.id}", "offset_days": 0.0}
                },
                "end": {"status": "open"},
            }
        },
    )
    service = EntityConnectionBrowseService(db_service)
    inputs = query(root.id, "at_playhead", 20.0)
    rows, responses = collect(service, inputs)
    assert [row["id"] for row in rows] == [identifier]
    assert rows[0]["temporal_evidence"]["events"] == [{"id": event.id, "name": "Start"}]
    event.lore_date = 25.0
    db_service.insert_event(event)
    with pytest.raises(StaleConnectionCursor):
        service.step({"query": inputs, "cursor": responses[-1]["cursor"]})
    assert collect(service, inputs)[0] == []


def test_read_failure_keeps_rows_and_retries_same_cursor(qtbot):
    view = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(view)
    coordinator = EntityConnectionBrowseCoordinator(view, lambda: query("root"))
    requests = []
    coordinator.requested.connect(requests.append)
    coordinator.restart()
    first = requests[-1]
    coordinator.accept(
        {"request_id": first["request_id"], "kind": "page", "error": True}
    )
    assert view.load_connections.text() == "Retry connections"
    assert "all eligible" not in view.connection_status.text()
    coordinator.load_more()
    assert requests[-1]["cursor"] == first["cursor"]
    coordinator.stop()


def test_new_entity_cannot_render_old_connections(qtbot):
    view = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(view)
    view.enable_connection_browsing()
    view.set_entity_context(EntityAuthoringContext("old"))
    view.set_connection_page([], "Loading new Entity", False, entity_id="new")
    assert view._context_id == "old"
    view.set_entity_context(EntityAuthoringContext("new"))
    assert view.sections["Saved direct connections"].section.rows == ()


def test_queued_command_runs_between_candidate_batches(qtbot, tmp_path):
    path = str(tmp_path / "browse.kraken")
    db = DatabaseService(path)
    db.connect()
    root, target = Entity("A", "person"), Entity("B", "place")
    db.insert_entity(root)
    db.insert_entity(target)
    for index in range(110):
        db.insert_relation(root.id, target.id, f"future {index}", {"valid_from": 100.0})
    db.close()
    order = []

    class Owner(QObject):
        command = Signal()

        def __init__(self):
            super().__init__()
            self.db = None

        def database(self):
            if self.db is None:
                self.db = DatabaseService(path)
                self.db.connect()
            return self.db

        @Slot()
        def save(self):
            self.database().insert_entity(Entity("Saved while browsing", "place"))
            order.append("save")

        @Slot()
        def close(self):
            if self.db:
                self.db.close()

    thread = QThread()
    owner = Owner()
    owner.moveToThread(thread)
    task = EntityConnectionBrowseTask(owner.database)
    task.moveToThread(thread)
    view = AuthoringContextWidget(object_label="Entity")
    qtbot.addWidget(view)
    coordinator = EntityConnectionBrowseCoordinator(
        view, lambda: query(root.id, "at_playhead", 20.0)
    )
    coordinator.requested.connect(task.run, Qt.ConnectionType.QueuedConnection)
    owner.command.connect(owner.save, Qt.ConnectionType.QueuedConnection)
    task.finished.connect(lambda result: order.append("batch"))
    task.finished.connect(coordinator.accept, Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(owner.close, Qt.ConnectionType.DirectConnection)
    thread.finished.connect(task.deleteLater)
    thread.finished.connect(owner.deleteLater)
    thread.start()
    try:
        coordinator.restart()
        owner.command.emit()
        qtbot.waitUntil(lambda: len(order) >= 3)
        assert order[:3] == ["batch", "save", "batch"]
    finally:
        coordinator.stop()
        thread.quit()
        assert thread.wait(5000)
