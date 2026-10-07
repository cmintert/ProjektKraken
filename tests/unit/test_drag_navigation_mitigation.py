"""Delivered gesture and real workspace regression evidence for KRT-56."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from src.app.coordinators.longform_navigation import LongformNavigationController
from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.gui.widgets.longform.editor import LongformEditorWidget
from src.gui.workspace import WorkspaceShell

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def document_window(qtbot, init_theme_manager):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.workspace = WorkspaceShell()
    window.setCentralWidget(window.workspace)
    window.longform_editor = LongformEditorWidget()
    for panel_id, widget in (
        ("longform", window.longform_editor),
        ("entity", QLabel("Entity inspector")),
        ("event", QLabel("Event inspector")),
    ):
        window.workspace.register_panel(panel_id, panel_id.title(), widget, "center")
    window.workspace.reset_layout()
    window.workspace.show_panel("longform")
    for name in (
        "event_editor",
        "entity_editor",
        "editor_coordinator",
        "unified_list",
        "timeline",
        "data_coordinator",
    ):
        setattr(window, name, Mock())
    window.event_editor.has_unsaved_changes.return_value = False
    window.entity_editor.has_unsaved_changes.return_value = False
    window.entity_editor.current_entity_id = "prior"
    window.event_editor.current_event_id = None
    navigation = NavigationCoordinator(window)
    navigation.selected_id = "prior"
    navigation.selected_type = "entity"
    window.navigation = navigation
    window.binding = LongformNavigationController(window.longform_editor, navigation)
    window.longform_editor.load_sequence(
        [
            {
                "id": item_id,
                "name": name,
                "table": kind,
                "heading_level": 1,
                "content": "Text to select without leaving the document.",
                "meta": {"position": index * 100, "depth": 0, "parent_id": None},
            }
            for index, (item_id, name, kind) in enumerate(
                [("first", "Character", "entities"), ("second", "Council", "events")]
            )
        ]
    )
    window.resize(1100, 700)
    window.show()
    qtbot.waitExposed(window)
    return window


def test_held_press_and_cancelled_drag_never_switch_shared_tab(document_window, qtbot):
    window = document_window
    outline = window.longform_editor.outline
    point = outline.visualItemRect(outline.topLevelItem(1)).center()
    outline.setFocus()
    qtbot.mousePress(outline.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.wait(300)
    assert window.workspace.active_panel("center") == "longform"
    assert window.navigation.selected_id == "prior"
    with patch("src.gui.widgets.longform.outline.QDrag") as drag:
        drag.return_value.exec.side_effect = lambda *args: qtbot.wait(300)
        outline.startDrag(Qt.DropAction.CopyAction)
    qtbot.mouseRelease(outline.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.wait(300)
    assert window.workspace.active_panel("center") == "longform"
    assert window.navigation.selected_id == "prior"
    window.data_coordinator.load_event_details.assert_not_called()
    window.data_coordinator.load_entity_details.assert_not_called()
    window.timeline.focus_event.assert_not_called()


@pytest.mark.parametrize("index,kind", [(0, "entity"), (1, "event")])
def test_shared_zone_click_stays_local_explicit_open_reveals_inspector(
    document_window, qtbot, index, kind
):
    window = document_window
    view = window.longform_editor
    point = view.outline.visualItemRect(view.outline.topLevelItem(index)).center()
    qtbot.mouseClick(view.outline.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert window.workspace.active_panel("center") == "longform"
    assert window.navigation.selected_id == "prior"
    qtbot.mouseClick(view.btn_open_inspector, Qt.MouseButton.LeftButton)
    assert window.workspace.active_panel("center") == kind
    getattr(window.data_coordinator, f"load_{kind}_details").assert_called_once()


@pytest.mark.parametrize("kind,index", [("entity", 0), ("event", 1)])
def test_visible_separate_inspector_updates_only_after_release(
    document_window, qtbot, kind, index
):
    window = document_window
    window.workspace.move_panel(kind, "right")
    view = window.longform_editor
    view.outline.setFocus()
    point = view.outline.visualItemRect(view.outline.topLevelItem(index)).center()
    qtbot.mousePress(view.outline.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.wait(300)
    assert window.navigation.selected_id == "prior"
    qtbot.mouseRelease(view.outline.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert window.navigation.selected_id in {"first", "second"}
    assert window.workspace.active_panel("center") == "longform"
    assert window.workspace.active_panel("right") == kind
    assert view.outline.hasFocus()


def test_programmatic_selection_is_silent_keyboard_browse_is_completed(
    document_window, qtbot
):
    window = document_window
    window.workspace.move_panel("event", "right")
    outline = window.longform_editor.outline
    outline.setCurrentItem(outline.topLevelItem(0))
    qtbot.wait(300)
    assert window.navigation.selected_id == "prior"
    qtbot.keyClick(outline, Qt.Key.Key_Down)
    assert window.navigation.selected_id == "second"
    assert window.workspace.active_panel("center") == "longform"


def test_deferred_save_is_superseded_by_next_document_gesture(document_window, qtbot):
    from PySide6.QtWidgets import QMessageBox

    window = document_window
    window.workspace.move_panel("entity", "right")
    source = window.entity_editor
    source.has_unsaved_changes.return_value = True
    source._on_save.side_effect = lambda: setattr(source, "_pending_save_revision", 7)
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Save,
    ):
        window.binding.browse("entities", "first")
    assert window.navigation._pending_navigation is not None
    window.longform_editor.gesture_started.emit()
    source.has_unsaved_changes.return_value = False
    window.navigation._on_navigation_save_finished("entity", "prior", 7, True)
    assert window.navigation.selected_id == "prior"
    window.data_coordinator.load_entity_details.assert_not_called()


def test_card_hold_and_text_selection_do_not_navigate(document_window, qtbot):
    content = document_window.longform_editor.content
    selected = []
    content.item_selected.connect(lambda *args: selected.append(args))
    point = QPoint(50, 100)
    qtbot.mousePress(content.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.wait(300)
    assert selected == []
    qtbot.mouseMove(content.viewport(), point + QPoint(100, 0))
    qtbot.mouseRelease(
        content.viewport(), Qt.MouseButton.LeftButton, pos=point + QPoint(100, 0)
    )
    assert selected == []
    assert document_window.workspace.active_panel("center") == "longform"


def test_document_gesture_supersedes_pending_explorer_timer(document_window, qtbot):
    window = document_window
    window.navigation.on_item_selected("event", "second")
    window.longform_editor.gesture_started.emit()
    qtbot.wait(300)
    assert window.navigation.selected_id == "prior"
    assert window.workspace.active_panel("center") == "longform"


def test_explicit_link_save_continuation_keeps_document_origin(document_window):
    from PySide6.QtWidgets import QMessageBox

    from src.core.entities import Entity

    window = document_window
    window.data_coordinator.cached_entities = [
        Entity(id="first", name="Character", type="Character")
    ]
    window.data_coordinator.cached_events = []
    source = window.entity_editor
    source.has_unsaved_changes.return_value = True
    source._on_save.side_effect = lambda: setattr(source, "_pending_save_revision", 7)
    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Save,
    ):
        window.longform_editor.link_clicked.emit("Character")
    assert window.navigation._pending_navigation_context == ("longform", True)
    window.longform_editor.gesture_started.emit()
    source.has_unsaved_changes.return_value = False
    window.navigation._on_navigation_save_finished("entity", "prior", 7, True)
    assert window.navigation.selected_id == "prior"
    assert window.workspace.active_panel("center") == "longform"
