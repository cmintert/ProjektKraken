"""Activity layouts preserve live authoring state and isolated local snapshots."""

from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QMainWindow, QTextEdit, QToolButton

from src.app.coordinators.workspace_coordinator import WorkspaceCoordinator
from src.core.workspaces import (
    BUILTIN_WORKSPACES,
    WORKSPACE_COLLECTION_KEY,
    workspace_default,
)
from src.gui.workspace import WorkspaceShell
from src.services.local_settings import LocalSettingsAdapter
from src.services.workspace_store import WorkspaceStore

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def workspace(qtbot, tmp_path):
    window = QMainWindow()
    qtbot.addWidget(window)
    shell = WorkspaceShell(window)
    window.setCentralWidget(shell)
    for identifier, zone in (
        ("project", "left"),
        ("entity", "center"),
        ("event", "center"),
        ("map", "center"),
        ("graph", "center"),
        ("longform", "center"),
        ("analysis", "right"),
        ("ai_search", "right"),
        ("wiki_peek", "right"),
        ("timeline", "bottom"),
        ("history", "bottom"),
    ):
        widget = (
            QTextEdit()
            if identifier in ("entity", "event", "longform")
            else QLabel(identifier)
        )
        shell.register_panel(identifier, identifier.title(), widget, zone)
    window.resize(1600, 900)
    window.show()
    settings = QSettings(str(tmp_path / "workspaces.ini"), QSettings.Format.IniFormat)
    selection = Mock(return_value="event")
    exit_focus = Mock()
    coordinator = WorkspaceCoordinator(
        shell, WorkspaceStore(settings), selection, exit_focus, window
    )
    coordinator.restore()
    qtbot.wait(1)
    return window, shell, coordinator, settings, selection, exit_focus


@pytest.mark.parametrize("identifier", [item.id for item in BUILTIN_WORKSPACES])
def test_defaults_are_independent_and_foreground_current_inspector(
    workspace, identifier
):
    _, shell, coordinator, _, _, _ = workspace
    coordinator.activate(identifier)
    if identifier in ("cartography", "connections"):
        assert shell.active_panel("right") == "event"
        assert shell.active_panel("center") == (
            "map" if identifier == "cartography" else "graph"
        )
    else:
        assert shell.active_panel("center") == "event"
    assert shell.zone_visible("bottom") == (
        identifier in ("overview", "chronology", "cartography")
    )
    assert shell.zone_visible("right") == (
        identifier in ("overview", "cartography", "connections", "research")
    )
    assert len(shell.panel_ids()) == 11


def test_switch_roundtrip_retains_drafts_documents_caret_and_undo(workspace):
    _, shell, coordinator, _, _, exit_focus = workspace
    snapshots = {}
    for identifier in ("entity", "event", "longform"):
        editor = shell.panel(identifier)
        editor.setPlainText("Saved paragraph\n" * 100)
        editor.moveCursor(QTextCursor.MoveOperation.End)
        editor.insertPlainText("unsaved draft")
        cursor = editor.textCursor()
        cursor.setPosition(3)
        cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        snapshots[identifier] = (
            editor,
            editor.document(),
            editor.toPlainText(),
            cursor.position(),
            cursor.anchor(),
        )
    shell.panel("map").setProperty("draft", {"vertices": [1, 2]})
    shell.panel("timeline").setProperty("playhead", 123.5)
    for identifier in (
        "writing",
        "cartography",
        "connections",
        "research",
        "chronology",
        "overview",
    ):
        coordinator.activate(identifier)
    for identifier, (editor, document, text, position, anchor) in snapshots.items():
        assert shell.panel(identifier) is editor
        assert editor.document() is document
        assert editor.toPlainText() == text
        assert editor.textCursor().position() == position
        assert editor.textCursor().anchor() == anchor
        assert document.isModified()
        assert document.isUndoAvailable()
    assert shell.panel("map").property("draft") == {"vertices": [1, 2]}
    assert shell.panel("timeline").property("playhead") == 123.5
    assert exit_focus.call_count == 6


