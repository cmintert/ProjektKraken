"""Focus-independent shortcut tests for trajectory edit sessions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QTextEdit, QWidget

from src.app.main_window import GlobalShortcutFilter


@pytest.mark.ci_fast
@pytest.mark.parametrize("editor_type", [QLineEdit, QTextEdit])
def test_delivered_enter_respects_text_focus(qapp, qtbot, editor_type):
    """Contract 2: real key delivery must not commit an unrelated map edit."""
    window = _Window()
    editor = editor_type()
    qtbot.addWidget(editor)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]
    qapp.installEventFilter(shortcut_filter)
    try:
        editor.show()
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        qtbot.keyClicks(editor, "Draft")
        qtbot.keyClick(editor, Qt.Key.Key_Return)
        window.trajectory_edit.apply.assert_not_called()
        text = editor.text() if isinstance(editor, QLineEdit) else editor.toPlainText()
        assert text == ("Draft" if isinstance(editor, QLineEdit) else "Draft\n")
    finally:
        qapp.removeEventFilter(shortcut_filter)


@pytest.mark.ci_fast
def test_delivered_escape_cancels_innermost_map_operation(qapp, qtbot):
    """Contract 2: Escape leaves the containing trajectory session intact."""
    window = _Window()
    window.trajectory_edit.is_date_editing = True
    widget = QWidget()
    qtbot.addWidget(widget)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]
    qapp.installEventFilter(shortcut_filter)
    try:
        widget.show()
        qtbot.keyClick(widget, Qt.Key.Key_Escape)
        window.trajectory_edit.cancel_date_edit.assert_called_once()
        window.trajectory_edit.cancel.assert_not_called()
        window.trajectory_edit.apply.assert_not_called()
    finally:
        qapp.removeEventFilter(shortcut_filter)


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.trajectory_edit = SimpleNamespace(
            is_active=True,
            is_date_editing=False,
            is_equalization_previewing=False,
            cancel=MagicMock(),
            cancel_date_edit=MagicMock(),
            cancel_speed_equalization=MagicMock(),
            confirm_speed_equalization=MagicMock(),
            apply=MagicMock(),
            delete_selected_keyframe=MagicMock(),
        )
        self.app_coordinator = SimpleNamespace(
            trajectory_edit=self.trajectory_edit
        )


def _key(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        Qt.KeyboardModifier.NoModifier,
    )


def test_escape_cancels_when_focus_is_outside_map(qtbot):
    window = _Window()
    widget = QWidget()
    qtbot.addWidget(widget)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]

    handled = shortcut_filter.eventFilter(widget, _key(Qt.Key.Key_Escape))

    assert handled
    window.trajectory_edit.cancel.assert_called_once()


def test_escape_cancels_only_active_date_suboperation(qtbot):
    window = _Window()
    window.trajectory_edit.is_date_editing = True
    widget = QWidget()
    qtbot.addWidget(widget)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]

    handled = shortcut_filter.eventFilter(widget, _key(Qt.Key.Key_Escape))

    assert handled
    window.trajectory_edit.cancel_date_edit.assert_called_once()
    window.trajectory_edit.cancel.assert_not_called()


def test_enter_is_left_to_active_text_field(qtbot):
    window = _Window()
    editor = QLineEdit()
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]

    handled = shortcut_filter.eventFilter(editor, _key(Qt.Key.Key_Return))

    assert not handled
    window.trajectory_edit.apply.assert_not_called()


def test_escape_cancels_only_equalization_preview(qtbot):
    window = _Window()
    window.trajectory_edit.is_equalization_previewing = True
    widget = QWidget()
    qtbot.addWidget(widget)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]

    handled = shortcut_filter.eventFilter(widget, _key(Qt.Key.Key_Escape))

    assert handled
    window.trajectory_edit.cancel_speed_equalization.assert_called_once()
    window.trajectory_edit.cancel.assert_not_called()


def test_enter_confirms_equalization_preview_before_trajectory_apply(qtbot):
    window = _Window()
    window.trajectory_edit.is_equalization_previewing = True
    widget = QWidget()
    qtbot.addWidget(widget)
    shortcut_filter = GlobalShortcutFilter(window)  # type: ignore[arg-type]

    handled = shortcut_filter.eventFilter(widget, _key(Qt.Key.Key_Return))

    assert handled
    window.trajectory_edit.confirm_speed_equalization.assert_called_once()
    window.trajectory_edit.apply.assert_not_called()
