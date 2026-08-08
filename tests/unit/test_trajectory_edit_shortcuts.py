"""Focus-independent shortcut tests for trajectory edit sessions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget

from src.app.main_window import GlobalShortcutFilter


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.trajectory_edit = SimpleNamespace(
            is_active=True,
            cancel=MagicMock(),
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
