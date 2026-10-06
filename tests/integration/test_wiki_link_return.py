"""KA-04/KA-20 assisted paths use guarded navigation and applied view snapshots."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from src.app.connection_manager import ConnectionManager
from src.app.main import MainWindow
from src.core.entities import Entity
from src.core.events import Event

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def session(qtbot, monkeypatch):
    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)
        window.worker = MagicMock()
        ConnectionManager(window).connect_editors()
        objects = {
            "entity": [
                Entity(name=name, type="Character", description="Origin writing " * 60)
                for name in ("Tasgillia", "House Bjornaer", "Third entry")
            ],
            "event": [
                Event(name=name, lore_date=1.0, description="Origin writing " * 60)
                for name in ("Charter", "Council", "Third event")
            ],
        }
        data = window.data_coordinator
        data._cached_entities = objects["entity"]
        data._cached_events = objects["event"]
        monkeypatch.setattr(
            window.time_coordinator, "resolve_selected_entity", lambda: None
        )

        def load(kind, item_id):
            item = next(item for item in objects[kind] if item.id == item_id)
            if kind == "entity":
                data.on_entity_details_ready(item, [], [])
            else:
                data.on_event_details_ready(item, [], [])

        monkeypatch.setattr(
            data, "load_entity_details", lambda item_id: load("entity", item_id)
        )
        monkeypatch.setattr(
            data, "load_event_details", lambda item_id: load("event", item_id)
        )
        window.resize(1000, 800)
        window.show()
        yield window, objects
        monkeypatch.setattr(window, "check_unsaved_changes", lambda _editor: True)
        monkeypatch.setattr(
            window.map_handler, "has_pending_raster_strokes", lambda: False
        )
        for editor in (window.event_editor, window.entity_editor):
            editor.desc_edit.link_authoring.cancel()
            editor.reset_draft_tracking()
            editor.set_dirty(False)
        window.close()


def editor_for(window, kind):
    return window.event_editor if kind == "event" else window.entity_editor


def start(window, objects, kind):
    item = objects[kind][0]
    window.navigation_coordinator.set_global_selection(kind, item.id)
    editor = editor_for(window, kind)
    cursor = editor.desc_edit.textCursor()
    cursor.setPosition(10)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.desc_edit.setTextCursor(cursor)
    return item, editor


@pytest.mark.parametrize(
    "source_kind,target_kind",
    [
        ("entity", "entity"),
        ("entity", "event"),
        ("event", "entity"),
        ("event", "event"),
    ],
)
@pytest.mark.parametrize("mode", ["rich", "source"])
def test_open_return_restores_mode_selection_and_scroll(
    session, source_kind, target_kind, mode
):
    window, objects = session
    origin, editor = start(window, objects, source_kind)
    if mode == "source":
        editor.desc_edit.toggle_view_mode()
        cursor = editor.desc_edit.textCursor()
        cursor.setPosition(10)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        editor.desc_edit.setTextCursor(cursor)
    editor.desc_edit.editor.verticalScrollBar().setValue(30)
    text = editor.desc_edit.get_wiki_text()
    target = objects[target_kind][1]
    controller = window.app_coordinator.wiki_links
    window.navigation_coordinator.navigate_writing_link(f"id:{target.id}")
    assert window.navigation_coordinator.selected_id == target.id
    assert len(controller.bookmarks) == 1
    destination = editor_for(window, target_kind)
    assert destination.desc_edit.action_return_writing.isVisible()
    destination.desc_edit.action_return_writing.trigger()
    assert window.navigation_coordinator.selected_id == origin.id
    assert editor.desc_edit.editor._view_mode == mode
    assert editor.desc_edit.textCursor().anchor() == 10
    assert editor.desc_edit.textCursor().position() == 5
    assert editor.desc_edit.editor.verticalScrollBar().value() == 30
    assert editor.desc_edit.get_wiki_text() == text
    assert controller.bookmarks == []


def test_nested_links_return_in_order_and_unrelated_navigation_clears(session):
    window, objects = session
    first, _editor = start(window, objects, "entity")
    second, third = objects["entity"][1:]
    controller = window.app_coordinator.wiki_links
    controller.open_link(f"id:{second.id}")
    controller.open_link(f"id:{third.id}")
    assert len(controller.bookmarks) == 2
    controller.return_to_writing()
    assert window.navigation_coordinator.selected_id == second.id
    controller.return_to_writing()
    assert window.navigation_coordinator.selected_id == first.id
    controller.open_link(f"id:{second.id}")
    window.navigation_coordinator.set_global_selection("entity", third.id)
    assert controller.bookmarks == []


@pytest.mark.parametrize("returning", [False, True])
def test_cancelled_navigation_retains_exact_draft_and_bookmark(
    session, monkeypatch, returning
):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    controller = window.app_coordinator.wiki_links
    target = objects["entity"][1]
    if returning:
        controller.open_link(f"id:{target.id}")
        editor = window.entity_editor
    editor.desc_edit.editor.insertPlainText("unfinished")
    before = editor.desc_edit.get_wiki_text()
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Cancel
    )
    if returning:
        controller.return_to_writing()
    else:
        controller.open_link(f"id:{target.id}")
    assert window.navigation_coordinator.selected_id == (
        target.id if returning else origin.id
    )
    assert editor.has_unsaved_changes()
    assert editor.desc_edit.get_wiki_text() == before
    assert len(controller.bookmarks) == int(returning)
    assert controller._pending is None


@pytest.mark.parametrize("complete", [True, False])
def test_link_open_waits_for_exact_save_acknowledgement(session, monkeypatch, complete):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    controller = window.app_coordinator.wiki_links
    target = objects["event"][1]
    editor.desc_edit.editor.insertPlainText("draft")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(editor, "_on_save", editor.begin_save)
    controller.open_link(f"id:{target.id}")
    assert window.navigation_coordinator.selected_id == origin.id
    assert controller.bookmarks == []
    revision = editor._pending_save_revision
    if complete:
        objects["entity"][0].description = editor.desc_edit.get_wiki_text()
    editor.finish_save(revision, complete)
    window.editor_coordinator.editor_save_finished.emit(
        "entity", origin.id, revision, complete
    )
    assert window.navigation_coordinator.selected_id == (
        target.id if complete else origin.id
    )
    assert len(controller.bookmarks) == int(complete)
    if complete:
        controller.return_to_writing()
        assert "draft" in editor.desc_edit.get_wiki_text()


def test_newer_edit_during_save_cancels_link_navigation(session, monkeypatch):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    editor.desc_edit.editor.insertPlainText("first")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(editor, "_on_save", editor.begin_save)
    controller = window.app_coordinator.wiki_links
    controller.open_link(f"id:{objects['event'][1].id}")
    revision = editor._pending_save_revision
    editor.desc_edit.editor.insertPlainText("newer")
    complete = editor.finish_save(revision, True)
    window.editor_coordinator.editor_save_finished.emit(
        "entity", origin.id, revision, complete
    )
    assert window.navigation_coordinator.selected_id == origin.id
    assert editor.has_unsaved_changes()
    assert "newer" in editor.desc_edit.get_wiki_text()
    assert controller.bookmarks == []


def test_peek_escalation_and_focus_writing_return(session, qtbot):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    focus = editor._focus_controller
    focus.enter(editor)
    assert editor.desc_edit.link_toolbar.isVisible()
    editor.desc_edit.action_link_entry.trigger()
    picker = editor.desc_edit.link_authoring.picker
    qtbot.keyClick(picker.search, Qt.Key.Key_Escape)
    assert focus.active is editor
    target = objects["event"][1]
    window.navigation_coordinator.peek_target(f"id:{target.id}")
    window.wiki_peek_panel.open_button.click()
    assert window.navigation_coordinator.selected_id == target.id
    window.app_coordinator.wiki_links.return_to_writing()
    assert window.navigation_coordinator.selected_id == origin.id
    assert focus.active is editor


def test_missing_target_and_origin_never_create_entries(session):
    window, objects = session
    origin, _editor = start(window, objects, "entity")
    commands = []
    window.command_requested.connect(commands.append)
    controller = window.app_coordinator.wiki_links
    controller.open_link("id:550e8400-e29b-41d4-a716-446655449999")
    assert window.navigation_coordinator.selected_id == origin.id
    assert controller.bookmarks == []
    controller.open_link(f"id:{objects['event'][1].id}")
    objects["entity"].remove(origin)
    controller.return_to_writing()
    assert controller.bookmarks == []
    assert commands == []


def test_context_change_cancels_picker_even_when_description_is_identical(session):
    window, objects = session
    _origin, editor = start(window, objects, "entity")
    editor.update_suggestions(
        items=[(item.id, item.name, "entity") for item in objects["entity"]]
    )
    editor.desc_edit.action_link_entry.trigger()
    assert editor.desc_edit.link_authoring.picker is not None
    editor.load_entity(objects["entity"][1])
    assert editor.desc_edit.link_authoring.picker is None


def test_return_waits_for_matching_hydration_and_world_change_clears(
    session, monkeypatch
):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    controller = window.app_coordinator.wiki_links
    controller.open_link(f"id:{objects['entity'][1].id}")
    monkeypatch.setattr(
        window.data_coordinator, "load_entity_details", lambda _id: None
    )
    controller.return_to_writing()
    controller.on_editor_hydrated("event", origin.id)
    assert len(controller.bookmarks) == 1
    assert controller._restore is not None
    window.data_coordinator.on_entity_details_ready(origin, [], [])
    assert editor.desc_edit.textCursor().position() == 5
    assert controller.bookmarks == []
    controller.open_link(f"id:{objects['event'][1].id}")
    monkeypatch.setattr(controller, "world", lambda: "another-world")
    controller.return_to_writing()
    assert controller.bookmarks == []
    assert controller._pending is None


def test_discarded_draft_does_not_reappear_on_return(session, monkeypatch):
    window, objects = session
    origin, editor = start(window, objects, "entity")
    original = origin.description
    editor.desc_edit.editor.insertPlainText("discard this")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Discard
    )
    controller = window.app_coordinator.wiki_links
    controller.open_link(f"id:{objects['entity'][1].id}")
    controller.return_to_writing()
    assert editor.desc_edit.get_wiki_text() == original
    assert not editor.has_unsaved_changes()


def test_missing_hydration_releases_return_controls(session, monkeypatch):
    window, objects = session
    origin, _editor = start(window, objects, "entity")
    controller = window.app_coordinator.wiki_links
    controller.open_link(f"id:{objects['event'][1].id}")
    monkeypatch.setattr(
        window.data_coordinator, "load_entity_details", lambda _id: None
    )
    controller.return_to_writing()
    data = window.data_coordinator
    data._entity_detail_requests.append((origin.id, False))
    data.on_entity_details_ready(None, [], [])
    assert controller._restore is None
    assert controller.bookmarks == []
    assert not window.entity_editor.desc_edit.action_return_writing.isVisible()


@pytest.mark.parametrize("kind", ["entity", "event"])
@pytest.mark.parametrize("derive_mentions", [False, True])
def test_link_save_command_reopen_and_rename_keeps_identity(
    session, db_service, monkeypatch, kind, derive_mentions
):
    from PySide6.QtCore import QSettings

    from src.app.constants import (
        SETTINGS_AUTO_RELATION_KEY,
        WINDOW_SETTINGS_APP,
        WINDOW_SETTINGS_KEY,
    )
    from src.services.text_parser import WikiLinkParser

    window, objects = session
    for item in objects["entity"]:
        db_service.insert_entity(item)
    for item in objects["event"]:
        db_service.insert_event(item)
    source, editor = start(window, objects, kind)
    target = objects["entity"][1]
    editor.desc_edit.set_completer(items=[(target.id, target.name, "entity")])
    editor.desc_edit.set_wiki_text("See House Bjornaer.")
    cursor = editor.desc_edit.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(18, QTextCursor.MoveMode.KeepAnchor)
    editor.desc_edit.setTextCursor(cursor)
    editor.desc_edit.action_link_entry.trigger()
    picker = editor.desc_edit.link_authoring.picker
    picker.results.setCurrentRow(0)
    picker.link_button.click()
    assert db_service.get_relations(source.id) == []
    assert len(db_service.get_all_entities()) == 3
    commands = []
    window.editor_coordinator.command_requested.connect(commands.append)
    QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP).setValue(
        SETTINGS_AUTO_RELATION_KEY, derive_mentions
    )
    editor._on_save()
    assert len(commands) == 1
    command = commands[0]
    result = command.execute(db_service)
    assert result.success
    getter = db_service.get_entity if kind == "entity" else db_service.get_event
    persisted = getter(source.id)
    links = WikiLinkParser.extract_links(persisted.description)
    assert [link.target_id for link in links] == [target.id]
    relations = db_service.get_relations(source.id)
    assert len(relations) == int(derive_mentions)
    assert all(relation["rel_type"] == "mentions" for relation in relations)
    target.name = "Renamed entry"
    db_service.insert_entity(target)
    editor.finish_save(editor._pending_save_revision, True)
    loader = editor.load_entity if kind == "entity" else editor.load_event
    loader(persisted)
    editor.desc_edit.toggle_view_mode()
    editor.desc_edit.toggle_view_mode()
    assert editor.desc_edit.get_wiki_text() == persisted.description
    assert not editor.has_unsaved_changes()
    objects[kind][0] = persisted
    cursor = editor.desc_edit.textCursor()
    cursor.setPosition(5)
    editor.desc_edit.setTextCursor(cursor)
    editor.desc_edit.action_open_link.trigger()
    assert window.navigation_coordinator.selected_id == target.id
    window.app_coordinator.wiki_links.return_to_writing()
    assert window.navigation_coordinator.selected_id == source.id
    assert editor.desc_edit.get_wiki_text() == persisted.description
    command.undo(db_service)
    assert getter(source.id).description == source.description
    assert db_service.get_relations(source.id) == []
    assert command.execute(db_service).success
    assert getter(source.id).description == persisted.description