def test_noop_and_view_panel_do_not_switch_workspaces(workspace):
    _, shell, coordinator, _, _, exit_focus = workspace
    changed = Mock()
    shell.layout_changed.connect(changed)
    coordinator.activate("overview")
    assert not changed.called
    assert not exit_focus.called
    coordinator.activate("writing")
    shell.show_panel("map")
    assert coordinator.active_id == "writing"
    assert shell.active_panel("center") == "map"


def test_custom_layout_survives_switch_and_restart(workspace):
    window, shell, coordinator, settings, selection, exit_focus = workspace
    coordinator.activate("writing")
    shell.move_panel("map", "right")
    shell.close_panel("analysis")
    identifier = coordinator.save_as("My writing")
    baseline = shell.capture_layout()
    coordinator.activate("chronology")
    coordinator.activate(identifier)
    assert shell.panel_zone("map") == "right"
    assert not shell.is_panel_open("analysis")
    shell.activity_bar.set_expanded(False)
    coordinator.flush()
    # Simulate a new session over the same settings with a separate shell.
    store = WorkspaceStore(settings)
    loaded = store.load()
    assert loaded["active"] == identifier
    assert loaded["expanded"] is False
    assert loaded["entries"][identifier]["baseline"] == baseline
    fresh = WorkspaceShell(window)
    for definition in shell.registry.definitions():
        fresh.register_panel(
            definition.id, definition.title, QLabel(), definition.default_zone
        )
    restored = WorkspaceCoordinator(fresh, store, selection, exit_focus, window)
    restored.restore()
    assert restored.active_id == identifier
    assert fresh.panel_zone("map") == "right"
    assert not fresh.is_panel_open("analysis")


def test_custom_reset_rename_and_delete_preserve_other_workspaces(workspace):
    _, shell, coordinator, _, _, _ = workspace
    identifier = coordinator.save_as("Drafting")
    original = deepcopy(coordinator.collection["entries"]["overview"])
    baseline = deepcopy(coordinator.collection["entries"][identifier]["baseline"])
    shell.move_panel("map", "left")
    shell.close_panel("history")
    coordinator.rename("Drafting revised")
    coordinator.reset()
    assert shell.panel_zone("map") == "center"
    assert shell.is_panel_open("history")
    assert coordinator.collection["entries"][identifier]["baseline"] == baseline
    assert coordinator.collection["entries"]["overview"] == original
    coordinator.delete()
    assert identifier not in coordinator.collection["entries"]
    assert coordinator.active_id == "overview"


def test_duplicate_names_and_builtin_mutation_are_guarded(workspace):
    _, _, coordinator, _, _, _ = workspace
    coordinator.rename("No")
    coordinator.delete()
    assert coordinator.active_id == "overview"
    with pytest.raises(ValueError):
        coordinator.save_as(" overview ")
    with pytest.raises(ValueError):
        coordinator.save_as(" ")


def test_atomic_activation_emits_only_final_visible_panels(workspace):
    _, shell, coordinator, _, _, _ = workspace
    activations = []
    shell.panel_activated.connect(activations.append)
    coordinator.activate("writing")
    assert activations == ["project", "event"]
    assert "longform" not in activations
    assert "graph" not in activations


def test_selected_inspector_and_last_inspector_fallback(workspace):
    _, shell, coordinator, _, selection, _ = workspace
    selection.return_value = None
    shell.show_panel("entity")
    coordinator.activate("research")
    assert shell.active_panel("center") == "entity"
    selection.return_value = "event"
    coordinator.activate("writing")
    assert shell.active_panel("center") == "event"


def test_debounced_tab_and_visibility_changes_are_saved(workspace, qtbot):
    _, shell, coordinator, settings, _, _ = workspace
    shell.show_panel("longform")
    shell.hide_zone("right")
    qtbot.waitUntil(
        lambda: WorkspaceStore(settings).load()["entries"]["overview"]["layout"][
            "zones"
        ]["center"]["active"]
        == "longform"
    )
    assert not WorkspaceStore(settings).load()["entries"]["overview"]["layout"][
        "zones"
    ]["right"]["visible"]


