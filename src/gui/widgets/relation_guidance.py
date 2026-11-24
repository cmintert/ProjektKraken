"""Shared Qt inputs and read-only guidance for relation drafts."""

from collections.abc import Iterable
from html import escape
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSignalBlocker,
    Qt,
)
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.relation_guidance import relation_hint, type_suggestions
from src.core.relation_vocabulary import RelationWording, Vocabulary, resolve_wording
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.standard_buttons import StandardButton

_SEARCH_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class _SuggestionModel(QAbstractListModel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.rows: list[tuple[str, str]] = []

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        key, label = self.rows[index.row()]
        if role in (Qt.ItemDataRole.UserRole, Qt.ItemDataRole.EditRole):
            return key
        if role == Qt.ItemDataRole.DisplayRole:
            return label
        if role == _SEARCH_ROLE:
            return f"{key}\n{label}"
        return None

    def replace(self, rows: list[tuple[str, str]]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class _KeyCompleter(QCompleter):
    def pathFromIndex(self, index: QModelIndex | QPersistentModelIndex) -> str:  # noqa: N802
        return str(index.data(Qt.ItemDataRole.UserRole) or "")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        popup = self.popup()
        if (
            popup is not None
            and popup.isVisible()
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and self._popup_key(popup, event.key())
        ):
            return True
        return super().eventFilter(watched, event)

    def _popup_key(self, popup: QAbstractItemView, key: int) -> bool:
        if key == Qt.Key.Key_Escape:
            popup.hide()
            return True
        index = popup.currentIndex()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            count = self.completionModel().rowCount()
            if count:
                step = 1 if key == Qt.Key.Key_Down else -1
                row = (
                    (index.row() + step) % count
                    if index.isValid()
                    else (0 if step == 1 else count - 1)
                )
                popup.setCurrentIndex(self.completionModel().index(row, 0))
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            popup.hide()
            if index.isValid():
                self.activated.emit(self.pathFromIndex(index))
            return True
        return False


class RelationTypeField(ScrollSafeComboBox):
    """Search captions and keys while keeping literal edits in the text field."""

    def __init__(self) -> None:
        """Configure an editable field with exact-key completion."""
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._suggestions = _SuggestionModel(self)
        self.setModel(self._suggestions)
        completer = _KeyCompleter(self._suggestions, self)
        completer.setCompletionRole(_SEARCH_ROLE)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(completer)
        completer.activated.connect(self.setEditText)

    def set_suggestions(
        self,
        keys: Iterable[str],
        vocabulary: Vocabulary,
        source_kind: str = "",
        target_kind: str = "",
    ) -> None:
        """Refresh choices without committing a choice or changing the draft."""
        rows = type_suggestions(keys, vocabulary, source_kind, target_kind)
        if rows == self._suggestions.rows:
            return
        field = self.lineEdit()
        assert field is not None
        value, cursor = field.text(), field.cursorPosition()
        start = field.selectionStart()
        length = len(field.selectedText().encode("utf-16-le")) // 2
        with QSignalBlocker(self), QSignalBlocker(field):
            self._suggestions.replace(rows)
            self.setCurrentIndex(self.findData(value))
            field.setText(value)
            if start >= 0 and cursor == start:
                field.setSelection(start + length, -length)
            elif start >= 0:
                field.setSelection(start, length)
            else:
                field.setCursorPosition(cursor)


class RelationGuide(QWidget):
    """Show a single perspective at a time without editing the assertion."""

    def __init__(self) -> None:
        """Compose the preview, perspective button and optional guidance."""
        super().__init__()
        self.preview = self._label()
        self._apply_theme()
        connect_theme(self, self._apply_theme)
        self.preview.setAccessibleName("Relation wording preview")
        self.hint = self._label()
        self.hint.setAccessibleName("Relation type guidance")
        self.other = declare_inspection(
            StandardButton("View from other entry"),
            "relation-preview-other-entry|relations.create|help-inspect-relation-preview-other-entry",
        )
        self.other.clicked.connect(self._swap)
        layout = QVBoxLayout(self)
        StyleHelper.apply_no_margins(layout)
        layout.addWidget(self.preview)
        layout.addWidget(self.other, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.hint)
        self._alternate = False
        self._assertions: tuple[RelationWording, RelationWording] | None = None
        self._names = ("", "")

    @staticmethod
    def _label() -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        return label

    def _apply_theme(self, *_args: object) -> None:
        self.preview.setStyleSheet(StyleHelper.get_preview_label_style())

    def set_draft(
        self,
        relation: dict[str, Any],
        vocabulary: Vocabulary,
        source_kind: str,
        target_kind: str,
        *,
        incoming: bool = False,
    ) -> RelationWording:
        """Recompute both views for the same proposed canonical endpoints."""
        primary = resolve_wording(relation, vocabulary, incoming=incoming)
        self._assertions = (
            primary,
            resolve_wording(relation, vocabulary, incoming=not incoming),
        )
        names = (relation["source_name"], relation["target_name"])
        self._names = names[::-1] if incoming else names
        has_alternate = all(self._names) and bool(relation["rel_type"])
        self.other.setVisible(has_alternate)
        if not has_alternate:
            self._alternate = False
        hint = relation_hint(relation["rel_type"], vocabulary, source_kind, target_kind)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        self.other.setAccessibleDescription(hint)
        self._render()
        return primary

    def _swap(self) -> None:
        self._alternate = not self._alternate
        self._render()

    def _render(self) -> None:
        if self._assertions is None:
            return
        if not all(self._names):
            self.preview.setText("Choose an existing target to preview the relation.")
            self.preview.setAccessibleDescription("")
            return
        wording = self._assertions[self._alternate]
        self.preview.setText(wording.sentence or wording.assertion)
        viewed = self._names[self._alternate]
        other = self._names[not self._alternate]
        self.preview.setAccessibleDescription(f"Viewed from {viewed}")
        caption = f"View from {other}"
        metrics = self.other.fontMetrics()
        chrome = self.other.sizeHint().width() - metrics.horizontalAdvance(
            self.other.text()
        )
        self.other.setText(
            metrics.elidedText(
                caption, Qt.TextElideMode.ElideRight, max(0, self.width() - chrome)
            )
        )
        self.other.setAccessibleName(caption)
        self.other.setToolTip(f"<p>{escape(caption)}</p>")

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Fit the perspective label to the available preview width."""
        super().resizeEvent(event)
        self._render()
