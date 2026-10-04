"""Presentation-only homes for independently splittable inspector sections."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.standard_buttons import StandardButton


class AuxiliarySectionHome(QWidget):
    """Move one live section between its embedded home and a split pane.

    The home and pane remain owned while detached. Neither relocation nor its
    placeholder emits authoring intent or reconstructs the content widget.
    """

    show_requested = Signal()
    return_requested = Signal()
    detached_changed = Signal(bool)

    def __init__(
        self, content: QWidget, title: str, parent: QWidget | None = None
    ) -> None:
        """Create a home, a reusable pane and visible return controls."""
        super().__init__(parent)
        self.content = content
        self.title = title
        self.detached = False
        self._layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(self._layout)
        self._layout.addWidget(content)
        content.show()
        self.placeholder = QWidget(self)
        placeholder_layout = QVBoxLayout(self.placeholder)
        StyleHelper.apply_no_margins(placeholder_layout)
        label = QLabel(f"{title} is open in another inspector pane.")
        label.setWordWrap(True)
        placeholder_layout.addWidget(label)
        actions = OverflowToolBar(self.placeholder)
        show = StandardButton("Show")
        show.setAccessibleName(f"Show {title}")
        show.clicked.connect(self.show_requested.emit)
        restore = StandardButton("Return here")
        restore.setAccessibleName(f"Return {title} here")
        restore.clicked.connect(self.return_requested.emit)
        actions.add_button(show, priority=10)
        actions.add_button(restore)
        placeholder_layout.addWidget(actions)
        self._layout.addWidget(self.placeholder)
        self.placeholder.hide()
        self.pane = QWidget(self)
        self._pane_layout = QVBoxLayout(self.pane)
        StyleHelper.apply_no_margins(self._pane_layout)
        return_button = StandardButton("Return here")
        return_button.setAccessibleName(f"Return {title} to its original section")
        return_button.clicked.connect(self.return_requested.emit)
        self._pane_layout.addWidget(return_button)
        self.pane.hide()

    def detach(self) -> None:
        """Install the same content in the already-inserted split pane."""
        if self.detached:
            return
        # Mark the relocation before touching ownership so a partial failure
        # can always restore the content through attach().
        self.detached = True
        self._layout.removeWidget(self.content)
        self._pane_layout.addWidget(self.content, 1)
        self.content.show()
        self.placeholder.show()
        self.detached_changed.emit(True)

    def attach(self) -> None:
        """Return content home without changing its document or data."""
        if not self.detached:
            return
        self._pane_layout.removeWidget(self.content)
        self._layout.insertWidget(0, self.content)
        self.content.show()
        self.placeholder.hide()
        self.pane.setParent(self)
        self.pane.hide()
        self.detached = False
        self.detached_changed.emit(False)