def test_rail_sizes_and_keyboard_activation(workspace, qtbot):
    _, shell, coordinator, _, _, _ = workspace
    rail = shell.activity_bar
    assert not rail.expanded
    assert rail.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert rail.iconSize().width() == 18
    rail.set_expanded(True)
    qtbot.wait(1)
    expanded_width = rail.width()
    rail.set_expanded(False)
    qtbot.wait(1)
    assert rail.width() < expanded_width
    button = rail.widgetForAction(rail.workspace_actions["writing"])
    button.setFocus()
    qtbot.keyClick(button, Qt.Key.Key_Space)
    assert coordinator.active_id == "writing"
    assert button.hasFocus()
    assert button.accessibleName() == "Writing"
    assert not button.icon().isNull()
    assert len(rail.workspace_actions) == 6
    assert all(
        isinstance(rail.widgetForAction(action), QToolButton)
        for action in rail.workspace_actions.values()
    )


def test_menu_bar_keeps_full_workspace_name(workspace):
    window, shell, _, _, _, _ = workspace
    menu_action = window.menuBar().addMenu(shell.activity_bar.workspace_menu)
    assert menu_action.text() == "Workspaces"
    assert menu_action.icon().isNull()


def test_workspace_popup_returns_focus_to_navigation(workspace, qtbot):
    window, shell, coordinator, _, _, _ = workspace
    rail = shell.activity_bar
    origin = rail.widgetForAction(rail.management_action)
    origin.setFocus()
    menu = rail.workspace_menu
    menu.popup(origin.mapToGlobal(QPoint(0, origin.height())))
    qtbot.wait(1)
    next(action for action in menu.actions() if action.text() == "Writing").trigger()
    menu.close()
    qtbot.wait(1)
    assert coordinator.active_id == "writing"
    # Offscreen Qt leaves the closed popup as its active top-level window.
    # Assert the destination window's focus owner; native activation is reviewed separately.
    assert window.focusWidget() is origin


def test_cancelled_reset_leaves_layout_unchanged(workspace, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    _, shell, coordinator, _, _, _ = workspace
    coordinator.activate("writing")
    shell.close_panel("map")
    before = shell.capture_layout()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No
    )
    coordinator.manage("reset")
    assert shell.capture_layout() == before


def test_popup_return_respects_assistance_keyboard_ownership(workspace, qapp):
    window, shell, _, _, _, _ = workspace
    rail = shell.activity_bar
    origin = rail.widgetForAction(rail.management_action)
    other = rail.widgetForAction(rail.workspace_actions["writing"])
    other.setFocus()
    rail._menu_origin = origin
    previous = qapp.property("krakenInspectionPopup")
    try:
        qapp.setProperty("krakenInspectionPopup", True)
        rail._restore_menu_focus()
        assert window.focusWidget() is other
    finally:
        qapp.setProperty("krakenInspectionPopup", previous)


@pytest.mark.parametrize("size", [float("inf"), 10**400])
def test_malformed_geometry_and_unknown_panels_are_normalized(workspace, size):
    _, shell, coordinator, _, _, _ = workspace
    layout = workspace_default("overview")
    layout["zones"]["left"]["size"] = size
    layout["zones"]["center"]["panels"] = ["missing", "event", "event"]
    layout["closed_panels"] = {"gone": "left", "map": "right"}
    coordinator.collection["entries"]["research"]["layout"] = layout
    coordinator.activate("research")
    assert shell.panes["center"].panel_ids().count("event") == 1
    assert "missing" not in shell.panes["center"].panel_ids()
    assert not shell.is_panel_open("map")
    assert shell.panel_zone("map") == "right"


def test_migration_and_invalid_entry_recovery(tmp_path):
    settings = QSettings(str(tmp_path / "migration.ini"), QSettings.Format.IniFormat)
    old = workspace_default("chronology", "event")
    settings.setValue("workspace_layout", json.dumps(old))
    settings.setValue("saved_layouts", json.dumps({"Legacy": old, "Broken": "garbage"}))
    store = WorkspaceStore(settings)
    result = store.load()
    assert result["entries"]["overview"]["layout"] == old
    custom = next(key for key in result["entries"] if key.startswith("custom:"))
    assert result["entries"][custom]["name"] == "Legacy"
    store.save(result)
    assert store.load()["entries"].keys() == result["entries"].keys()
    result["entries"]["writing"]["layout"] = {"layout_version": 999}
    result["entries"]["custom:broken"] = {"name": "Broken", "layout": []}
    result["entries"][custom]["layout"] = "malformed"
    result["active"] = "absent"
    store.save(result)
    restored = store.load()
    assert restored["active"] == "overview"
    assert restored["entries"]["writing"]["layout"] is None
    assert "custom:broken" not in restored["entries"]
    assert restored["entries"][custom]["name"] == "Legacy"
    assert settings.value("workspace_layout") == json.dumps(old)


