"""Component entry using standard themed controls and local keyboard ownership."""

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QWidget

from src.gui.widgets.event_offset_input import EventOffsetInput
from src.gui.widgets.wrapping_combo_box import WrappingComboBox


class CompoundOffsetControls(QWidget):
    """Render separate magnitudes and a shared earlier/later direction."""

    changed = Signal()

    def __init__(self, offset: dict[str, Any], parent: QWidget) -> None:
        """Hydrate without emitting authoring changes."""
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.direction = WrappingComboBox(self)
        self.direction.addItem("After endpoint (+)", 1)
        self.direction.addItem("Before endpoint (−)", -1)
        self.direction.setCurrentIndex(1 if offset.get("direction") == -1 else 0)
        self.years = EventOffsetInput(self)
        self.months = EventOffsetInput(self)
        self.days = EventOffsetInput(self)
        self.days.setRange(0, 1e12)
        for name, numeric in (("years", self.years), ("months", self.months)):
            numeric.setRange(0, 1e12)
            numeric.setValue(float(offset.get(name, 0)))
        self.days.setValue(float(offset.get("days", 0)))
        for caption, control in (
            ("Direction", self.direction),
            ("Years", self.years),
            ("Months", self.months),
            ("Days", self.days),
        ):
            control.setAccessibleName(f"Offset {caption.lower()}")
            form.addRow(caption, control)
        self.direction.currentIndexChanged.connect(self.changed)
        for control in (self.years, self.months, self.days):
            control.valueChanged.connect(self.changed)

    def offset(self) -> dict[str, Any]:
        """Collect detached magnitudes; calendar ownership stays with the caller."""
        return {
            "unit": "compound",
            "direction": self.direction.currentData(),
            "years": self.years.value(),
            "months": self.months.value(),
            "days": self.days.value(),
        }
