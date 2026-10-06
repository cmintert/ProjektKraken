"""KRT-47 visible authoring, explicit membership and guarded world deletion."""

import sqlite3
from contextlib import closing
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from src.app.coordinators.editor_coordinator import EditorCoordinator
from src.app.longform_manager import LongformManager
from src.commands.longform_commands import (
    AddLongformEntryCommand,
    RemoveLongformEntryCommand,
)
from src.commands.registry import get_command_types
from src.core.entities import Entity
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.gui.widgets.longform.editor import LongformEditorWidget
from src.services import longform_builder as longform
from src.services.history_service import HistoryService
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


def _sequence():
    return [
        {
            "table": "entities",
            "id": f"entry-{index}",
            "name": f"Section {index}",
            "content": "Some writing",
            "heading_level": 1,
            "meta": {"position": index * 100.0, "parent_id": None, "depth": 0},
        }
        for index in range(1, 4)
    ]


class Window(QWidget):
    command_requested = Signal(object)


@pytest.fixture
def authoring(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window.longform_editor = LongformEditorWidget(window)
    window.longform_editor.setWindowFlag(Qt.WindowType.Window)
    window.data_coordinator = SimpleNamespace(
        cached_entities=[Entity(id="entry-1", name="Tasgillia", type="Person")],
        cached_events=[Event(id="event-1", name="Charter", lore_date=1218.0)],
        cached_longform_sequence=_sequence(),
    )
    window.status_bar = MagicMock()
    window.editor_coordinator = MagicMock()
    window.navigation_coordinator = SimpleNamespace(
        selected_type=None, selected_id=None
    )
    window.entity_editor = MagicMock()
    window.event_editor = MagicMock()
    manager = LongformManager(window)
    # Existing ConnectionManager binding (unchanged by KRT-47).
    window.longform_editor.delete_requested.connect(manager.delete_longform_item)
    return window, manager


@pytest.mark.parametrize("width", [400, 1100])
def test_labeled_routes_survive_narrow_width(authoring, qtbot, width):
    window, _ = authoring
    editor = window.longform_editor
    editor.resize(width, 600)
    editor.show()
    qtbot.wait(10)
    editor.action_toolbar.refresh()
    assert editor.width() == width
    overflow = editor.action_toolbar.overflow_menu
    for button in (editor.btn_add, editor.btn_outline_actions, editor.btn_find):
        assert button.text()
        assert button.isVisible() or any(
            action.isVisible() and action.text() == button.text()
            for action in overflow.actions()
        )
    assert not editor.btn_outline_actions.isEnabled()
    editor.load_sequence(_sequence())
    editor.outline.setCurrentItem(editor.outline.topLevelItem(1))
    assert editor.btn_outline_actions.isEnabled()
    editor._prepare_outline_actions()
    assert any(
        a.text() == "Demote" and a.isEnabled()
        for a in editor.outline_actions_menu.actions()
    )


def test_membership_add_and_cancel_do_not_navigate_or_delete(authoring, qtbot):
    window, _ = authoring
    editor = window.longform_editor
    commands = []
    navigations = []
    window.command_requested.connect(commands.append)
    editor.item_selected.connect(lambda *args: navigations.append(args))
    editor.btn_add.click()
    picker = editor.membership
    assert picker.results.count() == 2
    assert not picker.add_button.isEnabled()
    picker.search.setText("charter")
    picker.results.setCurrentRow(0)
    picker.add_button.click()
    assert len(commands) == 1
    assert isinstance(commands[0], AddLongformEntryCommand)
    assert (commands[0].table, commands[0].row_id) == ("events", "event-1")
    assert picker.isHidden()
    editor.btn_add.click()
    qtbot.keyClick(picker.search, Qt.Key.Key_Escape)
    assert picker.isHidden()
    assert len(commands) == 1
    assert not navigations


@pytest.mark.parametrize(
    "action_name,signal_name",
    [
        ("Move Up", "move_up_requested"),
        ("Move Down", "move_down_requested"),
        ("Promote", "promote_requested"),
        ("Demote", "demote_requested"),
        ("Remove from document", "remove_requested"),
    ],
)
def test_visible_and_context_actions_share_intents(authoring, action_name, signal_name):
    window, _ = authoring
    editor = window.longform_editor
    sequence = _sequence()
    # Three siblings beneath a parent; middle child permits every structural action.
    parent = deepcopy(sequence[0])
    parent["id"] = "parent"
    for item in sequence:
        item["meta"].update(parent_id="parent", depth=1)
    editor.load_sequence([parent, *sequence])
    editor.outline.setCurrentItem(editor.outline.topLevelItem(0).child(1))
    intents = []
    getattr(editor, signal_name).connect(lambda *args: intents.append(args))
    editor._prepare_outline_actions()
    context = QMenu()
    editor.outline.populate_actions_menu(context)
    for menu in (editor.outline_actions_menu, context):
        action = next(a for a in menu.actions() if a.text() == action_name)
        assert action.isEnabled()
        action.trigger()
    assert intents[0] == intents[1]
    assert intents[0][:2] == ("entities", "entry-2")


def test_outline_refresh_preserves_target_without_navigation(authoring):
    window, _ = authoring
    editor = window.longform_editor
    editor.load_sequence(_sequence())
    editor.outline.setCurrentItem(editor.outline.topLevelItem(1))
    navigations = []
    editor.item_selected.connect(lambda *args: navigations.append(args))
    editor.load_sequence(list(reversed(_sequence())))
    assert editor.get_current_selection() == ("entities", "entry-2")
    assert not navigations
    editor._on_content_selected("entities", "entry-1")
    assert editor.get_current_selection() == ("entities", "entry-1")
    assert navigations == [("entities", "entry-1")]


@pytest.mark.parametrize("table,kind", [("events", "event"), ("entities", "entity")])
@pytest.mark.parametrize(
    "answer", [QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes]
)
def test_complete_deletion_requires_confirmation(
    authoring, monkeypatch, db_service, table, kind, answer
):
    window, _ = authoring
    entry = (
        Event(id="target", name="Delete me", lore_date=1.0)
        if kind == "event"
        else Entity(id="target", name="Delete me", type="Person")
    )
    getattr(db_service, f"insert_{kind}")(entry)
    window.editor_coordinator = EditorCoordinator(window)
    commands = []
    window.editor_coordinator.command_requested.connect(commands.append)
    prompts = []

    def warning(*args):
        prompts.append(args)
        return answer

    monkeypatch.setattr(QMessageBox, "warning", warning)
    window.longform_editor.delete_requested.emit(table, "target")
    assert prompts[0][-1] == QMessageBox.StandardButton.Cancel
    if answer == QMessageBox.StandardButton.Yes:
        assert len(commands) == 1
        assert commands[0].execute(db_service).success
        assert getattr(db_service, f"get_{kind}")(entry.id) is None
        commands[0].undo(db_service)
        assert getattr(db_service, f"get_{kind}")(entry.id).name == "Delete me"
    else:
        assert not commands
        assert getattr(db_service, f"get_{kind}")(entry.id).name == "Delete me"


def test_delete_preserves_dirty_target_on_guard_cancel(authoring, monkeypatch):
    window, manager = authoring
    window.navigation_coordinator.selected_type = "entity"
    window.navigation_coordinator.selected_id = "entry-1"
    window.editor_coordinator.check_unsaved_changes.return_value = False
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes
    )
    manager.delete_longform_item("entities", "entry-1")
    window.editor_coordinator.check_unsaved_changes.assert_called_once_with(
        window.entity_editor
    )
    window.editor_coordinator.on_item_delete_requested.assert_not_called()


