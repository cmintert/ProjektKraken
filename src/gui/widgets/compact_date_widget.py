"""Compact Date Widget Module.

Provides a polished, calendar-aware date input widget with:
- Year spinbox
- Month dropdown (populated from calendar)
- Day dropdown (adjusts to month length)
- Optional time inputs (hour/minute)
- Calendar popup button
- Live preview of formatted date
"""

import logging
import os
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal, Slot
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter, CalendarDate
from src.core.date_parser import DateParser
from src.core.temporal_expression import (
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
)
from src.core.theme_manager import ThemeManager
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class CompactDateWidget(QWidget):
    """A polished date input widget with calendar-aware dropdowns.

    Features:
    - Year spinbox
    - Month dropdown with calendar-specific names
    - Day dropdown that adjusts to month length
    - Hour/Minute inputs for time
    - Calendar popup for visual date selection
    - Live preview of formatted date
    - Direct text input parsing

    Signals:
        value_changed: Emitted when the date value changes.
    """

    value_changed = Signal(float)
    draft_changed = Signal(bool)
    range_end_selected = Signal(object)

    def __init__(
        self, parent: Optional[QWidget] = None, *, text_first: bool = False
    ) -> None:
        """Initializes the compact date widget.

        Args:
            parent: Parent widget.
            text_first: Opt into draft-aware text entry for the event inspector.

        """
        super().__init__(parent)
        self._text_first = text_first
        self._draft_pending = False
        self._accepted_value = 0.0
        self._expression: TemporalExpression | None = None
        self.allow_duration_range = False
        # Set size policy to prevent vertical squashing
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._converter: CalendarConverter | None = None
        self._parser: Optional[DateParser] = None
        self._updating = False

        self._setup_ui()
        self._connect_signals()
        if text_first:
            self._setup_text_first()

    def _setup_text_first(self) -> None:
        """Promote typed entry while retaining all structured controls."""
        from src.gui.widgets.editor_presentation import DisclosureButton

        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        row_item = layout.itemAt(0)
        assert row_item is not None
        date_row = row_item.layout()
        assert isinstance(date_row, QHBoxLayout)
        date_row.removeWidget(self._date_chip)
        date_row.removeWidget(self.btn_time_toggle)
        date_row.takeAt(date_row.count() - 1)
        time_layout = self._time_container.layout()
        assert time_layout is not None
        time_layout.removeWidget(self.txt_date)
        self.txt_date.setMinimumWidth(0)
        self.txt_date.setMaximumWidth(16777215)
        self.txt_date.setMinimumHeight(32)
        self.txt_date.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.txt_date.setAccessibleName("Date")
        date_row.insertWidget(0, self.txt_date, 1)
        date_row.setStretch(0, 1)
        self.btn_calendar.setFixedSize(32, 32)
        self.btn_calendar.setAccessibleName("Choose date from calendar")
        self.date_fields_button = DisclosureButton("Date fields…", self)
        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.addWidget(self.date_fields_button)
        options_row.addWidget(self.btn_time_toggle)
        layout.insertLayout(1, options_row)
        layout.insertWidget(2, self._date_chip)
        chip_layout = self._date_chip.layout()
        assert chip_layout is not None
        for field in (self.spin_year, self.combo_month, self.combo_day):
            field.setMinimumWidth(0)
            field.setMaximumWidth(16777215)
            field.setMinimumHeight(32)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._date_chip.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        chip_layout.setSpacing(4)
        self.date_fields_button.toggled.connect(self._date_chip.setVisible)
        self._qualification_row = QWidget(self)
        qualification_layout = QHBoxLayout(self._qualification_row)
        qualification_layout.setContentsMargins(0, 0, 0, 0)
        qualification_layout.addWidget(QLabel("Date qualification"))
        self.qualifier_combo = QComboBox()
        for label, qualifier in (
            ("Asserted", TemporalQualifier.ASSERTED),
            ("Approximate", TemporalQualifier.APPROXIMATE),
            ("Uncertain", TemporalQualifier.UNCERTAIN),
            ("Approximate and uncertain", TemporalQualifier.APPROXIMATE_UNCERTAIN),
            ("Estimated", TemporalQualifier.ESTIMATED),
            ("Calculated", TemporalQualifier.CALCULATED),
        ):
            self.qualifier_combo.addItem(label, qualifier.value)
        self.qualifier_combo.setAccessibleName("Date qualification")
        qualification_layout.addWidget(self.qualifier_combo, 1)
        layout.insertWidget(3, self._qualification_row)
        self._qualification_row.hide()
        self.limits_button = QPushButton("Possible date limits…")
        layout.insertWidget(4, self.limits_button)
        self.limits_button.hide()
        self.date_fields_button.toggled.connect(self.limits_button.setVisible)
        self.limits_button.clicked.connect(self._edit_limits)
        self.date_fields_button.toggled.connect(self._qualification_row.setVisible)
        self.qualifier_combo.currentIndexChanged.connect(self._on_qualifier_changed)
        self.btn_time_toggle.setText("Time…")
        self.btn_time_toggle.setIcon(QIcon())
        self.btn_time_toggle.setMinimumSize(0, 32)
        self.btn_time_toggle.setMaximumSize(16777215, 32)
        self.btn_time_toggle.setAccessibleName("Show time fields")
        self.feedback = QLabel(self)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.txt_date.textEdited.connect(self._on_draft_edited)
        self.txt_date.installEventFilter(self)
        for field in (self.combo_month, self.combo_day):
            field.installEventFilter(self)
            field.setToolTip("Choose a component, or press Delete to leave it unknown.")
        self._sync_entry_availability()

    def _sync_entry_availability(self) -> None:
        if not self._text_first:
            return
        available = self._parser is not None
        self.txt_date.setVisible(available)
        self.btn_calendar.setEnabled(available)
        self.date_fields_button.setChecked(not available)
        self._date_chip.setVisible(not available)
        self.feedback.setText(
            "" if available else "Use date fields until a calendar is available."
        )
        if available and self._converter is not None:
            example = self._entry_text()
            self.txt_date.setPlaceholderText(example)
            self.txt_date.setToolTip(f"Enter a calendar date, for example {example}")
            self._accepted_value = self.get_value()
            self._show_accepted_date()

    def _edit_limits(self) -> None:
        """Collect explicit occurrence limits without changing the event duration."""
        from dataclasses import replace

        from PySide6.QtWidgets import QCheckBox, QDialogButtonBox, QFormLayout

        from src.core.temporal_authoring import (
            explicit_limit_text,
            with_explicit_limits,
        )

        if self._parser is None or not self.commit_draft():
            return
        parser = self._parser
        expression = self._expression or parser.parse_expression(self._entry_text())
        dialog = QDialog(self)
        dialog.setWindowTitle("Possible date limits")
        dialog.setStyleSheet(StyleHelper.get_dialog_base_style())
        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "Limits bound when the occurrence can happen. The until limit includes the whole entered period. These are not duration endpoints."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        editors = []
        for label, value in (
            ("Possible from", expression.explicit_outer_start),
            ("Possible until", expression.explicit_outer_end),
        ):
            enabled = QCheckBox(label)
            enabled.setChecked(value is not None)
            field = QLineEdit()
            field.setAccessibleName(label)
            # Stored upper limits are exclusive; show the last included period.
            text = (
                explicit_limit_text(
                    value, parser.converter, upper=label == "Possible until"
                )
                if value is not None
                else ""
            )
            field.setText(text)
            field.setEnabled(enabled.isChecked())
            enabled.toggled.connect(field.setEnabled)
            form.addRow(enabled, field)
            editors.append((enabled, field, text, value))
        layout.addLayout(form)
        error = QLabel()
        error.setWordWrap(True)
        error.setStyleSheet(StyleHelper.get_error_label_style())
        layout.addWidget(error)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(actions)

        def apply() -> None:
            try:
                values: list[float | None] = []
                for index, (enabled, field, original, old_value) in enumerate(editors):
                    if not enabled.isChecked():
                        values.append(None)
                    elif field.text() == original and old_value is not None:
                        values.append(old_value)
                    else:
                        if not field.text().strip():
                            raise ValueError("Enter a date for each enabled limit.")
                        bound = with_explicit_limits(
                            expression,
                            parser,
                            field.text().strip() if index == 0 else "",
                            field.text().strip() if index == 1 else "",
                        )
                        values.append(
                            bound.explicit_outer_start
                            if index == 0
                            else bound.explicit_outer_end
                        )
                updated = replace(
                    expression,
                    explicit_outer_start=values[0],
                    explicit_outer_end=values[1],
                )
                problem = updated.resolve_bounds(parser.converter).error
                if problem:
                    raise ValueError(problem)
                self.set_expression(updated)
                self.value_changed.emit(self.get_value())
                dialog.accept()
            except ValueError as exc:
                error.setText(str(exc))

        actions.accepted.connect(apply)
        actions.rejected.connect(dialog.reject)
        dialog.exec()

    def _on_qualifier_changed(self, _index: int) -> None:
        """Publish an intentional qualification edit without changing precision."""
        if self._updating or self._parser is None:
            return
        from dataclasses import replace

        expression = self._expression or self._parser.parse_expression(
            self._entry_text()
        )
        expression = replace(
            expression,
            original_text=None,
            qualifier=TemporalQualifier(self.qualifier_combo.currentData()),
        )
        self.set_expression(expression)
        self.value_changed.emit(self.get_value())

    def _on_draft_edited(self, _text: str) -> None:
        self._draft_pending = True
        self.feedback.setText("Date not applied yet. Enter to apply; Esc to restore.")
        self.draft_changed.emit(True)

    def has_pending_draft(self) -> bool:
        """Return whether typed input is awaiting acceptance."""
        return self._draft_pending

    def commit_draft(self) -> bool:
        """Accept parseable text without altering values on invalid input."""
        if not self._draft_pending:
            return True
        try:
            if self._parser is None:
                raise ValueError("No calendar is available")
            expression, range_end = self._parse_draft_expression()
            timestamp = expression.representative_time(self._parser.converter)
        except (ValueError, TypeError, OverflowError):
            self.feedback.setText(
                "Date not recognized. Use this calendar's date format, "
                "choose a date, or press Esc to restore."
            )
            self.txt_date.setAccessibleDescription(self.feedback.text())
            return False
        self._draft_pending = False
        self.set_value(timestamp)
        self.set_expression(expression)
        self.value_changed.emit(timestamp)
        if range_end is not None:
            self.range_end_selected.emit(range_end)
        self.draft_changed.emit(False)
        return True

    def _parse_draft_expression(
        self,
    ) -> tuple[TemporalExpression, TemporalExpression | None]:
        """Require an explicit meaning for a bare date range."""
        assert self._parser is not None
        text = self.txt_date.text().strip()
        try:
            return self._parser.parse_expression(text), None
        except ValueError:
            start, end = self._parser.parse_range_expressions(text)
        options = ["Occurred sometime within this range"]
        if self.allow_duration_range:
            options.append("Lasted from the first date to the second")
        selected, accepted = QInputDialog.getItem(
            self,
            "What does this date range mean?",
            "Range meaning",
            options,
            0,
            False,
        )
        if not accepted:
            raise ValueError("Choose the range meaning or restore the previous date")
        if selected == options[0]:
            expression = self._parser.parse_expression(
                f"between {start.display_text(self._converter)} and {end.display_text(self._converter)}"
            )
            return expression, None
        return start, end

    def cancel_draft(self) -> None:
        """Restore the last accepted value without publishing an edit."""
        if self._draft_pending:
            self._draft_pending = False
            expression = self._expression
            self.set_value(self._accepted_value)
            if expression is not None:
                self.set_expression(expression)
            self.draft_changed.emit(False)

    def _show_accepted_date(self) -> None:
        if self._converter is not None and not self._draft_pending:
            text = (
                self._expression.display_text(self._converter)
                if self._expression
                else self._converter.format_date(self.get_value())
            )
            self.txt_date.setText(self._entry_text())
            self.feedback.setText(f"Date: {text}")
            self.txt_date.setAccessibleDescription("")

    def _entry_text(self) -> str:
        """Use existing parser syntax for the editable date representation."""
        if self._expression is not None:
            return self._expression.display_text(self._converter)
        day = self.combo_day.currentIndex() + 1
        year = self.spin_year.value()
        month = self.combo_month.currentText()
        if self._parser is not None and month.lower() in self._parser.month_lookup:
            text = f"{day} {month} {year}"
        else:
            text = f"{year}-{self.combo_month.currentIndex() + 1:02d}-{day:02d}"
        hour, minute = self.spin_hour.value(), self.spin_minute.value()
        if hour or minute:
            text += f" {hour:02d}:{minute:02d}"
        return text

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Let Escape cancel only this field's unaccepted date draft."""
        if (
            watched in (self.combo_month, self.combo_day)
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}
        ):
            assert isinstance(watched, QComboBox)
            watched.setCurrentIndex(-1)
            self._on_input_changed()
            return True
        if (
            watched is self.txt_date
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and self._draft_pending
        ):
            self.cancel_draft()
            return True
        return super().eventFilter(watched, event)

    def _setup_ui(self) -> None:
        """Sets up the widget UI."""
        from PySide6.QtWidgets import QSizePolicy

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # ── Row 1: date chip + toggle buttons ─────────────────────────────
        date_row = QHBoxLayout()
        date_row.setSpacing(4)

        # Date chip: grouped QFrame for Year / Month / Day
        self._date_chip = QFrame()
        self._date_chip.setObjectName("date_chip")
        chip_layout = QHBoxLayout(self._date_chip)
        chip_layout.setContentsMargins(4, 1, 4, 1)
        chip_layout.setSpacing(0)

        self.spin_year = QSpinBox()
        self.spin_year.setRange(-999999, 999999)
        self.spin_year.setValue(1)
        self.spin_year.setPrefix("Year ")
        self.spin_year.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.spin_year.setFixedWidth(130)
        chip_layout.addWidget(self.spin_year, stretch=0)

        self.combo_month = QComboBox()
        self.combo_month.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.combo_month.setFixedWidth(100)
        chip_layout.addWidget(self.combo_month, stretch=0)

        self.combo_day = QComboBox()
        self.combo_day.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.combo_day.setFixedWidth(70)
        chip_layout.addWidget(self.combo_day, stretch=0)

        self._date_chip.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        date_row.addWidget(self._date_chip, stretch=0)

        # Time toggle button (clock icon)
        self.btn_time_toggle = QPushButton()
        self.btn_time_toggle.setFixedSize(32, 24)
        self.btn_time_toggle.setCheckable(True)
        self.btn_time_toggle.setToolTip(
            "Show / hide time input (auto-shown for non-midnight dates)"
        )
        date_row.addWidget(self.btn_time_toggle, stretch=0)

        # Calendar button
        self.btn_calendar = QPushButton()
        self.btn_calendar.setFixedSize(32, 24)
        self.btn_calendar.setToolTip("Open calendar picker")
        date_row.addWidget(self.btn_calendar, stretch=0)
        date_row.addStretch(1)

        theme = ThemeManager().get_theme()
        self._update_icons(theme)

        main_layout.addLayout(date_row)

        # ── Row 2: time inputs (collapsible) ──────────────────────────────
        self._time_container = QWidget()
        self._time_container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        time_row = QHBoxLayout(self._time_container)
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(8)

        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setValue(0)
        self.spin_hour.setSuffix("h")
        self.spin_hour.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # The shared spinbox theme reserves space for a 16px arrow column and
        # 20px of right padding.  65px leaves too little room for a two-digit
        # value plus its unit, particularly under Windows font metrics.
        self.spin_hour.setFixedWidth(88)
        time_row.addWidget(self.spin_hour, stretch=0)

        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setValue(0)
        self.spin_minute.setSuffix("m")
        self.spin_minute.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.spin_minute.setFixedWidth(88)
        time_row.addWidget(self.spin_minute, stretch=0)

        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("Type date...")
        self.txt_date.setToolTip("Enter date text (e.g. '15 Jan 3019')")
        self.txt_date.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.txt_date.setFixedWidth(140)
        time_row.addWidget(self.txt_date, stretch=0)
        time_row.addStretch(1)

        self._time_container.setVisible(False)
        main_layout.addWidget(self._time_container)

        # Initialize with default months
        self._populate_months()
        self._populate_days()

        # Apply initial styles
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Applies theme-aware styles to all inputs."""
        input_style = StyleHelper.get_input_field_style()
        spinbox_style = StyleHelper.get_spinbox_style()

        # Date chip provides the unified outer border; internals go borderless.
        self._date_chip.setStyleSheet(StyleHelper.get_date_chip_style())
        self.spin_year.setStyleSheet(StyleHelper.get_chip_spinbox_style())
        self.combo_month.setStyleSheet(StyleHelper.get_chip_combo_style())
        self.combo_day.setStyleSheet(StyleHelper.get_chip_combo_style())

        # Time row keeps its own normal styles.
        self.spin_hour.setStyleSheet(spinbox_style)
        self.spin_minute.setStyleSheet(spinbox_style)
        self.txt_date.setStyleSheet(
            input_style + " font-family: 'Consolas', monospace; font-size: 11px;"
        )

        self.btn_calendar.setStyleSheet(StyleHelper.get_icon_button_style())
        self.btn_time_toggle.setStyleSheet(StyleHelper.get_icon_button_style())

    def _connect_signals(self) -> None:
        """Connects internal signals."""
        self.spin_year.valueChanged.connect(self._on_input_changed)
        self.combo_month.currentIndexChanged.connect(self._on_month_changed)
        self.combo_day.currentIndexChanged.connect(self._on_input_changed)
        self.spin_hour.valueChanged.connect(self._on_input_changed)
        self.spin_minute.valueChanged.connect(self._on_input_changed)
        self.btn_calendar.clicked.connect(self._open_calendar_popup)
        self.btn_time_toggle.toggled.connect(self._on_time_toggle)
        self.txt_date.editingFinished.connect(self._on_text_edited)

        # Theme changes
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _update_icons(self, theme: dict) -> None:
        """Updates both the calendar and time-toggle icons for the given theme.

        Args:
            theme: Current theme dictionary from ThemeManager.

        """
        color = theme.get("accent_secondary", theme.get("text_main", "#e0e0e0"))
        cal_path = os.path.join("default_assets", "icons", "ui_icons", "calendar.svg")
        clock_path = os.path.join("default_assets", "icons", "ui_icons", "clock.svg")
        self.btn_calendar.setIcon(load_icon(cal_path, color=color))
        if self._text_first and self.btn_calendar.icon().isNull():
            self.btn_calendar.setText("…")
        self.btn_calendar.setIconSize(QSize(16, 16))
        self.btn_time_toggle.setIcon(load_icon(clock_path, color=color))
        self.btn_time_toggle.setIconSize(QSize(14, 14))

    @Slot(bool)
    def _on_time_toggle(self, checked: bool) -> None:
        """Shows or hides the time input row.

        Args:
            checked: True to show the time controls, False to hide them.

        """
        self._time_container.setVisible(checked)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """Sets the calendar converter for date calculations.

        Args:
            converter: CalendarConverter instance.

        """
        self._converter = converter
        if self._converter and self._converter._config:
            self._parser = DateParser(self._converter._config)
        elif self._text_first:
            self._parser = None

        self._populate_months()
        self._populate_days()
        self._update_preview()
        self._sync_entry_availability()

    def _populate_months(self) -> None:
        """Populates month dropdown from calendar."""
        prev_updating = self._updating
        self._updating = True
        try:
            current_index = self.combo_month.currentIndex()
            self.combo_month.clear()

            if self._converter and self._converter._config:
                year = self.spin_year.value()
                months = self._converter._config.get_months_for_year(year)
                for month in months:
                    self.combo_month.addItem(month.name)
            else:
                # Fallback: 12 generic months
                for i in range(12):
                    self.combo_month.addItem(f"Month {i + 1}")

            # Restore selection
            if self._expression is not None and self._expression.month is None:
                self.combo_month.setCurrentIndex(-1)
            elif current_index >= 0 and current_index < self.combo_month.count():
                self.combo_month.setCurrentIndex(current_index)
            elif self.combo_month.count() > 0:
                self.combo_month.setCurrentIndex(0)
        finally:
            self._updating = prev_updating

    def _populate_days(self) -> None:
        """Populates day dropdown based on selected month."""
        prev_updating = self._updating
        self._updating = True
        try:
            current_day = self.combo_day.currentIndex()
            self.combo_month.blockSignals(True)
            self.combo_day.clear()

            days_in_month = 30  # Default
            if self._converter and self._converter._config:
                year = self.spin_year.value()
                month_index = self.combo_month.currentIndex()
                months = self._converter._config.get_months_for_year(year)
                if 0 <= month_index < len(months):
                    days_in_month = months[month_index].days

            for d in range(1, days_in_month + 1):
                self.combo_day.addItem(f"Day {d}")

            # Restore or clamp day selection
            if self._expression is not None and self._expression.day is None:
                self.combo_day.setCurrentIndex(-1)
            elif current_day >= 0 and current_day < days_in_month:
                self.combo_day.setCurrentIndex(current_day)
            elif days_in_month > 0:
                self.combo_day.setCurrentIndex(min(current_day, days_in_month - 1))

            self.combo_month.blockSignals(False)
        finally:
            self._updating = prev_updating

    @Slot(int)
    def _on_month_changed(self, index: int) -> None:
        """Handles month selection change."""
        self._populate_days()
        self._on_input_changed()

    @Slot()
    def _on_input_changed(self) -> None:
        """Handles any input change."""
        if self._updating:
            return

        if self._text_first and self._converter is not None:
            month_index = self.combo_month.currentIndex()
            day_index = self.combo_day.currentIndex()
            month = month_index + 1 if month_index >= 0 else None
            day = day_index + 1 if day_index >= 0 and month is not None else None
            has_time = self.btn_time_toggle.isChecked() and day is not None
            precision = (
                TemporalPrecision.MINUTE
                if has_time
                else TemporalPrecision.DAY
                if day is not None
                else TemporalPrecision.MONTH
                if month is not None
                else TemporalPrecision.YEAR
            )
            self._expression = TemporalExpression(
                calendar_id=self._converter._config.id,
                year=self.spin_year.value(),
                month=month,
                day=day,
                hour=self.spin_hour.value() if has_time else None,
                minute=self.spin_minute.value() if has_time else None,
                precision=precision,
                qualifier=(
                    self._expression.qualifier
                    if self._expression
                    else TemporalQualifier.ASSERTED
                ),
                explicit_outer_start=self._expression.explicit_outer_start
                if self._expression
                else None,
                explicit_outer_end=self._expression.explicit_outer_end
                if self._expression
                else None,
            )

        self._update_preview()
        value = self.get_value()
        if self._text_first:
            self._draft_pending = False
            self._accepted_value = value
            self._show_accepted_date()
        self.value_changed.emit(value)
        if self._text_first:
            self.draft_changed.emit(False)

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Handles theme changes to update icons and styles."""
        self._apply_styles()
        self._update_icons(theme)

    @Slot()
    def _on_text_edited(self) -> None:
        """Handles manual text input."""
        if self._text_first:
            self.commit_draft()
            return
        if self._updating or not self._parser:
            return

        text = self.txt_date.text().strip()
        if not text:
            return

        try:
            parsed = self._parser.parse_date(text)
            timestamp = self._parser.calculate_timestamp(parsed)
            # This will trigger set_value which formats text back to canonical
            self.set_value(timestamp)
            self.value_changed.emit(timestamp)
        except ValueError:
            # Maybe show red border or tooltip?
            # For now just don't update value, keep user text dirty
            pass

    def _update_preview(self) -> None:
        """Updates the preview text field."""
        if not self._converter:
            if not self.txt_date.hasFocus():
                self.txt_date.setText("")
            return

        try:
            value = self.get_value()
            formatted = self._converter.format_date(value)
            # Only update text if not focused to avoid fighting user
            if not self.txt_date.hasFocus():
                self.txt_date.setText(formatted)
        except Exception as e:
            logger.warning(f"Date formatting failed: {e}")
            if not self.txt_date.hasFocus():
                self.txt_date.setText("")

    def get_value(self) -> float:
        """Gets the current date as a float value.

        Returns:
            float: Absolute day value.

        """
        if self._expression is not None and self._converter is not None:
            return self._expression.representative_time(self._converter)
        if not self._converter:
            # Fallback: simple calculation
            year = self.spin_year.value()
            month = self.combo_month.currentIndex() + 1
            day = self.combo_day.currentIndex() + 1
            hour = self.spin_hour.value()
            minute = self.spin_minute.value()

            # Rough estimate: 365 days/year, 30 days/month
            days = float((year - 1) * 365 + (month - 1) * 30 + (day - 1))
            days += (hour * 60 + minute) / (24 * 60)
            return days

        # Use converter
        year = self.spin_year.value()
        month = self.combo_month.currentIndex() + 1
        day = self.combo_day.currentIndex() + 1
        hour = self.spin_hour.value()
        minute = self.spin_minute.value()

        time_fraction = (hour * 60 + minute) / (24 * 60)

        date = CalendarDate(
            year=year,
            month=month,
            day=day,
            time_fraction=time_fraction,
        )
        return self._converter.to_float(date)

    def set_value(self, days_float: float) -> None:
        """Sets the date from a float value.

        Args:
            days_float: Absolute day value.

        """
        if self._updating:
            return

        self._expression = None
        if self._text_first:
            self.qualifier_combo.blockSignals(True)
            self.qualifier_combo.setCurrentIndex(0)
            self.qualifier_combo.blockSignals(False)

        prev_updating = self._updating
        self._updating = True
        try:
            if self._converter:
                date = self._converter.from_float(days_float)
                self.spin_year.setValue(date.year)

                # Ensure months are populated for this year
                self._populate_months()

                if 1 <= date.month <= self.combo_month.count():
                    self.combo_month.setCurrentIndex(date.month - 1)

                self._populate_days()

                if 1 <= date.day <= self.combo_day.count():
                    self.combo_day.setCurrentIndex(date.day - 1)

                # Time
                total_minutes = int(date.time_fraction * 24 * 60)
                self.spin_hour.setValue(total_minutes // 60)
                self.spin_minute.setValue(total_minutes % 60)

                # Auto-expand time row for non-midnight dates.
                has_time = total_minutes != 0
                if self.btn_time_toggle.isChecked() != has_time:
                    self.btn_time_toggle.setChecked(has_time)
            else:
                # Fallback
                year = int(days_float / 365) + 1
                remaining = days_float % 365
                month = int(remaining / 30) + 1
                day = int(remaining % 30) + 1

                self.spin_year.setValue(year)
                if month <= self.combo_month.count():
                    self.combo_month.setCurrentIndex(month - 1)
                self._populate_days()
                if day <= self.combo_day.count():
                    self.combo_day.setCurrentIndex(day - 1)

            self._update_preview()
            if self._text_first and hasattr(self, "feedback"):
                self._accepted_value = self.get_value()
                self._show_accepted_date()
        finally:
            self._updating = prev_updating

    def get_expression(self) -> TemporalExpression | None:
        """Return the semantic assertion, or None for an unchanged legacy date."""
        return self._expression

    def set_expression(self, expression: TemporalExpression) -> None:
        """Load an assertion without completing unspecified components."""
        self._expression = expression
        self._updating = True
        try:
            self.spin_year.setValue(expression.year or 0)
            self._populate_months()
            self.combo_month.setPlaceholderText("Month unknown")
            self.combo_month.setCurrentIndex(
                expression.month - 1 if expression.month is not None else -1
            )
            self._populate_days()
            self.combo_day.setPlaceholderText("Day unknown")
            self.combo_day.setCurrentIndex(
                expression.day - 1 if expression.day is not None else -1
            )
            self.spin_hour.setValue(expression.hour or 0)
            self.spin_minute.setValue(expression.minute or 0)
            self.btn_time_toggle.setChecked(expression.hour is not None)
            if self._text_first:
                self.qualifier_combo.setCurrentIndex(
                    self.qualifier_combo.findData(expression.qualifier.value)
                )
            self._draft_pending = False
            self._accepted_value = self.get_value()
            if self._text_first:
                self._show_accepted_date()
            else:
                self.txt_date.setText(expression.display_text(self._converter))
        finally:
            self._updating = False

    @Slot()
    def _open_calendar_popup(self) -> None:
        """Opens the calendar picker popup."""
        if not self._converter:
            return

        popup = CalendarPopup(
            self,
            self._converter,
            self.spin_year.value(),
            self.combo_month.currentIndex() + 1,
            self.combo_day.currentIndex() + 1,
        )
        if popup.exec() == QDialog.DialogCode.Accepted:
            year, month, day = popup.get_selected_date()
            if self._text_first:
                self._updating = True
                try:
                    self.spin_year.setValue(year)
                    self._populate_months()
                    self.combo_month.setCurrentIndex(month - 1)
                    self._populate_days()
                    self.combo_day.setCurrentIndex(day - 1)
                finally:
                    self._updating = False
                self._on_input_changed()
                return
            self.spin_year.setValue(year)
            self.combo_month.setCurrentIndex(month - 1)
            self._populate_days()
            self.combo_day.setCurrentIndex(day - 1)

    def minimumSizeHint(self) -> QSize:
        """Returns the minimum size hint to prevent vertical collapse.

        Returns:
            QSize: Minimum size reserved for the complete date control.

        """
        if self._text_first:
            layout = self.layout()
            assert layout is not None
            return layout.minimumSize()
        return QSize(250, 72)

    def sizeHint(self) -> QSize:
        """Returns the preferred size hint.

        Returns:
            QSize: Dynamic preferred size based on time row visibility.

        """
        if self._text_first:
            layout = self.layout()
            assert layout is not None
            return layout.sizeHint()
        if self._time_container.isVisible():
            return QSize(350, 72)
        return QSize(350, 34)


class CalendarPopup(QDialog):
    """A popup dialog for visual date selection.

    Shows a grid of days for the selected month.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        converter: CalendarConverter,
        year: int,
        month: int,
        day: int,
    ) -> None:
        """Initializes the calendar popup.

        Args:
            parent: Parent widget.
            converter: Calendar converter.
            year: Initial year.
            month: Initial month (1-indexed).
            day: Initial day (1-indexed).

        """
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self._converter = converter
        self._year = year
        self._month = month
        self._selected_day = day

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the popup UI."""
        # Set dialog-level stylesheet for day buttons using StyleHelper
        dialog_style = (
            StyleHelper.get_dialog_base_style()
            + "\n"
            + StyleHelper.get_dialog_button_style(selected=False)
            + "\n"
            + StyleHelper.get_dialog_button_style(selected=True)
        )
        self.setStyleSheet(dialog_style)

        layout = QVBoxLayout(self)

        # Header: Year and Month selectors
        header = QHBoxLayout()

        self.spin_year = QSpinBox()
        self.spin_year.setRange(-999999, 999999)
        self.spin_year.setValue(self._year)
        self.spin_year.valueChanged.connect(self._refresh_grid)
        header.addWidget(self.spin_year)

        self.combo_month = QComboBox()
        months = self._converter._config.get_months_for_year(self._year)
        for m in months:
            self.combo_month.addItem(m.name)
        self.combo_month.setCurrentIndex(self._month - 1)
        self.combo_month.currentIndexChanged.connect(self._refresh_grid)
        header.addWidget(self.combo_month)

        layout.addLayout(header)

        # Day grid
        self.grid_frame = QFrame()
        self.grid_layout = QGridLayout(self.grid_frame)
        self.grid_layout.setSpacing(2)
        layout.addWidget(self.grid_frame)

        self._refresh_grid()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _refresh_grid(self) -> None:
        """Refreshes the day grid."""
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()  # type: ignore

        year = self.spin_year.value()
        month_idx = self.combo_month.currentIndex()
        months = self._converter._config.get_months_for_year(year)

        if 0 <= month_idx < len(months):
            days = months[month_idx].days
        else:
            days = 30

        # Create day buttons in 7-column grid
        for d in range(1, days + 1):
            btn = QPushButton(str(d))
            btn.setFixedSize(32, 32)
            btn.clicked.connect(lambda checked, day=d: self._select_day(day))

            # Use objectName for styling - dialog stylesheet handles the rest
            if d == self._selected_day:
                btn.setObjectName("day_btn_selected")
            else:
                btn.setObjectName(f"day_btn_{d}")

            row = (d - 1) // 7
            col = (d - 1) % 7
            self.grid_layout.addWidget(btn, row, col)

    def _select_day(self, day: int) -> None:
        """Selects a day and accepts."""
        self._selected_day = day
        self._year = self.spin_year.value()
        self._month = self.combo_month.currentIndex() + 1
        self.accept()

    def get_selected_date(self) -> tuple[int, int, int]:
        """Returns the selected date as (year, month, day)."""
        return self._year, self._month, self._selected_day
