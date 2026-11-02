"""Draft-only recurrence controls for the ordinary Event date frame."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QGridLayout, QLabel, QVBoxLayout, QWidget

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.recurrence import RECURRENCE_ATTRIBUTE, RecurrenceRule
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.editor_presentation import DisclosureButton
from src.gui.widgets.numeric_inputs import ScrollSafeDoubleSpinBox
from src.gui.widgets.standard_buttons import StandardCheckbox
from src.services.recurrence_presentation_service import (
    occurrence_bound,
    preview_recurrence,
)


class RecurrenceWidget(QWidget):
    """Render a schedule draft; commands remain responsible for persistence."""

    draft_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a collapsed, keyboard-accessible recurrence disclosure."""
        super().__init__(parent)
        declare_inspection(
            self, "event-repeat-controls|event.recurrence|help-event-repeats"
        )
        self._loading = False
        self._edited = False
        self._baseline: dict[str, Any] | None = None
        self._converter: CalendarConverter | None = None
        self._source = Event("", 0.0)
        self._calendar_id: str | None = None
        self._opaque = False
        self._bound_loaded_values: dict[str, float] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.disclosure = DisclosureButton("Repeats", self)
        declare_inspection(
            self.disclosure, "event-repeats|event.recurrence|help-event-repeats"
        )
        layout.addWidget(self.disclosure)
        self.content = QWidget(self)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 4, 0, 4)
        self.enabled = StandardCheckbox("Repeat this Event")
        content_layout.addWidget(self.enabled)
        self.fields = QWidget(self.content)
        form = QFormLayout(self.fields)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.frequency = ScrollSafeComboBox()
        for label, value in (
            ("Elapsed days", "days"),
            ("Calendar weeks", "weeks"),
            ("Calendar months", "months"),
            ("Calendar years", "years"),
        ):
            self.frequency.addItem(label, value)
        self.interval = declare_inspection(
            ScrollSafeDoubleSpinBox(),
            "event-repeat-interval|event.recurrence|help-event-repeat-interval",
        )
        self.interval.setDecimals(8)
        self.interval.setRange(0.00000001, 1e9)
        self.interval.setValue(1)
        self.direction = ScrollSafeComboBox()
        for label, value in (
            ("Forward", "forward"),
            ("Backward", "backward"),
            ("Both directions", "both"),
        ):
            self.direction.addItem(label, value)
        self.ordinal = ScrollSafeComboBox()
        for label, ordinal_value in (
            ("Same day of the month", None),
            ("First weekday", 1),
            ("Second weekday", 2),
            ("Third weekday", 3),
            ("Fourth weekday", 4),
            ("Fifth weekday", 5),
            ("Last weekday", -1),
        ):
            self.ordinal.addItem(label, ordinal_value)
        form.addRow("Repeat every", self.interval)
        form.addRow("Unit", self.frequency)
        form.addRow("Propagate", self.direction)
        form.addRow("Within each month", self.ordinal)
        self.weekday_container = QWidget()
        self.weekday_layout = QGridLayout(self.weekday_container)
        self.weekday_layout.setContentsMargins(0, 0, 0, 0)
        self.weekdays: list[StandardCheckbox] = []
        form.addRow("Weekdays", self.weekday_container)
        self.bounds: dict[str, tuple[StandardCheckbox, CompactDateWidget]] = {}
        for key, title in (
            ("earliest", "Earliest occurrence"),
            ("latest", "Latest occurrence"),
        ):
            check = StandardCheckbox(title)
            date = CompactDateWidget(text_first=True)
            date.setEnabled(False)
            check.toggled.connect(date.setEnabled)
            form.addRow(check)
            form.addRow(date)
            self.bounds[key] = check, date
            check.toggled.connect(self._changed)
            date.value_changed.connect(self._changed)
            date.draft_changed.connect(self._changed)
        content_layout.addWidget(self.fields)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setAccessibleName("Recurrence preview")
        content_layout.addWidget(self.preview)
        layout.addWidget(self.content)
        self.content.hide()
        self.disclosure.toggled.connect(self.content.setVisible)
        self.enabled.toggled.connect(self._changed)
        for combo in (self.frequency, self.direction, self.ordinal):
            combo.currentIndexChanged.connect(self._changed)
        self.interval.valueChanged.connect(self._changed)
        self._render_state()

    def set_calendar_converter(self, converter: CalendarConverter | None) -> None:
        """Refresh calendar labels without changing a schedule draft's identity."""
        self._converter = converter
        self._loading = True
        selected = {i for i, button in enumerate(self.weekdays) if button.isChecked()}
        while self.weekday_layout.count():
            item = self.weekday_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.weekdays = []
        names = converter._config.week.day_names if converter else []
        for index, name in enumerate(names):
            button = StandardCheckbox(name)
            button.setChecked(index in selected)
            button.toggled.connect(self._changed)
            self.weekday_layout.addWidget(button, index // 2, index % 2)
            self.weekdays.append(button)
        for _check, date in self.bounds.values():
            date.set_calendar_converter(converter)
        self._loading = False
        self._render_state()

    def load_event(self, event: Event) -> None:
        """Hydrate an acknowledged snapshot; preserve opaque metadata losslessly."""
        self._source = event
        self._baseline = deepcopy(event.attributes.get(RECURRENCE_ATTRIBUTE))
        self._loading = True
        self._opaque = False
        try:
            rule = RecurrenceRule.from_dict(self._baseline) if self._baseline else None
        except (ValueError, TypeError, KeyError):
            rule = None
            self._opaque = True
        self.enabled.setChecked(self._baseline is not None)
        self._calendar_id = (
            rule.calendar_id
            if rule
            else self._converter._config.id
            if self._converter
            else None
        )
        if rule is not None:
            self.frequency.setCurrentIndex(self.frequency.findData(rule.frequency))
            self.interval.setValue(rule.interval)
            self.direction.setCurrentIndex(self.direction.findData(rule.direction))
            self.ordinal.setCurrentIndex(self.ordinal.findData(rule.ordinal))
        else:
            self.frequency.setCurrentIndex(self.frequency.findData("years"))
            self.interval.setValue(1)
            self.direction.setCurrentIndex(0)
            self.ordinal.setCurrentIndex(0)
        for index, button in enumerate(self.weekdays):
            button.setChecked(rule is not None and index in rule.weekdays)
        for key, (check, date) in self.bounds.items():
            value = getattr(rule, key) if rule else None
            check.setChecked(value is not None)
            date.set_value(value if value is not None else event.lore_date or 0.0)
            self._bound_loaded_values[key] = date.get_value()
        self._edited = False
        self._loading = False
        self.disclosure.setText(
            "Repeats · configured" if self._baseline is not None else "Repeats"
        )
        self._render_state()

    def metadata(self) -> dict[str, Any] | None:
        """Collect draft intent without validating or changing its saved baseline."""
        if not self._edited or self._opaque:
            return deepcopy(self._baseline) if self.enabled.isChecked() else None
        if not self.enabled.isChecked():
            return None
        frequency = self.frequency.currentData()
        ordinal = (
            self.ordinal.currentData() if frequency in {"months", "years"} else None
        )
        days = [i for i, button in enumerate(self.weekdays) if button.isChecked()]
        return {
            "schema": 1,
            "frequency": frequency,
            "interval": self.interval.value(),
            "direction": self.direction.currentData(),
            "calendar_id": self._calendar_id if frequency != "days" else None,
            "ordinal": ordinal,
            "weekdays": days if frequency == "weeks" or ordinal is not None else [],
            **{
                key: self._bound_value(key, date) if check.isChecked() else None
                for key, (check, date) in self.bounds.items()
            },
        }

    def saved_metadata(self) -> dict[str, Any] | None:
        """Return the baseline used for worker-side stale schedule detection."""
        return deepcopy(self._baseline)

    def _bound_value(self, key: str, date: CompactDateWidget) -> float:
        original = (self._baseline or {}).get(key)
        if (
            original is not None
            and date.get_expression() is None
            and date.get_value() == self._bound_loaded_values.get(key)
        ):
            return float(original)
        try:
            return occurrence_bound(
                date.get_value(),
                date.get_expression(),
                self._converter,
                latest=key == "latest",
            )
        except (ValueError, TypeError):
            return date.get_value()

    def has_changes(self) -> bool:
        """Include uncommitted bound text in navigation/save protection."""
        return self.metadata() != self._baseline or any(
            check.isChecked() and date._draft_pending
            for check, date in self.bounds.values()
        )

    def commit_drafts(self) -> bool:
        """Accept date text only on explicit save."""
        for check, date in self.bounds.values():
            if not check.isChecked():
                continue
            if not date.commit_draft():
                return False
            expression = date.get_expression()
            if expression is not None and (
                expression.qualifier.value != "asserted" or expression.day is None
            ):
                self.preview.setText(
                    "Occurrence bounds require an exact date with a day."
                )
                return False
        return True

    def discard_draft(self) -> None:
        """Restore the saved schedule so the normal reload can restore date fields."""
        attributes = deepcopy(self._source.attributes)
        attributes.pop(RECURRENCE_ATTRIBUTE, None)
        if self._baseline is not None:
            attributes[RECURRENCE_ATTRIBUTE] = deepcopy(self._baseline)
        self.load_event(replace(self._source, attributes=attributes))

    def acknowledge(
        self, saved: dict[str, Any] | None, submitted: dict[str, Any] | None
    ) -> None:
        """Adopt saved facts while retaining any newer local recurrence edits."""
        current = self.metadata()
        self._baseline = deepcopy(saved)
        if current == submitted:
            self._edited = False
        self._render_state()

    def set_anchor(self, event: Event) -> None:
        """Refresh preview input while retaining the schedule draft."""
        self._source = event
        self._render_state()

    def _changed(self, *_args: object) -> None:
        if self._loading:
            return
        self._edited = True
        if self._calendar_id is None and self._converter is not None:
            self._calendar_id = self._converter._config.id
        self._render_state()
        self.draft_changed.emit(self.has_changes())

    def _render_state(self) -> None:
        self.fields.setEnabled(self.enabled.isChecked() and not self._opaque)
        frequency = self.frequency.currentData()
        self.ordinal.setEnabled(frequency in {"months", "years"})
        self.weekday_container.setEnabled(
            frequency == "weeks" or self.ordinal.currentData() is not None
        )
        raw = self.metadata()
        if raw is None:
            self.preview.setText(
                "The authored date anchors the pattern. Save Changes applies recurrence edits."
            )
            return
        event = replace(
            self._source,
            attributes={**self._source.attributes, RECURRENCE_ATTRIBUTE: raw},
        )
        self.preview.setText(preview_recurrence(event, self._converter).text)