@pytest.mark.parametrize("table", ["entities", "events"])
def test_membership_survives_refresh_export_and_history(db_service, table):
    entry = (
        Entity(name="Keep", type="Person")
        if table == "entities"
        else Event(name="Keep", lore_date=1.0)
    )
    getattr(db_service, "insert_entity" if table == "entities" else "insert_event")(
        entry
    )
    command = AddLongformEntryCommand.from_dict(
        AddLongformEntryCommand(table, entry.id, {}, {}).to_dict()
    )
    assert command.execute(db_service).success
    conn = db_service.require_connection()
    before = deepcopy(longform.get_longform_meta(conn, table, entry.id))
    duplicate = AddLongformEntryCommand(table, entry.id, {}, {})
    assert duplicate.execute(db_service).success
    duplicate.undo(db_service)
    assert duplicate.execute(db_service).success
    assert longform.get_longform_meta(conn, table, entry.id) == before
    removal = RemoveLongformEntryCommand.from_dict(
        RemoveLongformEntryCommand(table, entry.id, {}).to_dict()
    )
    assert removal.execute(db_service).success
    worker = DatabaseWorker("unused")
    worker.db_service = db_service
    loaded = []
    worker.longform_sequence_loaded.connect(loaded.append)
    worker.load_longform_sequence("default")
    assert loaded == [[]]
    assert longform.build_longform_sequence(conn) == []
    assert "Keep" not in longform.export_longform_to_markdown(conn)
    longform.reindex_document_positions(conn)
    assert longform.get_longform_meta(conn, table, entry.id) == {}
    assert (
        getattr(db_service, "get_entity" if table == "entities" else "get_event")(
            entry.id
        ).name
        == "Keep"
    )
    restored = RemoveLongformEntryCommand.from_dict(removal.to_dict())
    restored.undo(db_service)
    assert longform.get_longform_meta(conn, table, entry.id) == before
    assert restored.execute(db_service).success
    command = AddLongformEntryCommand.from_dict(command.to_dict())
    command.undo(db_service)
    assert command.execute(db_service).success
    assert longform.get_longform_meta(conn, table, entry.id) == before
    assert {
        "AddLongformEntryCommand",
        "RemoveLongformEntryCommand",
    } <= get_command_types().keys()


