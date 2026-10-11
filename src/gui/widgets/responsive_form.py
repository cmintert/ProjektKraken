"""Shared content-first form rows and explicit scrollable configuration pages."""

from PySide6.QtWidgets import QFormLayout, QFrame, QScrollArea, QVBoxLayout, QWidget


class ResponsiveFormLayout(QFormLayout):
    """Move a complete field below its label when the row cannot fit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Retain native form semantics with responsive long-row wrapping."""
        super().__init__(parent)
        self.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)


def scrollable_form_page(page: QWidget) -> QScrollArea:
    """Keep one existing configuration page accessible within dialog bounds."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(page)
    return scroll


def scroll_section_contents(section: QWidget) -> QScrollArea:
    """Keep a section's identity and live controls while scrolling its content."""
    existing = section.layout()
    if existing is None:
        raise ValueError("A scrollable section must already have a layout")
    page = QWidget()
    page.setLayout(existing)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    scroll = scrollable_form_page(page)
    layout.addWidget(scroll)
    return scroll
