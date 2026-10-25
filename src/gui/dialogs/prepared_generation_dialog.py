"""Read-only frozen prompt preview; emits preparation and generation intent."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.standard_buttons import StandardButton


class PreparedGenerationDialog(QDialog):
    """Display an immutable preview with an explicit stale/refresh boundary."""

    refresh_requested = Signal()
    generate_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the existing preview flow with explicit Generate and Refresh."""
        super().__init__(parent)
        self.setWindowTitle("Prompt Preview")
        self.resize(600, 500)
        layout = QVBoxLayout(self)
        self.status = QLabel("Preparing context…")
        self.status.setWordWrap(True)
        self.text = declare_inspection(
            QPlainTextEdit(),
            "prepared-generation-text|writing.ai|help-prepared-generation-text",
        )
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Exact prepared prompt")
        layout.addWidget(self.status)
        layout.addWidget(self.text)
        actions = OverflowToolBar()
        self.generate_button = declare_inspection(
            StandardButton("Generate"),
            "prepared-generation-generate-button|writing.ai|help-prepared-generation-generate-button",
        )
        self.refresh_button = declare_inspection(
            StandardButton("Refresh"),
            "prepared-generation-refresh-button|writing.ai|help-prepared-generation-refresh-button",
        )
        close = declare_inspection(
            StandardButton("Close"),
            "prepared-generation-close|writing.ai|help-prepared-generation-close",
        )
        self.generate_button.setEnabled(False)
        self.generate_button.setStyleSheet(StyleHelper.get_primary_button_style())
        for button in (self.refresh_button, close):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())
        self.generate_button.clicked.connect(self.generate_requested)
        self.refresh_button.clicked.connect(self.refresh_requested)
        close.clicked.connect(self.reject)
        for button in (self.generate_button, self.refresh_button, close):
            actions.add_button(button, pinned=button is self.generate_button)
        layout.addWidget(actions)
        self._close_button = close
        ThemeManager().theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.setStyleSheet(StyleHelper.get_dialog_base_style())
        self.generate_button.setStyleSheet(StyleHelper.get_primary_button_style())
        for button in (self.refresh_button, self._close_button):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())

    def invalidate(self) -> None:
        """Keep the reviewed text visible while preventing a stale send."""
        self.status.setText("Context changed. Choose Refresh before generating.")
        self.generate_button.setEnabled(False)

    def present(self, prompt: dict[str, str], caption: str) -> None:
        """Show the exact messages without interpretation or further lookups."""
        self.text.setPlainText(
            f"--- SYSTEM ---\n{prompt.get('system', '')}\n\n"
            f"--- USER ---\n{prompt.get('user', '')}"
        )
        self.status.setText(caption)
        self.generate_button.setEnabled(True)