def test_restore_before_show_does_not_save_provisional_splitter_sizes(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "hidden.ini"), QSettings.Format.IniFormat)
    store = WorkspaceStore(settings)
    for _ in range(2):
        window = QMainWindow()
        qtbot.addWidget(window)
        shell = WorkspaceShell(window)
        window.setCentralWidget(shell)
        shell.register_panel("project", "Project", QLabel(), "left")
        shell.register_panel("entity", "Entity", QLabel(), "center")
        coordinator = WorkspaceCoordinator(
            shell, store, lambda: "entity", lambda: None, window
        )
        coordinator.restore()
        assert (
            store.load()["entries"]["overview"]["layout"]["zones"]["left"]["size"]
            == 270
        )


def test_local_reset_retains_custom_resources(workspace):
    _, _, coordinator, settings, _, _ = workspace
    identifier = coordinator.save_as("Retained")
    LocalSettingsAdapter(settings).reset_workspace()
    result = WorkspaceStore(settings).load()
    assert identifier in result["entries"]
    assert result["entries"]["overview"]["layout"] is None
    assert result["active"] == "overview"
    assert result["expanded"] is False
    assert settings.value(WORKSPACE_COLLECTION_KEY)


def test_new_icon_default_applies_once_then_remembers_expansion(tmp_path):
    settings = QSettings(str(tmp_path / "navigation.ini"), QSettings.Format.IniFormat)
    settings.setValue(
        WORKSPACE_COLLECTION_KEY, json.dumps({"version": 1, "expanded": True})
    )
    store = WorkspaceStore(settings)
    collection = store.load()
    assert collection["expanded"] is False
    collection["expanded"] = True
    store.save(collection)
    assert store.load()["expanded"] is True


def test_real_longform_retains_selection_scroll_and_cached_hydration(qtbot, tmp_path):
    from src.app.longform_manager import LongformManager
    from src.gui.widgets.longform import LongformEditorWidget

    window = QMainWindow()
    qtbot.addWidget(window)
    shell = WorkspaceShell(window)
    window.workspace = shell
    window.setCentralWidget(shell)
    longform = LongformEditorWidget(window)
    window.longform_editor = longform
    window.data_coordinator = Mock()
    window.longform_filter_config = {}
    shell.register_panel("project", "Project", QLabel(), "left")
    shell.register_panel("entity", "Entity", QLabel(), "center")
    shell.register_panel("longform", "Longform", longform, "center")
    manager = LongformManager(window)
    sequence = [
        {
            "id": "draft",
            "table": "entities",
            "name": "Draft",
            "content": "A paragraph for reading.\n\n" * 100,
            "heading_level": 1,
            "meta": {},
            "depth": 0,
        }
    ]
    longform.load_sequence(sequence)
    manager.on_longform_sequence_loaded(sequence)
    shell.panel_activated.connect(manager.on_panel_activated)
    coordinator = WorkspaceCoordinator(
        shell,
        WorkspaceStore(
            QSettings(str(tmp_path / "longform.ini"), QSettings.Format.IniFormat)
        ),
        lambda: "entity",
        lambda: None,
        window,
    )
    coordinator.restore()
    coordinator.activate("writing")
    shell.show_panel("longform")
    window.resize(1600, 900)
    window.show()
    qtbot.wait(1)
    view = longform.content
    document = view.document()
    cursor = view.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    view.verticalScrollBar().setValue(100)
    scroll = view.verticalScrollBar().value()
    coordinator.activate("overview")
    coordinator.activate("writing")
    qtbot.wait(1)
    assert view.document() is document
    assert view.textCursor().position() == 10
    assert view.textCursor().anchor() == 3
    assert view.verticalScrollBar().value() == scroll
    assert not manager._reload_timer.isActive()
    manager.shutdown()
