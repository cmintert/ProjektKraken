"""Focused writing presentation preserves live editor and workspace behavior."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QVBoxLayout, QWidget

from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.focus_writing import FocusWritingController
from src.gui.workspace.workspace_shell import WorkspaceShell


@pytest.fixture(params=["event", "entity"])
def focus_setup(qtbot, request):
    window = QWidget()
    window.worker = MagicMock()
    layout = QVBoxLayout(window)
    workspace = WorkspaceShell(window)
    window.workspace = workspace
    layout.addWidget(workspace)
    window.event_editor = EventEditorWidget(window)
    window.entity_editor = EntityEditorWidget(window)
    workspace.register_panel("project", "Project", QWidget(), "left")
    workspace.register_panel("event", "Event", window.event_editor, "center")
    workspace.register_panel("entity", "Entity", window.entity_editor, "center")
    window.event_editor.load_event(
        Event(id="event", name="Arrival", lore_date=0.0, description="First paragraph")
    )
    window.entity_editor.load_entity(
        Entity(id="entity", name="Ada", type="Character", description="First paragraph")
    )
    workspace.show_panel(request.param)
    controller = FocusWritingController(window, QMenu(window))
    qtbot.addWidget(window)
    window.resize(1050, 750)
    window.show()
    editor = window.event_editor if request.param == "event" else window.entity_editor
    yield window, editor, controller
    controller.exit()


def test_focus_mode_preserves_live_document_and_state(focus_setup, qtbot):
    window, editor, controller = focus_setup
    view = editor.desc_edit
    document = view.editor.document()
    original_sizes = editor.description_field.sizes()
    cursor = view.editor.textCursor()
    cursor.setPosition(5)
    view.editor.setTextCursor(cursor)
    editor.inspector.main_tabs.setCurrentIndex(2)
    controller.enter(editor)
    assert controller.active is editor
    assert view.editor.document() is document
    assert view.isAncestorOf(view.editor)
    assert not editor.has_unsaved_changes()
    assert not editor.header_widget.isVisible()
    assert controller._tints["left"].testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )
    qtbot.keyClicks(view.editor, " new")
    assert editor.has_unsaved_changes()
    assert " new" in view.editor.toPlainText()
    controller.exit()
    assert editor.description_field.indexOf(view) == 0
    assert view.editor.document() is document
    assert editor.inspector.main_tabs.currentIndex() == 2
    assert view.editor.textCursor().position() == 9
    assert editor.has_unsaved_changes()
    assert len(editor.description_field.sizes()) == len(original_sizes)
    view.editor.undo()
    assert view.editor.toPlainText() == "First paragraph"
    assert window.workspace.active_panel("center") in {"event", "entity"}


def test_escape_and_local_button_restore_layout(focus_setup, qtbot):
    _window, editor, controller = focus_setup
    editor._presentation.focus_button.click()
    assert controller.active is editor
    qtbot.keyClick(editor.desc_edit.editor, Qt.Key.Key_Escape)
    assert controller.active is None
    assert editor.header_widget.isVisible()
    assert not editor.has_unsaved_changes()


def test_focus_action_precedes_bold_in_formatting_toolbar(focus_setup):
    _window, editor, _controller = focus_setup
    actions = editor.desc_edit.toolbar.actions()
    focus_index = actions.index(editor._presentation._focus_toolbar_action)
    bold_index = actions.index(editor.desc_edit.editor.action_bold)
    assert focus_index + 1 == bold_index
    assert editor._presentation.focus_button.toolTip() == "Focus writing (F11)"


def test_local_focus_control_stays_checked_until_exit(focus_setup):
    _window, editor, controller = focus_setup
    button = editor._presentation.focus_button
    button.click()
    assert controller.active is editor
    assert button.isChecked()
    controller.toggle_for(editor)
    assert controller.active is editor
    assert button.isChecked()
    controller.exit()
    assert not button.isChecked()


def test_read_only_entity_cannot_enter(focus_setup):
    _window, editor, controller = focus_setup
    if not isinstance(editor, EntityEditorWidget):
        pytest.skip("Only Entity has a temporal read-only mode")
    editor.set_read_only_mode(True)
    assert not editor._presentation.focus_button.isEnabled()
    assert not controller.action.isEnabled()
    controller.enter(editor)
    assert controller.active is None
    editor.set_read_only_mode(False)
    assert editor._presentation.focus_button.isEnabled()


@pytest.mark.parametrize("width", [360, 560, 800, 1200])
def test_focus_controls_fit_available_width(focus_setup, qtbot, width):
    window, editor, controller = focus_setup
    window.resize(width, 650)
    controller.enter(editor)
    qtbot.wait(10)
    assert editor._focus_surface.width() <= editor.width()
    assert editor._focus_surface.exit_button.isVisible()
    assert editor._focus_surface.toc_button.isVisible()
    assert editor._focus_surface.toolbar_button.isVisible()


def test_navigation_closes_focus_without_blocking_panel(focus_setup):
    window, editor, controller = focus_setup
    controller.enter(editor)
    window.workspace.show_panel("project")
    assert controller.active is None
    assert window.workspace.active_panel("left") == "project"
    assert not controller._tints["left"].isVisible()


@pytest.mark.parametrize("zone", ["left", "center", "right", "bottom"])
def test_focus_dims_every_visible_pane_except_its_own(focus_setup, qtbot, zone):
    window, editor, controller = focus_setup
    workspace = window.workspace
    panel_id = "event" if isinstance(editor, EventEditorWidget) else "entity"
    if zone != "center":
        workspace.move_panel(panel_id, zone)
    for pane_zone in ("left", "right", "bottom"):
        workspace.show_zone(pane_zone)

    controller.enter(editor)
    assert controller.active is editor
    for pane_zone, tint in controller._tints.items():
        assert tint.isVisible() == (pane_zone != zone and workspace.panes[pane_zone].isVisible())

    qtbot.mouseClick(editor.desc_edit.editor.viewport(), Qt.MouseButton.LeftButton)
    assert controller.active is editor


def test_same_item_reload_keeps_focus_new_item_exits(focus_setup):
    _window, editor, controller = focus_setup
    controller.enter(editor)
    if isinstance(editor, EventEditorWidget):
        editor.load_event(
            Event(id="event", name="Arrival", lore_date=0.0, description="Again")
        )
        assert controller.active is editor
        editor.load_event(Event(id="other", name="Elsewhere", lore_date=0.0))
    else:
        editor.load_entity(
            Entity(id="entity", name="Ada", type="Character", description="Again")
        )
        assert controller.active is editor
        editor.load_entity(Entity(id="other", name="Elsewhere", type="Character"))
    assert controller.active is None


def test_repeated_entry_restores_width_and_chrome(focus_setup, qtbot):
    _window, editor, controller = focus_setup
    view = editor.desc_edit
    qtbot.wait(10)
    original_limits = (view.minimumWidth(), view.maximumWidth())
    original_sizes = editor.description_field.sizes()
    for _ in range(3):
        editor._presentation.focus_button.click()
        qtbot.wait(10)
        assert controller.active is editor
        assert editor.inspector.isHidden()
        surface = editor._focus_surface
        available = surface.width() - 24
        assert view.width() == view.minimumWidth() == view.maximumWidth()
        assert view.width() <= available
        surface.toc_button.click()
        surface.toc_button.click()
        surface.exit_button.click()
        qtbot.wait(10)
        assert controller.active is None
        assert not editor.inspector.isHidden()
        assert (view.minimumWidth(), view.maximumWidth()) == original_limits
        assert editor.description_field.sizes() == original_sizes
        assert not editor.has_unsaved_changes()


def test_keyboard_navigation_keeps_destination_focus(focus_setup, qtbot):
    from PySide6.QtWidgets import QLineEdit

    window, editor, controller = focus_setup
    project = window.workspace.panel("project")
    field = QLineEdit(project)
    field.show()
    controller.enter(editor)
    field.setFocus()
    qtbot.wait(10)
    assert controller.active is None
    assert field.hasFocus()
