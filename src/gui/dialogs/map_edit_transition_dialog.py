"""Explicit resolution of a map draft before context replacement."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


class MapEditTransitionDialog(QDialog):
    """Present safe default and explicit apply/discard intent."""

    def __init__(
        self, reason: str, status: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        """Build a compact, wrapping decision surface."""
        super().__init__(parent)
        self.setWindowTitle("Unfinished map edit")
        self.setMinimumWidth(300)
        self.resize(420, 240)
        self.decision = "keep"
        layout = QVBoxLayout(self)
        label = QLabel(
            f"You have unfinished changes to {status['label']}.\n"
            f"Apply or discard them before you {reason}?",
            self,
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.apply_button = QPushButton("Apply", self)
        self.keep_button = QPushButton("Keep editing", self)
        self.discard_button = QPushButton("Discard", self)
        for button, role, decision in (
            (self.apply_button, "primary", "apply"),
            (self.keep_button, "secondary", "keep"),
            (self.discard_button, "destructive", "discard"),
        ):
            button.setStyleSheet(StyleHelper.get_action_role_style(role))
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, d=decision: self._choose(d))
            layout.addWidget(button)
        self.apply_button.setEnabled(bool(status["can_apply"]))
        if not status["can_apply"]:
            explanation = str(status["explanation"])
            self.apply_button.setToolTip(explanation)
            hint = QLabel(explanation, self)
            hint.setWordWrap(True)
            layout.addWidget(hint)
        self.keep_button.setDefault(True)
        self.keep_button.setFocus()
        ThemeManager().theme_changed.connect(self._apply_theme)

    def _apply_theme(self, _theme: dict[str, Any]) -> None:
        for button, role in (
            (self.apply_button, "primary"),
            (self.keep_button, "secondary"),
            (self.discard_button, "destructive"),
        ):
            button.setStyleSheet(StyleHelper.get_action_role_style(role))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Enter activates the focused decision; Escape retains the draft."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focused = self.focusWidget()
            if isinstance(focused, QPushButton) and focused.isEnabled():
                focused.click()
                event.accept()
                return
        super().keyPressEvent(event)

    def _choose(self, decision: str) -> None:
        self.decision = decision
        self.accept()


def decide_map_transition(reason: str, status: dict[str, Any], parent: QWidget) -> str:
    """Return intent and restore the originating focus on cancellation."""
    focused = QApplication.focusWidget()
    dialog = MapEditTransitionDialog(reason, status, parent)
    dialog.exec()
    if dialog.decision == "keep" and focused is not None and isValid(focused):
        focused.setFocus()
    return dialog.decision
