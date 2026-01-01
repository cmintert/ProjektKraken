"""
Lore Date Widget Module.

Provides a structured date input widget that adapts to calendar configuration,
with Year/Month/Day dropdowns and fallback to raw float input.
"""

import logging
from typing import Optional

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from src.core.calendar import CalendarConverter, CalendarDate
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class LoreDateWidget(QWidget):
    """
    A composite widget for entering lore dates with structured fields.

    Provides Year/Month/Day dropdowns that adapt to the configured calendar,
    with a toggle to switch to raw float input mode.

    Signals:
        value_changed(float): Emitted when the date value changes.
    """

    value_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the lore date widget.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        # Set size policy to prevent vertical squashing
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._converter: CalendarConverter = None
        self._updating = False  # Prevents signal loops during updates

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the widget UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Year spinbox (allows negative for pre-Epoch)
        self._year_spin = QSpinBox()
        self._year_spin.setRange(-10000, 10000)
        self._year_spin.setValue(1)
        self._year_spin.setPrefix("Year ")
        self._year_spin.valueChanged.connect(self._on_structured_changed)
        layout.addWidget(self._year_spin)

        # Month combo
        self._month_combo = QComboBox()
        self._month_combo.currentIndexChanged.connect(self._on_month_changed)
        layout.addWidget(self._month_combo)

        # Day combo
        self._day_combo = QComboBox()
        self._day_combo.currentIndexChanged.connect(self._on_structured_changed)
        layout.addWidget(self._day_combo)

        # Hour combo (0-23)
        self._hour_combo = QComboBox()
        for h in range(24):
            self._hour_combo.addItem(f"{h:02d}h")
        self._hour_combo.setCurrentIndex(0)
        self._hour_combo.currentIndexChanged.connect(self._on_structured_changed)
        layout.addWidget(self._hour_combo)

        # Minute combo (0-59, 5-minute intervals)
        self._minute_combo = QComboBox()
        for m in range(0, 60, 5):
            self._minute_combo.addItem(f"{m:02d}m")
        self._minute_combo.setCurrentIndex(0)
        self._minute_combo.currentIndexChanged.connect(self._on_structured_changed)
        layout.addWidget(self._minute_combo)

        # Raw float spinbox (hidden by default)
        self._raw_spin = QDoubleSpinBox()
        self._raw_spin.setRange(-1e12, 1e12)
        self._raw_spin.setDecimals(4)  # More precision for time fractions
        self._raw_spin.setPrefix("Float: ")
        self._raw_spin.valueChanged.connect(self._on_raw_changed)
        self._raw_spin.setVisible(False)
        layout.addWidget(self._raw_spin)

        # Raw mode toggle
        self._raw_toggle = QCheckBox("Raw")
        self._raw_toggle.setToolTip("Toggle raw float input mode")
        self._raw_toggle.toggled.connect(self._on_raw_toggle)
        layout.addWidget(self._raw_toggle)

        # Preview label
        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(StyleHelper.get_preview_label_style())
        layout.addWidget(self._preview_label)

        layout.addStretch()

        # Initialize with disabled structured mode (no calendar)
        self._set_structured_enabled(False)

    def _set_structured_enabled(self, enabled: bool) -> None:
        """
        Enables or disables structured input mode.

        Args:
            enabled: Whether structured mode should be enabled.
        """
        self._year_spin.setEnabled(enabled)
        self._month_combo.setEnabled(enabled)
        self._day_combo.setEnabled(enabled)
        self._hour_combo.setEnabled(enabled)
        self._minute_combo.setEnabled(enabled)

        if not enabled:
            # Force raw mode when no calendar
            self._raw_toggle.setChecked(True)
            self._raw_toggle.setEnabled(False)
        else:
            self._raw_toggle.setEnabled(True)

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """
        Sets the calendar converter for date formatting.

        Args:
            converter: CalendarConverter instance or None.
        """
        self._converter = converter

        if converter:
            self._populate_month_combo()
            self._update_day_combo()
            self._set_structured_enabled(True)
            # Explicitly switch to structured mode
            self._raw_toggle.blockSignals(True)  # Prevent signal loop
            self._raw_toggle.setChecked(False)
            self._raw_toggle.blockSignals(False)
            # Set visibility explicitly
            self._year_spin.setVisible(True)
            self._month_combo.setVisible(True)
            self._day_combo.setVisible(True)
            self._hour_combo.setVisible(True)
            self._minute_combo.setVisible(True)
            self._raw_spin.setVisible(False)
        else:
            self._set_structured_enabled(False)

        self._update_preview()

    def _populate_month_combo(self) -> None:
        """Populates the month dropdown from calendar config."""
        if not self._converter:
            return

        self._updating = True
        self._month_combo.clear()

        year = self._year_spin.value()
        months = self._converter._config.get_months_for_year(year)

        for month in months:
            self._month_combo.addItem(month.name)

        self._updating = False

    def _update_day_combo(self) -> None:
        """Updates the day dropdown based on selected month."""
        if not self._converter:
            return

        self._updating = True

        # Remember current selection
        current_day_index = max(0, self._day_combo.currentIndex())

        year = self._year_spin.value()
        month_index = self._month_combo.currentIndex()
        if month_index < 0:
            month_index = 0

        months = self._converter._config.get_months_for_year(year)
        if month_index < len(months):
            num_days = months[month_index].days
        else:
            num_days = 30  # Fallback

        self._day_combo.clear()
        for d in range(1, num_days + 1):
            self._day_combo.addItem(f"Day {d}")

        # Restore selection, clamped to valid range
        if current_day_index >= num_days:
            current_day_index = num_days - 1
        self._day_combo.setCurrentIndex(current_day_index)

        self._updating = False

    def _on_month_changed(self, index: int) -> None:
        """
        Handles month selection change.

        Args:
            index: New month index.
        """
        if self._updating:
            return

        self._update_day_combo()
        self._on_structured_changed()

    def _on_structured_changed(self) -> None:
        """Handles changes to structured fields."""
        if self._updating:
            return

        self._update_preview()
        self.value_changed.emit(self.get_value())

    def _on_raw_changed(self, value: float) -> None:
        """
        Handles changes to raw float spinbox.

        Args:
            value: New float value.
        """
        if self._updating:
            return

        self._update_preview()
        self.value_changed.emit(value)

    def _on_raw_toggle(self, checked: bool) -> None:
        """
        Handles raw mode toggle.

        Args:
            checked: Whether raw mode is enabled.
        """
        if checked:
            # Switching to raw mode - compute value from structured fields
            # Note: isChecked() is already True at this point, so we must
            # compute the value directly from structured fields
            current_value = self._get_structured_value()
            self._raw_spin.setValue(current_value)

            self._year_spin.setVisible(False)
            self._month_combo.setVisible(False)
            self._day_combo.setVisible(False)
            self._hour_combo.setVisible(False)
            self._minute_combo.setVisible(False)
            self._raw_spin.setVisible(True)
        else:
            # Switching to structured mode - sync from raw
            raw_value = self._raw_spin.value()
            self._set_value_internal(raw_value)

            self._year_spin.setVisible(True)
            self._month_combo.setVisible(True)
            self._day_combo.setVisible(True)
            self._hour_combo.setVisible(True)
            self._minute_combo.setVisible(True)
            self._raw_spin.setVisible(False)

        self._update_preview()

    def _get_structured_value(self) -> float:
        """
        Gets the date value from structured fields only.

        Returns:
            float: The computed float value from Year/Month/Day fields.
        """
        if not self._converter:
            return 0.0

        year = self._year_spin.value()
        month_index = self._month_combo.currentIndex()
        day_index = self._day_combo.currentIndex()

        # Handle empty combos
        if month_index < 0:
            month_index = 0
        if day_index < 0:
            day_index = 0

        month = month_index + 1  # 1-indexed
        day = day_index + 1  # 1-indexed

        # Clamp to valid ranges
        months = self._converter._config.get_months_for_year(year)
        if month > len(months):
            month = len(months) if len(months) > 0 else 1
        if len(months) > 0 and day > months[month - 1].days:
            day = months[month - 1].days

        # Calculate time fraction from hour/minute
        hour_index = self._hour_combo.currentIndex()
        minute_index = self._minute_combo.currentIndex()
        if hour_index < 0:
            hour_index = 0
        if minute_index < 0:
            minute_index = 0
        hour = hour_index
        minute = minute_index * 5  # 5-minute intervals
        time_fraction = (hour + minute / 60.0) / 24.0

        from src.core.calendar import CalendarDate

        date = CalendarDate(
            year=year,
            month=month,
            day=day,
            time_fraction=time_fraction,
        )

        return self._converter.to_float(date)

    def _update_preview(self) -> None:
        """Updates the formatted date preview label."""
        if self._converter:
            try:
                value = self.get_value()
                formatted = self._converter.format_date(value)
                self._preview_label.setText(f"({formatted})")
            except Exception as e:
                logger.debug(f"Preview format error: {e}")
                self._preview_label.setText("")
        else:
            self._preview_label.setText("")

    def set_value(self, float_value: float) -> None:
        """
        Sets the date value from a float.

        Args:
            float_value: The absolute day float value.
        """
        if self._raw_toggle.isChecked():
            self._raw_spin.setValue(float_value)
        else:
            self._set_value_internal(float_value)

        self._update_preview()

    def _set_value_internal(self, float_value: float) -> None:
        """
        Updates structured fields from a float value.

        Args:
            float_value: The absolute day float value.
        """
        if not self._converter:
            self._raw_spin.setValue(float_value)
            return

        self._updating = True

        try:
            date = self._converter.from_float(float_value)

            self._year_spin.setValue(date.year)

            # Re-populate months for this year (may have variants)
            self._populate_month_combo()

            # Set month index (1-indexed to 0-indexed)
            month_index = date.month - 1
            if month_index < self._month_combo.count():
                self._month_combo.setCurrentIndex(month_index)

            # Update and set day
            self._update_day_combo()
            day_index = date.day - 1
            if day_index < self._day_combo.count():
                self._day_combo.setCurrentIndex(day_index)

            # Set hour and minute from time_fraction
            total_hours = date.time_fraction * 24
            hour = int(total_hours)
            minute = int((total_hours - hour) * 60)
            # Round minute to nearest 5-minute interval
            minute_index = round(minute / 5)
            if minute_index >= 12:
                minute_index = 11
            self._hour_combo.setCurrentIndex(min(hour, 23))
            self._minute_combo.setCurrentIndex(minute_index)

        except Exception as e:
            logger.warning(f"Failed to set structured date from {float_value}: {e}")
            self._raw_spin.setValue(float_value)

        self._updating = False

    def get_value(self) -> float:
        """
        Gets the current date value as a float.

        Returns:
            float: The absolute day float value.
        """
        if self._raw_toggle.isChecked() or not self._converter:
            return self._raw_spin.value()

        # Build CalendarDate from fields
        year = self._year_spin.value()
        month = self._month_combo.currentIndex() + 1  # 1-indexed
        day = self._day_combo.currentIndex() + 1  # 1-indexed

        # Clamp to valid ranges
        months = self._converter._config.get_months_for_year(year)
        if month < 1:
            month = 1
        if month > len(months):
            month = len(months)
        if day < 1:
            day = 1
        if day > months[month - 1].days:
            day = months[month - 1].days

        # Calculate time fraction from hour/minute
        hour = self._hour_combo.currentIndex()
        minute = self._minute_combo.currentIndex() * 5  # 5-minute intervals
        if hour < 0:
            hour = 0
        time_fraction = (hour + minute / 60.0) / 24.0

        date = CalendarDate(
            year=year,
            month=month,
            day=day,
            time_fraction=time_fraction,
        )

        return self._converter.to_float(date)

    def minimumSizeHint(self) -> "QSize":
        """
        Returns the minimum size hint to prevent vertical collapse.

        Returns:
            QSize: Minimum size for the lore date widget.
        """
        from PySide6.QtCore import QSize

        return QSize(400, 40)  # Single row of controls

    def sizeHint(self) -> "QSize":
        """
        Returns the preferred size hint.

        Returns:
            QSize: Preferred size for comfortable date input.
        """
        from PySide6.QtCore import QSize

        return QSize(500, 40)  # Comfortable size for single-row layout
