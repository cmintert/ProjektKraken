"""Management dialog for Base and dated vector geometry states."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.gui.widgets.compact_date_widget import CompactDateWidget


class FeatureGeometryStatesDialog(QDialog):
    """Let the user choose an edit, retime, or delete state intent."""

    def __init__(
        self,
        feature_label: str,
        states: list[dict[str, Any]],
        calendar_converter: Any = None,
        parent: Any = None,
    ) -> None:
        """Initialize the feature-geometry states dialog."""
        super().__init__(parent)
        self.setWindowTitle("Manage Geometry States")
        self.setMinimumWidth(420)
        self._states = {str(state["id"]): state for state in states}
        self._calendar_converter = calendar_converter
        self.selected_action: tuple[str, str | None, float | None] | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(feature_label))
        self.state_list = QListWidget(self)
        base_item = QListWidgetItem("Base Geometry")
        base_item.setData(Qt.ItemDataRole.UserRole, None)
        self.state_list.addItem(base_item)
        for state in sorted(states, key=lambda item: float(item["effective_date"])):
            lore_date = float(state["effective_date"])
            label = (
                calendar_converter.format_date(lore_date)
                if calendar_converter is not None
                else f"Lore day {lore_date:g}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(state["id"]))
            self.state_list.addItem(item)
        self.state_list.setCurrentRow(0)
        layout.addWidget(self.state_list)

        actions = QHBoxLayout()
        edit_button = QPushButton("Edit Geometry", self)
        date_button = QPushButton("Change Date", self)
        delete_button = QPushButton("Delete", self)
        close_button = QPushButton("Close", self)
        edit_button.clicked.connect(self._edit)
        date_button.clicked.connect(self._change_date)
        delete_button.clicked.connect(self._delete)
        close_button.clicked.connect(self.reject)
        actions.addWidget(edit_button)
        actions.addWidget(date_button)
        actions.addWidget(delete_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _selected_state_id(self) -> str | None:
        item = self.state_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item and item.data(
            Qt.ItemDataRole.UserRole
        ) is not None else None

    def _edit(self) -> None:
        state_id = self._selected_state_id()
        self.selected_action = (
            "edit_base" if state_id is None else "edit_state",
            state_id,
            None,
        )
        self.accept()

    def _change_date(self) -> None:
        state_id = self._selected_state_id()
        if state_id is None:
            QMessageBox.information(self, "Base Geometry", "Base Geometry has no date.")
            return
        state = self._states[state_id]
        dialog = QDialog(self)
        dialog.setWindowTitle("Change Geometry State Date")
        layout = QVBoxLayout(dialog)
        date_input = CompactDateWidget(dialog)
        if self._calendar_converter is not None:
            date_input.set_calendar_converter(self._calendar_converter)
        date_input.set_value(float(state["effective_date"]))
        layout.addWidget(date_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.selected_action = ("move_state", state_id, date_input.get_value())
            self.accept()

    def _delete(self) -> None:
        state_id = self._selected_state_id()
        if state_id is None:
            QMessageBox.information(
                self, "Base Geometry", "Base Geometry cannot be deleted."
            )
            return
        if QMessageBox.question(
            self,
            "Delete Geometry State",
            "Delete this dated geometry state?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.selected_action = ("delete_state", state_id, None)
        self.accept()
