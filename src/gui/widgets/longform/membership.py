"""Inline selection of existing world content for a Longform document."""

from collections import Counter

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


class LongformMembershipWidget(QWidget):
    """Present snapshots and emit one membership intent without navigation."""

    add_requested = Signal(str, str)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a collapsed, keyboard-accessible existing-content chooser."""
        super().__init__(parent)
        self._items: list[tuple[str, str, str]] = []
        layout = QVBoxLayout(self)
        StyleHelper.apply_form_spacing(layout)
        caption = QLabel("Restore existing content to this document")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search entities and events…")
        self.search.setAccessibleName("Search existing content")
        layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setAccessibleName("Existing world content")
        self.results.setMaximumHeight(150)
        layout.addWidget(self.results)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add to document")
        self.add_button.setToolTip("Select an existing entity or event first")
        self.cancel_button = QPushButton("Cancel")
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._accept)
        self.results.itemActivated.connect(lambda _item: self._accept())
        self.results.currentRowChanged.connect(self._update_acceptance)
        self.add_button.clicked.connect(self._accept)
        self.cancel_button.clicked.connect(self.cancelled.emit)
        ThemeManager().theme_changed.connect(self._apply_theme)
        self._apply_theme()
        self.hide()

    def show_items(self, items: list[tuple[str, str, str]]) -> None:
        """Show identity-bearing snapshots; current membership is idempotent."""
        self._items = items
        self.search.clear()
        self._filter("")
        self.show()
        self.search.setFocus()

    def _filter(self, text: str) -> None:
        counts = Counter((table, name.casefold()) for table, _, name in self._items)
        self.results.clear()
        for table, row_id, name in self._items:
            if text.casefold() in name.casefold():
                kind = "Event" if table == "events" else "Entity"
                label = f"{name} · {kind}"
                if counts[table, name.casefold()] > 1:
                    label += f" · {row_id}"
                item = QListWidgetItem(label, self.results)
                item.setToolTip(f"{name} · {kind} · {row_id}")
                item.setData(Qt.ItemDataRole.UserRole, (table, row_id))
        self.notice.setText(
            "Content is added automatically. Add restores removed entries; "
            "existing entries stay in place."
            if self.results.count()
            else "No matching content. Create entries in Explorer, or try another search."
        )
        self._update_acceptance()

    def _update_acceptance(self, _row: int = -1) -> None:
        self.add_button.setEnabled(self.results.currentItem() is not None)

    def _accept(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            table, row_id = item.data(Qt.ItemDataRole.UserRole)
            self.add_requested.emit(table, row_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Cancel the local chooser without affecting inspector drafts."""
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.search.setStyleSheet(StyleHelper.get_input_field_style())
        self.results.setStyleSheet(
            StyleHelper.get_list_widget_style()
            + StyleHelper.get_item_view_selection_style("QListWidget")
        )
        self.add_button.setStyleSheet(StyleHelper.get_primary_button_style())
        self.cancel_button.setStyleSheet(StyleHelper.get_secondary_button_style())