def test_remove_section_lifts_descendants_and_exact_undo(db_service, monkeypatch):
    entries = []
    for index, name in enumerate(("Section", "Child", "Grandchild", "Next")):
        parent_id = entries[index - 1].id if index in (1, 2) else None
        entry = Entity(
            name=name,
            type="Section",
            attributes={
                "unrelated": True,
                "_longform": {
                    "default": {
                        "parent_id": parent_id,
                        "depth": index if index < 3 else 0,
                        "position": 100.0 + index * 100,
                        "custom": [name],
                    },
                    "other": {"position": 77},
                },
            },
        )
        db_service.insert_entity(entry)
        entries.append(entry)
    before = [deepcopy(e.attributes) for e in entries]
    request = RemoveLongformEntryCommand("entities", entries[0].id, {})
    command = RemoveLongformEntryCommand.from_dict(request.to_dict())
    assert command.execute(db_service).success
    assert [
        i["name"]
        for i in longform.build_longform_sequence(db_service.require_connection())
    ] == ["Child", "Grandchild", "Next"]
    assert (
        db_service.get_entity(entries[1].id).attributes["_longform"]["default"]["depth"]
        == 0
    )
    command = RemoveLongformEntryCommand.from_dict(command.to_dict())
    command.undo(db_service)
    assert [db_service.get_entity(e.id).attributes for e in entries] == before

    original_remove = longform.remove_from_longform

    def fail_remove(*args):
        raise RuntimeError("removal failed after lifting children")

    monkeypatch.setattr(longform, "remove_from_longform", fail_remove)
    command = RemoveLongformEntryCommand("entities", entries[0].id, {})
    assert not command.execute(db_service).success
    assert [db_service.get_entity(e.id).attributes for e in entries] == before
    assert not db_service.require_connection().in_transaction
    monkeypatch.setattr(longform, "remove_from_longform", original_remove)
    assert command.execute(db_service).success
    command.undo(db_service)
    assert [db_service.get_entity(e.id).attributes for e in entries] == before


