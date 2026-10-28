"""Presentation of a manual date or an Event endpoint, with explicit detachment."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.core.event_timing.definitions import EndpointDefinition
from src.core.temporal_context import TemporalResolutionContext
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.event_anchor_controls import EventAnchorControls
from src.gui.widgets.wrapping_combo_box import WrappingComboBox


class EventTimingSource(QWidget):
    """Own source controls; the coordinator owns calculation and persistence."""

    changed = Signal()

    def __init__(
        self, date: CompactDateWidget, side: str, parent: QWidget | None = None
    ) -> None:
        """Reuse the shared endpoint/offset controls without before/after semantics."""
        super().__init__(parent)
        self.date = date
        self._side = side
        self._context = TemporalResolutionContext()
        self._owner = ""
        self._loading = False
        self._replacement_required = False
        self._loaded_owner: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bindings = {
            "start": (
                "event-start-source|event.timing|help-inspect-event-start-source",
                "event-start-reference|event.timing|help-inspect-event-start-reference",
            ),
            "end": (
                "event-end-source|event.timing|help-inspect-event-end-source",
                "event-end-reference|event.timing|help-inspect-event-end-reference",
            ),
        }
        self.mode = declare_inspection(
            WrappingComboBox(self),
            bindings[side][0],
        )
        self.mode.addItem("Manual date", "manual")
        self.mode.addItem("Follow Event", "event")
        self.mode.setAccessibleName(f"{side.title()} date source")
        layout.addWidget(self.mode)
        self.events = declare_inspection(
            WrappingComboBox(self),
            bindings[side][1],
        )
        self.events.setAccessibleName(f"Event followed by {side}")
        layout.addWidget(self.events)
        self.options = EventAnchorControls(parent=self, calculated_only=True)
        self.options.use_event_help()
        layout.addWidget(self.options)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.events.currentIndexChanged.connect(self._event_changed)
        self.options.changed.connect(self._edited)
        self._show_mode()

    def _show_mode(self) -> None:
        followed = self.mode.currentData() == "event"
        self.events.setVisible(followed)
        self.options.setVisible(followed)
        self.date.setVisible(not followed)

    def _mode_changed(self) -> None:
        if self._loading:
            return
        if self.mode.currentData() == "manual":
            key = f"event:{self._owner}" + (":end" if self._side == "end" else "")
            bounds = self._context.anchors().get(key)
            exact = (
                bounds is not None
                and not bounds.error
                and bounds.hard_start is not None
                and bounds.hard_start == bounds.hard_end
            )
            if exact:
                assert bounds is not None and bounds.hard_start is not None
                self.date.set_value(bounds.hard_start)
            else:
                self.date.txt_date.clear()
                self.date.txt_date.setPlaceholderText(
                    "Enter a replacement date or uncertainty"
                )
                self._replacement_required = True
        else:
            self.options.set_anchor_id(str(self.events.currentData() or ""))
        self._show_mode()
        self._edited()

    def _event_changed(self) -> None:
        if not self._loading:
            self.options.set_anchor_id(str(self.events.currentData() or ""))
            self._edited()

    def _edited(self) -> None:
        if not self._loading:
            self.changed.emit()

    def set_context(self, context: TemporalResolutionContext, owner: str) -> None:
        """Refresh target names without altering source intent or typed dates."""
        self._context, self._owner = context, owner
        selected = self.events.currentData()
        self._loading = True
        self.events.blockSignals(True)
        self.events.clear()
        self.events.addItem("Choose an Event…", "")
        for event in sorted(context.events(), key=lambda item: item.name.casefold()):
            if event.id != owner:
                self.events.addItem(event.name, f"event:{event.id}")
        index = self.events.findData(selected)
        if selected and index < 0:
            self.events.addItem("Unavailable Event — reference preserved", selected)
            index = self.events.count() - 1
        self.events.setCurrentIndex(max(index, 0))
        self.events.blockSignals(False)
        self.options.set_context(context)
        self._loading = False

    def load(self, definition: EndpointDefinition) -> None:
        """Hydrate an authored source without converting it to a copied date."""
        self._loading = True
        self._replacement_required = False
        self.mode.setCurrentIndex(self.mode.findData(definition.kind))
        old = self.options
        expanded = old.disclosure.isChecked()
        self.options = EventAnchorControls(
            definition.to_dict() if definition.kind == "event" else None,
            self,
            calculated_only=True,
        )
        self.options.use_event_help()
        if self._loaded_owner == self._owner:
            self.options.disclosure.setChecked(expanded)
        self._loaded_owner = self._owner
        layout = self.layout()
        assert layout is not None
        layout.replaceWidget(old, self.options)
        old.deleteLater()
        self.options.changed.connect(self._edited)
        self.options.set_context(self._context)
        if definition.kind == "event":
            index = self.events.findData(definition.anchor_id)
            if index < 0:
                self.events.addItem(
                    "Unavailable Event — reference preserved", definition.anchor_id
                )
                index = self.events.count() - 1
            self.events.setCurrentIndex(index)
        self._show_mode()
        self._loading = False

    def definition(self) -> EndpointDefinition:
        """Collect authoring values; validation remains in the domain types."""
        if self.mode.currentData() == "event":
            anchor = self.options.anchor()
            return EndpointDefinition(
                "event",
                anchor_id=str(self.events.currentData() or ""),
                endpoint=anchor.get("endpoint", "start"),
                offset=anchor.get("offset"),
            )
        if self._replacement_required and not self.date.txt_date.text().strip():
            raise ValueError(
                "Enter a replacement manual date before detaching uncertain timing"
            )
        expression = self.date.get_expression()
        return (
            EndpointDefinition(expression=expression.to_dict())
            if expression
            else EndpointDefinition(instant=self.date.get_value())
        )
