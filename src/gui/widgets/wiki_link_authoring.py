"""Local, reversible linking of prose to existing entries."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import shiboken6
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from src.core.theme_manager import ThemeManager
from src.core.wiki_ast import NodeType, WikiASTParser, WikiNode
from src.core.wiki_markdown_grammar import requires_source_mode
from src.gui.utils.style_helper import StyleHelper

if TYPE_CHECKING:
    from src.gui.widgets.wiki_text_edit import WikiTextEditView


class EntryLinkPicker(QFrame):
    """Search identity-bearing snapshots without changing the writer's document."""

    chosen = Signal(str)
    cancelled = Signal()

    def __init__(
        self, view: WikiTextEditView, items: list[tuple[str, str, str]], search: str
    ) -> None:
        """Build a compact popup with explicit selection and acceptance."""
        super().__init__(view, Qt.WindowType.Popup)
        self.setObjectName("EntryLinkPicker")
        self._items = items
        self._accepted = False
        self._cancelled = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Link to an existing entry"))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search entries…")
        self.search.setAccessibleName("Search existing entries")
        self.results = QListWidget(self)
        self.results.setAccessibleName("Existing entries")
        self.notice = QLabel("Select an entry, then Link. No new entry is created.")
        self.notice.setWordWrap(True)
        layout.addWidget(self.search)
        layout.addWidget(self.results)
        layout.addWidget(self.notice)
        buttons = QHBoxLayout()
        self.link_button = QPushButton("Link", self)
        cancel = QPushButton("Cancel", self)
        buttons.addWidget(self.link_button)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.search.textChanged.connect(self._filter)
        self.results.currentRowChanged.connect(self._update_acceptance)
        self.results.itemActivated.connect(lambda _item: self.accept_choice())
        self.search.returnPressed.connect(self.accept_choice)
        self.link_button.clicked.connect(self.accept_choice)
        cancel.clicked.connect(self.close)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self.search.setText(search)
        self._filter(search)
        self.resize(350, 300)

    def _filter(self, text: str) -> None:
        counts = Counter(name.casefold() for _, name, _ in self._items)
        suffixes = Counter(
            (name.casefold(), item_id[-8:]) for item_id, name, _ in self._items
        )
        self.results.clear()
        for item_id, name, kind in self._items:
            if text.casefold() not in name.casefold():
                continue
            label = f"{name} · {kind.title()}"
            if counts[name.casefold()] > 1:
                suffix = item_id[-8:]
                label += (
                    f" · {item_id if suffixes[name.casefold(), suffix] > 1 else suffix}"
                )
            item = QListWidgetItem(label, self.results)
            item.setToolTip(f"{name} · {kind.title()} · {item_id}")
            item.setData(Qt.ItemDataRole.UserRole, item_id)
        self.notice.setText(
            "Select an entry, then Link. No new entry is created."
            if self.results.count()
            else "No matching entries. Try another search."
        )
        self._update_acceptance()

    def _update_acceptance(self, _row: int = -1) -> None:
        self.link_button.setEnabled(self.results.currentItem() is not None)

    def accept_choice(self) -> None:
        """Accept only an explicitly selected existing entry."""
        item = self.results.currentItem()
        if item is not None:
            self._accepted = True
            self.chosen.emit(str(item.data(Qt.ItemDataRole.UserRole)))
            self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Keep Enter/Escape owned by the local picker."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_choice()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Cancel once, including a window-manager dismissal."""
        self._cancel()
        super().closeEvent(event)
        self.deleteLater()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        """Qt popup outside-click dismissal hides rather than always closing."""
        self._cancel()
        super().hideEvent(event)
        self.deleteLater()

    def _cancel(self) -> None:
        if not self._accepted and not self._cancelled:
            self._cancelled = True
            self.cancelled.emit()

    def _apply_theme(self, _theme: dict | None = None) -> None:
        theme = ThemeManager().get_theme()
        self.setStyleSheet(
            f"QFrame#EntryLinkPicker {{ background: {theme['surface']}; "
            f"color: {theme['text_main']}; }}"
        )
        self.search.setStyleSheet(StyleHelper.get_input_field_style())
        self.results.setStyleSheet(StyleHelper.get_list_widget_style())
        for label in self.findChildren(QLabel):
            label.setStyleSheet(f"color: {theme['text_main']};")
        for button in self.findChildren(QPushButton):
            button.setStyleSheet(StyleHelper.get_secondary_button_style())


