"""Delivered-key checks for panel-local navigation and explicit source edits."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.core.workspaces import BUILTIN_WORKSPACES, workspace_default
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.gui.workspace.focus_navigation import FocusNavigationController
from src.gui.workspace.workspace_shell import WorkspaceShell
from tests.unit import test_focus_writing, test_production_workspace

production_window = test_production_workspace.main_window
writing_setup = test_focus_writing.focus_setup

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def production(production_window):
    yield production_window


@pytest.fixture
def navigation(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    layout = QVBoxLayout(window)
    shell = WorkspaceShell(window)
    layout.addWidget(shell)
    shell.activity_bar.configure_workspaces()
    shell.activity_bar.set_entries([("overview", "Overview")], "overview")
    for identifier, zone in (
        ("project", "left"),
        ("entity", "center"),
        ("event", "center"),
        ("map", "center"),
        ("graph", "center"),
        ("longform", "center"),
        ("analysis", "right"),
        ("ai_search", "right"),
        ("timeline", "bottom"),
        ("history", "bottom"),
    ):
        panel = QWidget()
        body = QVBoxLayout(panel)
        body.addWidget(QLineEdit(identifier))
        if identifier in ("entity", "event"):
            writing = WikiTextEdit()
            writing.set_wiki_text("A paragraph")
            body.addWidget(writing)
        body.addWidget(QPushButton("Last control"))
        shell.register_panel(identifier, identifier.title(), panel, zone)
    exit_focus = Mock()
    controller = FocusNavigationController(shell, lambda: None, exit_focus, window)
    menu = QMenu(window)
    controller.install_actions(menu)
    window.addActions(menu.actions())
    window.resize(1600, 900)
    window.show()
    shell.apply_layout(workspace_default("overview"))
    window.activateWindow()
    qtbot.wait(10)
    return window, shell, controller, exit_focus


@pytest.mark.parametrize("forward", [True, False])
@pytest.mark.parametrize("preset", [item.id for item in BUILTIN_WORKSPACES])
def test_tab_cycles_active_region_without_edits(navigation, qtbot, preset, forward):
    _, shell, controller, _ = navigation
    shell.apply_layout(workspace_default(preset))
    shell.show_panel("entity")
    region = shell.panel_zone("entity")
    root = shell.panes[region]
    targets = controller.targets(root)
    writing = shell.panel("entity").findChild(WikiTextEdit)
    view = writing.editor
    cursor = view.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    before = (
        writing.get_wiki_text(),
        cursor.position(),
        cursor.anchor(),
        view.document().isModified(),
        view.document().availableUndoSteps(),
    )
    index = 0 if forward else len(targets) - 1
    targets[index].setFocus()
    for _ in range(len(targets) + 1):
        qtbot.keyClick(
            QApplication.focusWidget(),
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.NoModifier
            if forward
            else Qt.KeyboardModifier.ShiftModifier,
        )
        index = (index + (1 if forward else -1)) % len(targets)
        assert QApplication.focusWidget() is targets[index], (
            index,
            [(type(w).__name__, w.objectName(), id(w)) for w in targets],
            [
                (type(w).__name__, w.objectName(), id(w))
                for w in controller.targets(root)
            ],
        )
    cursor = view.textCursor()
    assert before == (
        writing.get_wiki_text(),
        cursor.position(),
        cursor.anchor(),
        view.document().isModified(),
        view.document().availableUndoSteps(),
    )
    assert shell.active_panel(region) == "entity"


def test_f6_cycles_visible_regions_and_remembers_control(navigation, qtbot):
    _, shell, controller, exit_focus = navigation
    last = shell.panel("entity").findChildren(QPushButton)[-1]
    last.setFocus()
    for region in ("right", "bottom", "rail", "left", "center"):
        qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_F6)
        assert controller._region_for(QApplication.focusWidget()) == region
    assert QApplication.focusWidget() is last
    assert exit_focus.call_count == 5
    shell.hide_zone("right")
    qtbot.keyClick(last, Qt.Key.Key_F6)
    assert controller._region_for(QApplication.focusWidget()) == "bottom"
    qtbot.keyClick(
        QApplication.focusWidget(), Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier
    )
    assert QApplication.focusWidget() is last


def test_hidden_disabled_and_inactive_controls_are_excluded(navigation, qtbot):
    _, shell, controller, _ = navigation
    panel = shell.panel("entity")
    hidden = QLineEdit(panel)
    panel.layout().addWidget(hidden)
    hidden.hide()
    disabled = panel.findChild(QLineEdit)
    disabled.setEnabled(False)
    root = shell.panes["center"]
    targets = controller.targets(root)
    assert hidden not in targets and disabled not in targets
    assert not any(shell.panel("event").isAncestorOf(item) for item in targets)
    shell.move_panel("entity", "right")
    shell.show_panel("entity")
    last = controller.targets(shell.panes["right"])[-1]
    last.setFocus()
    qtbot.keyClick(last, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is controller.targets(shell.panes["right"])[0]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("source", [False, True])
def test_completion_tab_dismisses_without_accepting(navigation, qtbot, reverse, source):
    _, shell, controller, _ = navigation
    view = shell.panel("entity").findChild(WikiTextEdit).editor
    view.set_wiki_text("[[Al" if source else "Paragraph")
    view.set_completer(items=[("ada", "Alpha", "entity")])
    view.setFocus()
    before = view.toPlainText()
    completer = view._completer
    completer.setCompletionPrefix("Al")
    completer.complete()
    qtbot.waitUntil(lambda: completer.popup().isVisible())
    qtbot.keyClick(
        view,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.ShiftModifier
        if reverse
        else Qt.KeyboardModifier.NoModifier,
    )
    assert not completer.popup().isVisible()
    assert view.toPlainText() == before
    assert QApplication.focusWidget() is not view
    assert controller._region_for(QApplication.focusWidget()) == "center"


def test_completion_enter_still_accepts(navigation, qtbot):
    _, shell, _, _ = navigation
    view = shell.panel("entity").findChild(WikiTextEdit).editor
    view.set_wiki_text("[[Al")
    view.moveCursor(QTextCursor.MoveOperation.End)
    view.set_completer(items=[("ada", "Alpha", "entity")])
    view.setFocus()
    completer = view._completer
    completer.setCompletionPrefix("Al")
    completer.complete()
    completer.popup().setCurrentIndex(completer.completionModel().index(0, 0))
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert "Alpha" in view.toPlainText()


def test_modal_and_help_keep_keyboard_ownership(navigation, qtbot):
    window, shell, _, exit_focus = navigation
    dialog = QDialog(window)
    layout = QVBoxLayout(dialog)
    first, second = QLineEdit(), QLineEdit()
    layout.addWidget(first)
    layout.addWidget(second)
    dialog.setModal(True)
    dialog.show()
    dialog.activateWindow()
    qtbot.wait(5)
    first.setFocus()
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    assert second.hasFocus()
    qtbot.keyClick(second, Qt.Key.Key_F6)
    assert exit_focus.call_count == 0
    dialog.close()
    field = shell.panel("entity").findChild(QLineEdit)
    field.setProperty("krakenHelpWindow", True)
    field.setFocus()
    qtbot.keyClick(field, Qt.Key.Key_F6)
    assert exit_focus.call_count == 0


@pytest.mark.parametrize("reverse", [False, True])
def test_source_indentation_one_undo_and_selection_direction(qtbot, reverse):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    writing.set_wiki_text("- first 😀\n- second\nlast")
    view = writing.editor
    assert view._view_mode == "source"
    cursor = view.textCursor()
    end = view.document().findBlockByNumber(2).position()
    cursor.setPosition(end if reverse else 0)
    cursor.setPosition(0 if reverse else end, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    actions = writing.toolbar_presentation.source_actions
    actions.refresh()
    before = writing.get_wiki_text()
    actions.indent.trigger()
    assert view.toPlainText() == "    - first 😀\n    - second\nlast"
    assert (view.textCursor().position() < view.textCursor().anchor()) == reverse
    selection = QTextCursor(view.textCursor())
    view.undo()
    assert writing.get_wiki_text() == before
    view.redo()
    view.setTextCursor(selection)
    actions.outdent.trigger()
    assert writing.get_wiki_text() == before


def test_source_commands_disabled_in_rich_and_readonly(qtbot):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    actions = writing.toolbar_presentation.source_actions
    for text, readonly in (("Paragraph", False), ("- source", True)):
        writing.set_wiki_text(text)
        writing.setReadOnly(readonly)
        actions.refresh()
        assert not any(
            a.isEnabled() for a in (actions.indent, actions.outdent, actions.insert_tab)
        )


def test_table_delegate_retains_commit_and_cell_navigation(navigation, qtbot):
    _, shell, _, _ = navigation
    panel = shell.panel("entity")
    table = QTableWidget(1, 2)
    panel.layout().insertWidget(0, table)
    table.setItem(0, 0, QTableWidgetItem("before"))
    table.setItem(0, 1, QTableWidgetItem("next"))
    table.setCurrentCell(0, 0)
    table.editItem(table.item(0, 0))
    editor = table.findChild(QLineEdit)
    editor.setFocus()
    qtbot.keyClicks(editor, "changed")
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    assert table.item(0, 0).text() == "changed"
    assert table.currentColumn() == 1


def test_production_navigation_keeps_workspace_and_draft(production, qtbot):
    from src.core.entities import Entity

    main_window = production
    editor = main_window.entity_editor
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(editor.gallery, "set_owner", Mock())
        editor.load_entity(
            Entity(name="Draft", type="character", description="Paragraph")
        )
    main_window.show()
    main_window.activateWindow()
    main_window.workspace.show_panel("entity")
    qtbot.wait(10)
    view = editor.desc_edit.editor
    view.setFocus()
    qtbot.keyClicks(view, "draft ")
    before = editor.desc_edit.get_wiki_text()
    active = main_window.workspace_coordinator.active_id
    qtbot.keyClick(view, Qt.Key.Key_Tab)
    assert editor.desc_edit.get_wiki_text() == before
    assert editor.has_unsaved_changes()
    assert main_window.workspace_coordinator.active_id == active
    assert main_window.workspace.panes["center"].isAncestorOf(
        QApplication.focusWidget()
    )
    editor.set_dirty(False)


def test_focus_writing_owns_tab_and_f6_exits(writing_setup, qtbot):
    window, editor, focus = writing_setup
    navigation = FocusNavigationController(
        window.workspace,
        lambda: focus.active._focus_surface if focus.active else None,
        lambda: focus.exit(restore_focus=False),
        window,
    )
    menu = QMenu(window)
    navigation.install_actions(menu)
    window.addActions(menu.actions())
    window.activateWindow()
    focus.enter(editor)
    qtbot.wait(5)
    surface = editor._focus_surface
    targets = navigation.targets(surface)
    targets[-1].setFocus()
    qtbot.keyClick(targets[-1], Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is targets[0]
    assert focus.active is editor
    qtbot.keyClick(targets[0], Qt.Key.Key_F6)
    assert focus.active is None
    assert navigation._region_for(QApplication.focusWidget()) == "left"


def test_layout_restore_close_and_collapsed_region(navigation, qtbot):
    _, shell, controller, _ = navigation
    layout = shell.capture_layout()
    field = shell.panel("entity").findChild(QLineEdit)
    field.setFocus()
    shell.close_panel("entity")
    qtbot.wait(5)
    assert controller._region_for(QApplication.focusWidget()) == "center"
    assert not field.isVisible()
    shell.apply_layout(layout)
    shell.show_panel("entity")
    qtbot.wait(5)
    shell.horizontal_splitter.setSizes([0, 1000, 300])
    assert not controller.targets(shell.panes["left"])
    controller._focus_region("rail")
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_F6)
    assert controller._region_for(QApplication.focusWidget()) == "center"


def test_layout_move_retains_a_valid_restored_focus(navigation, qtbot):
    _, shell, _, _ = navigation
    field = shell.panel("entity").findChild(QLineEdit)
    field.setFocus()
    shell.move_panel("entity", "right")
    shell.show_panel("entity")
    # WorkspaceCoordinator restores the origin after applying a layout.
    field.setFocus()
    qtbot.wait(5)
    assert QApplication.focusWidget() is field


@pytest.mark.parametrize(
    "source", ["\talpha\n  beta\ngamma\n- tail", "- alpha\n| x | y |"]
)
def test_explicit_source_edits_and_literal_tab(qtbot, source):
    writing = WikiTextEdit()
    qtbot.addWidget(writing)
    writing.set_wiki_text(source)
    view = writing.editor
    actions = writing.toolbar_presentation.source_actions
    actions.refresh()
    cursor = view.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    view.setTextCursor(cursor)
    actions.outdent.trigger()
    if source.startswith("\t"):
        assert view.toPlainText() == "alpha\nbeta\ngamma\n- tail"
        view.undo()
        assert view.toPlainText() == source
    view.moveCursor(QTextCursor.MoveOperation.End)
    actions.insert_tab.trigger()
    assert view.toPlainText().endswith("\t")
    view.undo()
    assert view.toPlainText() == source


def test_tab_reaches_fields_below_scroll_viewport(navigation, qtbot):
    _, shell, controller, _ = navigation
    panel = shell.panel("entity")
    scroll = QScrollArea()
    content = QWidget()
    layout = QVBoxLayout(content)
    first, last = QLineEdit("first"), QLineEdit("last")
    layout.addWidget(first)
    layout.addSpacing(1000)
    layout.addWidget(last)
    scroll.setWidget(content)
    scroll.setWidgetResizable(True)
    panel.layout().insertWidget(0, scroll)
    qtbot.wait(5)
    assert last in controller.targets(shell.panes["center"])
    first.setFocus()
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    assert last.hasFocus()
    assert scroll.verticalScrollBar().value() > 0


@pytest.mark.parametrize("operation", ["indent", "outdent", "insert_tab"])
def test_source_command_returns_text_ownership_for_keyboard_undo(
    navigation, qtbot, operation
):
    _, shell, _, _ = navigation
    writing = shell.panel("entity").findChild(WikiTextEdit)
    writing.set_wiki_text("    - list")
    actions = writing.toolbar_presentation.source_actions
    actions.refresh()
    writing.toolbar_presentation._menu_buttons[0].setFocus()
    getattr(actions, operation).trigger()
    assert writing.editor.hasFocus()
    assert writing.get_wiki_text() != "    - list"
    qtbot.keyClick(
        QApplication.focusWidget(), Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
    )
    assert writing.get_wiki_text() == "    - list"


@pytest.mark.parametrize(
    "theme",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_theme_and_narrow_focus_preserve_writing(
    navigation, qtbot, qapp, monkeypatch, tmp_path, theme
):
    window, shell, controller, _ = navigation
    manager = ThemeManager()
    original = qapp.styleSheet()
    original_font = qapp.font()
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
        qapp.setFont(QFont("Segoe UI", 10))
    monkeypatch.setattr(
        manager,
        "_qss_template",
        Path("src/resources/main.qss").read_text(encoding="utf-8"),
    )
    writing = shell.panel("entity").findChild(WikiTextEdit)
    before = writing.get_wiki_text()
    try:
        manager.set_theme(theme, persist=False)
        for width in (1600, 1280):
            window.resize(width, 900)
            shell.horizontal_splitter.setSizes([270, 360, width - 630])
            qtbot.wait(5)
            writing.editor.setFocus()
            qtbot.keyClick(writing.editor, Qt.Key.Key_Tab)
            assert controller._region_for(QApplication.focusWidget()) == "center"
            assert writing.get_wiki_text() == before
            assert window.grab().save(str(tmp_path / f"{theme}-{width}.png"))
    finally:
        qapp.setStyleSheet(original)
        qapp.setFont(original_font)
