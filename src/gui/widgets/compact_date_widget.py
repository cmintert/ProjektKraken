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

from PySide6.QtCore import QSize, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter, CalendarDate
from src.core.date_parser import DateParser
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the compact date widget.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        # Set size policy to prevent vertical squashing
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._converter: CalendarConverter | None = None
        self._parser: Optional[DateParser] = None
        self._updating = False

        self._setup_ui()
        self._connect_signals()

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
        self.spin_year.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.spin_year.setFixedWidth(130)
        chip_layout.addWidget(self.spin_year, stretch=0)

        self.combo_month = QComboBox()
        self.combo_month.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.combo_month.setFixedWidth(100)
        chip_layout.addWidget(self.combo_month, stretch=0)

        self.combo_day = QComboBox()
        self.combo_day.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
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
        self.spin_hour.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.spin_hour.setFixedWidth(65)
        time_row.addWidget(self.spin_hour, stretch=0)

        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setValue(0)
        self.spin_minute.setSuffix("m")
        self.spin_minute.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.spin_minute.setFixedWidth(65)
        time_row.addWidget(self.spin_minute, stretch=0)

        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("Type date...")
        self.txt_date.setToolTip("Enter date text (e.g. '15 Jan 3019')")
        self.txt_date.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
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
        cal_path = os.path.join(
            "default_assets", "icons", "ui_icons", "calendar.svg"
        )
        clock_path = os.path.join(
            "default_assets", "icons", "ui_icons", "clock.svg"
        )
        self.btn_calendar.setIcon(load_icon(cal_path, color=color))
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

        self._populate_months()
        self._populate_days()
        self._update_preview()

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
            if current_index >= 0 and current_index < self.combo_month.count():
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
            if current_day >= 0 and current_day < days_in_month:
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

        self._update_preview()
        value = self.get_value()
        self.value_changed.emit(value)

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Handles theme changes to update icons and styles."""
        self._apply_styles()
        self._update_icons(theme)

    @Slot()
    def _on_text_edited(self) -> None:
        """Handles manual text input."""
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
        finally:
            self._updating = prev_updating

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
            self.spin_year.setValue(year)
            self.combo_month.setCurrentIndex(month - 1)
            self._populate_days()
            self.combo_day.setCurrentIndex(day - 1)

    def minimumSizeHint(self) -> QSize:
        """Returns the minimum size hint to prevent vertical collapse.

        Returns:
            QSize: Minimum size reserved for the complete date control.

        """
        return QSize(250, 72)

    def sizeHint(self) -> QSize:
        """Returns the preferred size hint.

        Returns:
            QSize: Dynamic preferred size based on time row visibility.

        """
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