class WikiLinkAuthoring(QObject):
    """Own a local selection snapshot while the entry picker has focus."""

    def __init__(self, view: WikiTextEditView, notice: QLabel) -> None:
        """Bind authoring to one view without services or database access."""
        super().__init__(view)
        self.view = view
        self.notice = notice
        self.picker: EntryLinkPicker | None = None
        self._cursor = QTextCursor()
        self._revision = -1
        self._mode = ""
        self._scroll = 0
        view.textChanged.connect(self.cancel_stale)
        view.view_mode_changed.connect(self.cancel_stale)
        view.document_replacing.connect(self.cancel)

    def cancel(self) -> None:
        """Dismiss a picker before replacing its owning authoring context."""
        if self.picker is not None:
            self.picker.close()

    def selection_error(self) -> str:
        """Explain ranges that the existing link grammar cannot represent."""
        cursor = self.view.textCursor()
        label = cursor.selectedText()
        if any(char in label for char in "\n\r\u2028\u2029[]|"):
            return "Select words within one paragraph, without link syntax."
        if self.view.link_target_at_cursor():
            return "This text is already linked. Use Open link or Peek link."
        if self.view._view_mode == "rich":
            for position in range(cursor.selectionStart(), cursor.selectionEnd()):
                probe = QTextCursor(cursor.document())
                probe.setPosition(position)
                probe.movePosition(
                    QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
                )
                if probe.charFormat().isAnchor():
                    return "Select text that does not already contain a link."
        elif cursor.hasSelection():
            if requires_source_mode(cursor.block().text()):
                return "Select plain words in a supported Markdown paragraph."
            ast = WikiASTParser().parse(self.view.toPlainText())
            source = self.view.toPlainText().encode("utf-16-le")
            start = len(source[: cursor.selectionStart() * 2].decode("utf-16-le"))
            end = len(source[: cursor.selectionEnd() * 2].decode("utf-16-le"))
            if not self._within_text(ast, start, end):
                return "Select the words without their Markdown formatting marks."
        return ""

    @staticmethod
    def _within_text(node: WikiNode, start: int, end: int) -> bool:
        span = node.md_span
        if node.node_type == NodeType.TEXT and span is not None:
            return span.start <= start < end <= span.end
        return any(
            WikiLinkAuthoring._within_text(child, start, end) for child in node.children
        )

    def open_picker(self) -> None:
        """Capture selection before giving focus to the entry picker."""
        view = self.view
        if view.isReadOnly() or self.picker is not None:
            return
        error = self.selection_error()
        if error:
            self.notice.setText(error)
            self.notice.show()
            return
        self.notice.hide()
        self._cursor = QTextCursor(view.textCursor())
        self._revision = view.document().revision()
        self._mode = view._view_mode
        self._scroll = view.verticalScrollBar().value()
        items = [row for row in view._completion_items if row[0]]
        picker = EntryLinkPicker(view, items, self._cursor.selectedText())
        self.picker = picker
        picker.chosen.connect(self._accept)
        picker.cancelled.connect(self._cancel)
        point = view.viewport().mapToGlobal(view.cursorRect().bottomLeft())
        screen = view.screen().availableGeometry()
        picker.resize(min(350, screen.width()), min(300, screen.height()))
        point.setX(
            max(screen.left(), min(point.x(), screen.right() - picker.width() + 1))
        )
        point.setY(
            max(screen.top(), min(point.y(), screen.bottom() - picker.height() + 1))
        )
        picker.move(point)
        picker.show()
        picker.search.setFocus()

    def _is_current(self) -> bool:
        view = self.view
        return (
            shiboken6.isValid(view)
            and not view.isReadOnly()
            and self._cursor.document() == view.document()
            and self._revision == view.document().revision()
            and self._mode == view._view_mode
        )

    def cancel_stale(self) -> None:
        """Cancel after changes rather than applying to a relocated range."""
        if self.picker is not None and not self._is_current():
            self.picker.close()

    def _restore(self) -> None:
        if self._is_current():
            self.view.setTextCursor(self._cursor)
            self.view.verticalScrollBar().setValue(self._scroll)
            self.view.setFocus()

    def _cancel(self) -> None:
        self.picker = None
        self._restore()

    def _accept(self, item_id: str) -> None:
        self.picker = None
        row = next(
            (row for row in self.view._completion_items if row[0] == item_id), None
        )
        if not self._is_current() or row is None:
            if row is None:
                self.notice.setText(
                    "This entry is no longer available. Choose another entry."
                )
                self.notice.show()
            self._restore()
            return
        label = self._cursor.selectedText() if self._cursor.hasSelection() else row[1]
        if not label or any(char in label for char in "\n\r\u2028\u2029[]|"):
            self.notice.setText("This label cannot be represented as a wiki link.")
            self.notice.show()
            self._restore()
            return
        self.view.insert_entry_link(
            self._cursor, label, item_id, preserve_selection=True
        )
        self.view.setFocus()
