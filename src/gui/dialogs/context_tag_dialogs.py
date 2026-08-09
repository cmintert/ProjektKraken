"""Editor and recovery dialogs for session context tags."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton
from src.gui.widgets.tag_editor import TagEditorWidget

ModelIndex = QModelIndex | QPersistentModelIndex


class ContextTagEditorDialog(QDialog):
    """Edit the remembered tag set with existing tag autocomplete."""

    def __init__(
        self,
        tags: list[str],
        suggestions: list[str],
        *,
        active: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Context Tags")
        self.resize(560, 260)
        self.action = ""

        layout = QVBoxLayout(self)
        explanation = QLabel(
            "These tags are added to new interactive entities and events while "
            "the context is active."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.tag_editor = TagEditorWidget()
        self.tag_editor.load_tags(tags)
        self.tag_editor.update_suggestions(suggestions)
        layout.addWidget(self.tag_editor)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_cancel = StandardButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)

        self.btn_save = StandardButton("Save")
        self.btn_save.setVisible(not active)
        self.btn_save.clicked.connect(self._save)
        buttons.addWidget(self.btn_save)

        self.btn_primary = PrimaryButton("Apply" if active else "Save and Enable")
        self.btn_primary.clicked.connect(self._apply)
        buttons.addWidget(self.btn_primary)
        layout.addLayout(buttons)

    def tags(self) -> list[str]:
        """Return the edited set in display order."""
        return self.tag_editor.get_tags()

    def _save(self) -> None:
        self.action = "save"
        self.accept()

    def _apply(self) -> None:
        self.action = "apply"
        self.accept()


class ContextReviewModel(QAbstractTableModel):
    """Checkable table model for records affected by context tags."""

    HEADERS = ("", "Type", "Name", "Context tags", "Created")

    def __init__(self, records: list[dict[str, object]]) -> None:
        super().__init__()
        self.records = records
        self._checked = {row for row in range(len(records))}

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self.records):
            return None
        record = self.records[index.row()]
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            return (
                Qt.CheckState.Checked
                if index.row() in self._checked
                else Qt.CheckState.Unchecked
            )
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 1:
            return str(record["item_type"]).title()
        if index.column() == 2:
            return str(record["name"])
        if index.column() == 3:
            tags = record["tags"]
            return ", ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
        if index.column() == 4:
            created_at = record["created_at"]
            timestamp = (
                float(created_at) if isinstance(created_at, (int, float, str)) else 0.0
            )
            return datetime.fromtimestamp(timestamp).strftime(
                "%Y-%m-%d %H:%M"
            )
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(
        self,
        index: ModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if index.column() != 0 or role != Qt.ItemDataRole.CheckStateRole:
            return False
        if value == Qt.CheckState.Checked.value:
            self._checked.add(index.row())
        else:
            self._checked.discard(index.row())
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def set_all_checked(self, checked: bool) -> None:
        """Select or clear all visible records."""
        self._checked = set(range(len(self.records))) if checked else set()
        if self.records:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.records) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole],
            )

    def selected_keys(self) -> list[tuple[str, str]]:
        """Return checked item type/ID pairs."""
        return [
            (str(self.records[row]["item_type"]), str(self.records[row]["item_id"]))
            for row in sorted(self._checked)
        ]


class ContextTagReviewDialog(QDialog):
    """Review and selectively clean records tagged by the context system."""

    def __init__(
        self,
        records: list[dict[str, object]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Context Tags")
        self.resize(760, 440)
        self.action = ""
        self.navigation_target: tuple[str, str] | None = None

        layout = QVBoxLayout(self)
        explanation = QLabel(
            "Remove only the tags originally added by the active context. "
            "Other tags are preserved."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.model = ContextReviewModel(records)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_record)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        selection_buttons = QHBoxLayout()
        self.btn_all = QPushButton("Select All")
        self.btn_all.clicked.connect(lambda: self.model.set_all_checked(True))
        selection_buttons.addWidget(self.btn_all)
        self.btn_none = QPushButton("Select None")
        self.btn_none.clicked.connect(lambda: self.model.set_all_checked(False))
        selection_buttons.addWidget(self.btn_none)
        selection_buttons.addStretch(1)
        layout.addLayout(selection_buttons)

        buttons = QHBoxLayout()
        self.btn_clear = QPushButton("Clear Review History")
        self.btn_clear.clicked.connect(self._clear)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch(1)
        self.btn_close = StandardButton("Close")
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_close)
        self.btn_cleanup = PrimaryButton("Remove Context Tags")
        self.btn_cleanup.clicked.connect(self._cleanup)
        buttons.addWidget(self.btn_cleanup)
        layout.addLayout(buttons)

    def selected_keys(self) -> list[tuple[str, str]]:
        return self.model.selected_keys()

    def _cleanup(self) -> None:
        if not self.selected_keys():
            return
        self.action = "cleanup"
        self.accept()

    def _clear(self) -> None:
        self.action = "clear"
        self.accept()

    def _open_record(self, index: ModelIndex) -> None:
        record = self.model.records[index.row()]
        self.navigation_target = (
            str(record["item_type"]),
            str(record["item_id"]),
        )
        self.action = "navigate"
        self.accept()
