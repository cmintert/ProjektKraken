"""Counted, read-only fact rows with a local disclosure."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper


@dataclass(frozen=True)
class FactSection:
    """Already formatted facts; no retrieval or domain decisions live here."""

    title: str
    rows: tuple[str, ...]
    hint: str = ""


class ContextFactSection(QWidget):
    """Keep each fact distinct and reveal all loaded rows on request."""

    expansion_changed = Signal()
    PREVIEW_ROWS = 3

    def __init__(
        self,
        section: FactSection,
        browser: QTextBrowser,
        parent: QWidget | None = None,
    ) -> None:
        """Create a counted heading and a keyboard-accessible disclosure."""
        super().__init__(parent)
        self.section = section
        layout = QVBoxLayout(self)
        StyleHelper.apply_compact_spacing(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.heading = QLabel(f"{section.title} ({len(section.rows)})", self)
        self.heading.setWordWrap(True)
        font = self.heading.font()
        font.setBold(True)
        self.heading.setFont(font)
        layout.addWidget(self.heading)
        self.hint = QLabel(section.hint, self)
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(section.hint))
        layout.addWidget(self.hint)
        self.browser = browser
        layout.addWidget(browser)
        self.disclosure = declare_inspection(
            QToolButton(self),
            "context-section-show-all|authoring.tags|help-context-section-show-all",
        )
        self.disclosure.setCheckable(True)
        self.disclosure.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disclosure.setToolTip("Show every loaded entry in this section")
        self.disclosure.setVisible(len(section.rows) > self.PREVIEW_ROWS)
        self.disclosure.toggled.connect(self.update_label)
        self.disclosure.toggled.connect(self.expansion_changed)
        layout.addWidget(self.disclosure)
        self.update_label()

    def set_section(self, section: FactSection) -> None:
        """Refresh loaded facts without replacing a focused disclosure control."""
        self.section = section
        self.heading.setText(f"{section.title} ({len(section.rows)})")
        self.hint.setText(section.hint)
        self.hint.setVisible(bool(section.hint))
        self.disclosure.setVisible(len(section.rows) > self.PREVIEW_ROWS)
        self.update_label()

    def visible_rows(self) -> tuple[str, ...]:
        """Return the preview or all loaded rows without changing the snapshot."""
        if self.disclosure.isChecked():
            return self.section.rows
        return self.section.rows[: self.PREVIEW_ROWS]

    def update_label(self) -> None:
        """Keep visible and accessible action wording aligned with its state."""
        expanded = self.disclosure.isChecked()
        self.disclosure.setText(
            "Show fewer" if expanded else f"Show all {len(self.section.rows)}"
        )
        self.disclosure.setAccessibleName(
            f"{self.section.title}: {self.disclosure.text()}"
        )

    def apply_theme(self, theme: dict) -> None:
        """Use neutral captions and the shared quiet action treatment."""
        self.heading.setStyleSheet(f"color: {theme['text_main']};")
        self.hint.setStyleSheet(f"color: {theme['supporting_caption']};")
        self.disclosure.setStyleSheet(StyleHelper.get_flat_tool_button_style())