def test_labeled_find_and_theme_switch_keep_selection(authoring, qtbot):
    window, _ = authoring
    editor = window.longform_editor
    editor.resize(650, 600)
    editor.show()
    editor.activateWindow()
    qtbot.wait(10)
    editor.load_sequence(_sequence())
    editor.outline.setCurrentItem(editor.outline.topLevelItem(1))
    editor.btn_find.click()
    assert editor.search_input.hasFocus()
    editor.search_input.setText("writing")
    qtbot.keyClick(editor.search_input, Qt.Key.Key_Return)
    assert editor.content.textCursor().selectedText() == "writing"
    theme = ThemeManager()
    theme.theme_changed.emit(theme.get_theme())
    assert editor.get_current_selection() == ("entities", "entry-2")
    assert editor.search_input.text() == "writing"
    qtbot.keyClick(editor.search_input, Qt.Key.Key_Escape)
    assert editor.search_widget.isHidden()


def test_visible_add_nest_reorder_and_undo(authoring, db_service):
    """Exercise KA-18 through visible controls and the existing manager intents."""
    window, manager = authoring
    editor = window.longform_editor
    person = window.data_coordinator.cached_entities[0]
    charter = window.data_coordinator.cached_events[0]
    db_service.insert_entity(person)
    db_service.insert_event(charter)
    commands = []
    window.command_requested.connect(commands.append)
    for signal, slot in (
        (editor.promote_requested, manager.promote_longform_entry),
        (editor.demote_requested, manager.demote_longform_entry),
        (editor.move_up_requested, manager.move_up_longform_entry),
        (editor.move_down_requested, manager.move_down_longform_entry),
    ):
        signal.connect(slot)

    def apply():
        assert commands[-1].execute(db_service).success
        sequence = longform.build_longform_sequence(db_service.require_connection())
        window.data_coordinator.cached_longform_sequence = sequence
        editor.load_sequence(sequence)
        return sequence

    for search in ("Tasgillia", "Charter"):
        editor.btn_add.click()
        editor.membership.search.setText(search)
        editor.membership.results.setCurrentRow(0)
        editor.membership.add_button.click()
        apply()
    editor.outline.setCurrentItem(editor.outline.topLevelItem(1))

    def trigger(label):
        editor._prepare_outline_actions()
        action = next(
            a for a in editor.outline_actions_menu.actions() if a.text() == label
        )
        assert action.isEnabled()
        action.trigger()
        return apply()

    nested = trigger("Demote")
    assert nested[1]["meta"]["parent_id"] == person.id
    assert editor.get_current_selection() == ("events", charter.id)
    editor.load_sequence(nested)
    assert editor.outline.topLevelItem(0).child(0).text(0) == "Charter"
    trigger("Promote")
    reordered = trigger("Move Up")
    assert [item["id"] for item in reordered] == [charter.id, person.id]
    commands[-1].undo(db_service)
    restored = longform.build_longform_sequence(db_service.require_connection())
    editor.load_sequence(restored)
    assert [item["id"] for item in restored] == [person.id, charter.id]


def test_membership_commands_replay_after_database_reopen(db_service, tmp_path):
    entry = Entity(name="Stored entry", type="Person")
    db_service.insert_entity(entry)
    path = tmp_path / "membership.kraken"
    with closing(sqlite3.connect(path)) as target:
        db_service.require_connection().backup(target)
    db_service.close()
    db_service.db_path = str(path)
    db_service.connect()
    history = HistoryService(db_service, "membership-world")
    for name in ("AddLongformEntryCommand", "RemoveLongformEntryCommand"):
        history.register_command_type(name, get_command_types()[name])
    for command in (
        AddLongformEntryCommand("entities", entry.id, {}, {}),
        RemoveLongformEntryCommand("entities", entry.id, {}),
    ):
        assert command.execute(db_service).success
        history.save_command(command)
    history.end_session()
    db_service.close()
    db_service.connect()
    history = HistoryService(db_service, "membership-world")
    for name in ("AddLongformEntryCommand", "RemoveLongformEntryCommand"):
        history.register_command_type(name, get_command_types()[name])
    commands = history.load_recent_history()
    assert len(commands) == 2
    commands[1].undo(db_service)
    assert len(longform.build_longform_sequence(db_service.require_connection())) == 1
    commands[0].undo(db_service)
    assert longform.build_longform_sequence(db_service.require_connection()) == []
    for command in commands:
        assert command.execute(db_service).success
    assert longform.build_longform_sequence(db_service.require_connection()) == []
    assert db_service.get_entity(entry.id).name == "Stored entry"
