"""
Lore Duration Widget Module.

Provides a structured input for event duration (Years, Months, Days, Hours, Minutes)
and calculates the floating point day duration based on a start date context.
"""

import logging
from typing import Optional

from PySide6.QtCore import QSize, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from src.core.calendar import CalendarConverter, CalendarDate

logger = logging.getLogger(__name__)


class LoreDurationWidget(QWidget):
    """
    Widget for inputting duration in semantic units.
    Calculates absolute duration based on a start date context.
    """

    value_changed = Signal(float)  # Emits duration in days

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the LoreDurationWidget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        # Set size policy to prevent vertical squashing
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._converter: CalendarConverter = None
        self._start_date_float: float = 1.0  # Default to Year 1 Day 1
        self._updating = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Creates and layouts the duration input spinboxes."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Years
        self.spin_years = self._create_spinbox("Years")
        layout.addWidget(self.spin_years)
        layout.addWidget(QLabel("Y"))

        # Months
        self.spin_months = self._create_spinbox("Months")
        layout.addWidget(self.spin_months)
        layout.addWidget(QLabel("M"))

        # Days
        self.spin_days = self._create_spinbox("Days")
        layout.addWidget(self.spin_days)
        layout.addWidget(QLabel("D"))

        # Hours
        self.spin_hours = self._create_spinbox("Hours")
        layout.addWidget(self.spin_hours)
        layout.addWidget(QLabel("h"))

        # Minutes
        self.spin_minutes = self._create_spinbox("Minutes")
        self.spin_minutes.setRange(0, 60)  # Allow > 59? Maybe wrap. For now strict.
        layout.addWidget(self.spin_minutes)
        layout.addWidget(QLabel("m"))

        layout.addStretch()

    def _create_spinbox(self, tooltip: str) -> QSpinBox:
        """
        Creates a configured QSpinBox for duration input.

        Args:
            tooltip: Tooltip text for the spinbox.

        Returns:
            QSpinBox: Configured spinbox widget.
        """
        spin = QSpinBox()
        spin.setRange(0, 999999)
        spin.setValue(0)
        spin.setToolTip(tooltip)
        spin.valueChanged.connect(self._on_input_changed)
        return spin

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """
        Sets the calendar converter for accurate duration calculations.

        Args:
            converter: CalendarConverter instance for date/time calculations.
        """
        self._converter = converter
        self._on_input_changed()

    def set_start_date(self, start_date_float: float) -> None:
        """Sets the context date for duration calculation."""
        # Only update if changed meaningfully to avoid feedback loops if any
        if abs(self._start_date_float - start_date_float) > 0.0001:
            self._start_date_float = start_date_float
            # Recalculate duration float based on new start date + preserved inputs
            self._on_input_changed()

    @Slot()
    def _on_input_changed(self) -> None:
        """
        Handles changes to duration inputs and emits the calculated duration.

        Recalculates total duration in days based on current spinbox values
        and the configured calendar converter.
        """
        if self._updating:
            return

        duration = self.get_value()
        self.value_changed.emit(duration)

    def get_value(self) -> float:
        """Calculates duration in days based on semantic inputs and start date."""
        if not self._converter:
            # Fallback for no calendar: assume 365/30/1 standard?
            # Or just return days + fraction
            days = self.spin_days.value()
            days += self.spin_years.value() * 365
            days += self.spin_months.value() * 30
            days += self.spin_hours.value() / 24.0
            days += self.spin_minutes.value() / (24.0 * 60.0)
            return float(days)

        years = self.spin_years.value()
        months = self.spin_months.value()
        days_delta = self.spin_days.value()
        hours = self.spin_hours.value()
        minutes = self.spin_minutes.value()

        if (
            years == 0
            and months == 0
            and days_delta == 0
            and hours == 0
            and minutes == 0
        ):
            return 0.0

        # Logic:
        # 1. From Start Date (float) -> Start CalendarDate
        # 2. Add Years, Months
        # 3. Handle Month/Day overflow logic
        # 4. Add Days, Hours, Minutes
        # 5. Convert End CalendarDate -> End Float
        # 6. Return End Float - Start Float

        start_date = self._converter.from_float(self._start_date_float)

        # Target calculation (naive implementation of "Add semantic time")

        # 1. Add Years
        target_year = start_date.year + years

        # 2. Add Months
        # This is tricky because months have names/indices.
        # Simple math: target_month_index = (start.month - 1) + months
        # Resolve to Year/Month

        # Get all months for the CURRENT year structure
        # (simplified assumption: year structure doesn't change wildly)
        # Actually, we need to step through years if month count varies per year?
        # Let's assume standard month carrying for now.

        config = self._converter._config

        # We need a robust "add months" logic that handles changing year lengths
        # (YearVariants).
        # But `CalendarConverter` doesn't expose `add_months`.

        # Iterative approach for robustness:
        # Add years first (easy, just change year number).
        # But wait, if we are on day 31 and go to a year where that month has 28 days?
        # Clamp day? usually yes.

        # Step 1: Add Years
        curr_year = target_year

        # Step 2: Add Months
        # We need to loop because each year might have diff number of months
        curr_month_idx = start_date.month - 1  # 0-based
        months_to_add = months

        while months_to_add > 0:
            # Get months in current year
            year_months = config.get_months_for_year(curr_year)
            months_in_year = len(year_months)

            remaining_in_year = months_in_year - curr_month_idx

            if months_to_add >= remaining_in_year:
                # Skip to next year
                months_to_add -= remaining_in_year
                curr_year += 1
                curr_month_idx = 0  # Start of next year
            else:
                # Add within current year
                curr_month_idx += months_to_add
                months_to_add = 0

        target_month = curr_month_idx + 1  # 1-based

        # Clamp Day
        target_months_def = config.get_months_for_year(curr_year)
        # Handle edge case: if target month index is out of bounds (shouldn't be
        # with above logic logic, but what if we landed on a leap month that
        # doesn't exist? CalendarDate handles existence?)
        if curr_month_idx >= len(target_months_def):
            curr_month_idx = len(target_months_def) - 1
            target_month = curr_month_idx + 1

        max_days = target_months_def[curr_month_idx].days
        target_day = min(start_date.day, max_days)

        # Step 3: Add Days
        # We need Date -> Float here. Converter from_float handles overflow.
        # Actually, simpler: Get the float for (Year, Month, ClampedDay, Time).
        # Then add days_delta + time.

        # Reconstruct "intermediate" date
        intermediate_date = CalendarDate(
            year=curr_year,
            month=target_month,
            day=target_day,
            time_fraction=start_date.time_fraction,
        )

        intermediate_float = self._converter.to_float(intermediate_date)

        # Add remaining days/time
        additional_days = days_delta
        additional_days += hours / 24.0
        additional_days += minutes / (24.0 * 60.0)

        final_float = intermediate_float + additional_days

        return final_float - self._start_date_float

    def set_value(self, days_float: float) -> None:
        """
        Sets the inputs based on a float duration.
        Attempts to decompose into semantic units (Years, Months, Days).
        """
        if self._updating:
            return

        # Check if current inputs already result in roughly this float
        current_calc = self.get_value()
        if abs(current_calc - days_float) < 0.001:
            return

        self._updating = True
        try:
            # 1. Start with robust decomposition if Converter is available
            if self._converter and self._converter._config:
                config = self._converter._config

                # We need to simulate walking forward from Start Date
                # to see how many full years/months fit into 'days_float'.

                start_date = self._converter.from_float(self._start_date_float)
                target_float = self._start_date_float + days_float

                # Current simulation state
                curr_float = self._start_date_float
                curr_date = start_date

                years_count = 0
                months_count = 0

                # --- Count Years ---
                # Heuristic: Check if moving +1 year keeps us <= target_float
                # But "moving +1 year" is context dependent (year length).
                # We can just iterate.
                while True:
                    # Get length of current year
                    # Current year is curr_date.year
                    # But wait, date logic is complex.
                    # Simplification: Calculate float for (Year+1, Month, Day)

                    next_year = curr_date.year + 1
                    # Handle leap days/missing days in target year?
                    # CalendarConverter handles "valid date" clamping usually via
                    # from_float or to_float? Let's perform a check:
                    try:
                        # Construct candidate date for same Month/Day in next year
                        # We need to know max days in that month for next year to clamp
                        months_def = config.get_months_for_year(next_year)
                        target_month_idx = curr_date.month - 1
                        if target_month_idx >= len(months_def):
                            target_month_idx = len(months_def) - 1

                        max_days = months_def[target_month_idx].days
                        clamped_day = min(curr_date.day, max_days)

                        candidate_date = CalendarDate(
                            year=next_year,
                            month=target_month_idx + 1,
                            day=clamped_day,
                            time_fraction=curr_date.time_fraction,
                        )
                        candidate_float = self._converter.to_float(candidate_date)

                        if (
                            candidate_float <= target_float + 0.0001
                        ):  # Epsilon for float math
                            years_count += 1
                            curr_date = candidate_date
                            curr_float = candidate_float
                        else:
                            break
                    except Exception:
                        break

                # --- Count Months ---
                while True:
                    # Next month logic
                    # Advance month index
                    next_month = curr_date.month + 1
                    next_year = curr_date.year
                    months_def = config.get_months_for_year(next_year)

                    if next_month > len(months_def):
                        next_month = 1
                        next_year += 1
                        months_def = config.get_months_for_year(next_year)

                    # Clamp day
                    target_month_idx = next_month - 1
                    if target_month_idx >= len(months_def):
                        # Should not happen if logic is correct
                        break

                    max_days = months_def[target_month_idx].days
                    clamped_day = min(curr_date.day, max_days)

                    try:
                        candidate_date = CalendarDate(
                            year=next_year,
                            month=next_month,
                            day=clamped_day,
                            time_fraction=curr_date.time_fraction,
                        )
                        candidate_float = self._converter.to_float(candidate_date)

                        if (
                            candidate_float <= target_float + 0.0001
                        ):  # Epsilon for float math
                            months_count += 1
                            curr_date = candidate_date
                            curr_float = candidate_float
                        else:
                            break
                    except Exception:
                        break

                # --- Remaining Days / Time ---
                remaining_days = target_float - curr_float

                d = int(remaining_days)
                rem = (remaining_days - d) * 24
                h = int(rem)
                rem = (rem - h) * 60
                m = int(round(rem))

                self.spin_years.setValue(years_count)
                self.spin_months.setValue(months_count)
                self.spin_days.setValue(d)
                self.spin_hours.setValue(h)
                self.spin_minutes.setValue(m)

            else:
                # No calendar fallback
                total_days = days_float
                d = int(total_days)
                rem = (total_days - d) * 24
                h = int(rem)
                rem = (rem - h) * 60
                m = int(round(rem))

                self.spin_years.setValue(0)
                self.spin_months.setValue(0)
                self.spin_days.setValue(d)
                self.spin_hours.setValue(h)
                self.spin_minutes.setValue(m)

        finally:
            self._updating = False

    def minimumSizeHint(self) -> QSize:
        """
        Returns the minimum size hint to prevent vertical collapse.

        Returns:
            QSize: Minimum size for the lore duration widget.
        """
        from PySide6.QtCore import QSize

        return QSize(350, 40)  # Single row of controls

    def sizeHint(self) -> QSize:
        """
        Returns the preferred size hint.

        Returns:
            QSize: Preferred size for comfortable duration input.
        """
        from PySide6.QtCore import QSize

        return QSize(450, 40)  # Comfortable size for single-row layout
