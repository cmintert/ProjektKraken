"""Compact authoring of an Event from Entity history."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.temporal_expression import expression_from_attributes
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.compact_date_widget import CompactDateWidget


class LifecycleEventDialog(QDialog):
    """Collect a name and explicitly authored date or unknown timing."""

    def __init__(
        self, name: str, converter: CalendarConverter | None, parent: QWidget
    ) -> None:
        """Build a date form without adopting the current playhead."""
        super().__init__(parent)
        self.setWindowTitle("Add historical event")
        self.event_data: dict = {}
        self.name_edit = declare_inspection(
            QLineEdit(name),
            "lifecycle-event-name|authoring.details|help-lifecycle-event",
        )
        self.name_edit.selectAll()
        self.date = CompactDateWidget(text_first=True)
        self.date.set_calendar_converter(converter)
        self.date.txt_date.clear()
        self.date.txt_date.setPlaceholderText("Enter a date")
        self.unknown = declare_inspection(
            QCheckBox("Date unknown"),
            "lifecycle-event-unknown|authoring.details|help-lifecycle-event",
        )
        self.unknown.toggled.connect(self.date.setDisabled)
        self.error = QLabel()
        self.error.setWordWrap(True)
        buttons = declare_inspection(
            QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel),
            "lifecycle-event-confirm|authoring.details|help-lifecycle-event",
        )
        buttons.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow("Event name", self.name_edit)
        layout.addRow("Event date", self.date)
        layout.addRow(self.unknown)
        layout.addRow(self.error)
        layout.addRow(buttons)

    def accept(self) -> None:
        """Validate explicit timing and retain its authored expression."""
        name = self.name_edit.text().strip()
        if not name:
            self.error.setText("Enter an event name.")
            return
        self.event_data = {"name": name, "lore_date": None}
        if not self.unknown.isChecked():
            if not self.date.txt_date.text().strip() or not self.date.commit_draft():
                self.error.setText("Enter a valid date or choose Date unknown.")
                return
            self.event_data["lore_date"] = self.date.get_value()
            expression = self.date.get_expression()
            if expression is not None:
                self.event_data["attributes"] = {
                    "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
                }
        super().accept()

    def restore_input(self, data: dict) -> None:
        """Restore the last submission after a rejected or cancelled operation."""
        self.name_edit.setText(data["name"])
        date = data["lore_date"]
        self.unknown.setChecked(date is None)
        if date is not None:
            self.date.set_value(date)
            expression = expression_from_attributes(data.get("attributes", {}))
            if expression is not None:
                self.date.set_expression(expression)
