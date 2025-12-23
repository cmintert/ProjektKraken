"""
Compact Duration Widget Module.

Provides a polished, calendar-aware duration input widget with:
- Year, Month, Day spinboxes with labels AFTER inputs
- Hour and Minute spinboxes
- Smart decomposition of float durations
- Preview label with written format (hides zero values)
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.gui.utils.style_helper import StyleHelper


class CompactDurationWidget(QWidget):
    """
    A polished duration input widget with calendar-aware decomposition.

    Features:
    - Spinboxes for Years, Months, Days, Hours, Minutes
    - Labels after inputs (e.g., "1 Year")
    - Smart set_value that decomposes days into semantic units
    - Preview label that hides zero values

    Signals:
        value_changed: Emitted when the duration value changes.
    """

    value_changed = Signal(float)

    def __init__(self, parent=None):
        """
        Initializes the compact duration widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        # Set size policy to prevent vertical squashing
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._converter = None
        self._start_date_float = 0.0
        self._updating = False

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Sets up the widget UI."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Styled frame container
        self.frame = QFrame()
        self.frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.frame.setStyleSheet(StyleHelper.get_frame_style())
        outer_layout.addWidget(self.frame)

        main_layout = QVBoxLayout(self.frame)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(2)

        # Row 1: Years, Months, Days
        ymd_row = QHBoxLayout()
        ymd_row.setSpacing(12)

        # Years - allow expanding with suffix
        from PySide6.QtWidgets import QSizePolicy

        self.spin_years = QSpinBox()
        self.spin_years.setRange(0, 9999)
        self.spin_years.setValue(0)
        self.spin_years.setSuffix(" Y")
        self.spin_years.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ymd_row.addWidget(self.spin_years, stretch=1)

        # Months - allow expanding with suffix
        self.spin_months = QSpinBox()
        self.spin_months.setRange(0, 99)
        self.spin_months.setValue(0)
        self.spin_months.setSuffix(" M")
        self.spin_months.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ymd_row.addWidget(self.spin_months, stretch=1)

        # Days - allow expanding with suffix
        self.spin_days = QSpinBox()
        self.spin_days.setRange(0, 999)
        self.spin_days.setValue(0)
        self.spin_days.setSuffix(" D")
        self.spin_days.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ymd_row.addWidget(self.spin_days, stretch=1)

        main_layout.addLayout(ymd_row)

        # Row 2: Hours, Minutes, Preview
        hm_row = QHBoxLayout()
        hm_row.setSpacing(12)

        # Hours - allow expanding with suffix
        self.spin_hours = QSpinBox()
        self.spin_hours.setRange(0, 23)
        self.spin_hours.setValue(0)
        self.spin_hours.setSuffix(" h")
        self.spin_hours.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hm_row.addWidget(self.spin_hours, stretch=1)

        # Minutes - allow expanding with suffix
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(0, 59)
        self.spin_minutes.setValue(0)
        self.spin_minutes.setSuffix(" m")
        self.spin_minutes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hm_row.addWidget(self.spin_minutes, stretch=1)

        # Preview - takes remaining space
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet(StyleHelper.get_preview_label_style())
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hm_row.addWidget(self.lbl_preview, stretch=3)  # Wider for text

        main_layout.addLayout(hm_row)

    def _connect_signals(self):
        """Connects internal signals."""
        self.spin_years.valueChanged.connect(self._on_input_changed)
        self.spin_months.valueChanged.connect(self._on_input_changed)
        self.spin_days.valueChanged.connect(self._on_input_changed)
        self.spin_hours.valueChanged.connect(self._on_input_changed)
        self.spin_minutes.valueChanged.connect(self._on_input_changed)

    def set_calendar_converter(self, converter: CalendarConverter):
        """
        Sets the calendar converter for calculations.

        Args:
            converter: CalendarConverter instance.
        """
        self._converter = converter
        self._update_preview()

    def set_start_date(self, start_date_float: float):
        """
        Sets the start date for duration calculations.

        The start date affects how months/years are calculated since
        month lengths can vary.

        Args:
            start_date_float: Start date as absolute day float.
        """
        self._start_date_float = start_date_float

    def _on_input_changed(self):
        """Handles any input change."""
        if self._updating:
            return

        self._update_preview()
        value = self.get_value()
        self.value_changed.emit(value)

    def _update_preview(self):
        """Updates the preview label with written format."""
        parts = []

        years = self.spin_years.value()
        months = self.spin_months.value()
        days = self.spin_days.value()
        hours = self.spin_hours.value()
        minutes = self.spin_minutes.value()

        if years > 0:
            parts.append(f"{years} Year" if years == 1 else f"{years} Years")
        if months > 0:
            parts.append(f"{months} Month" if months == 1 else f"{months} Months")
        if days > 0:
            parts.append(f"{days} Day" if days == 1 else f"{days} Days")
        if hours > 0:
            parts.append(f"{hours} Hour" if hours == 1 else f"{hours} Hours")
        if minutes > 0:
            parts.append(f"{minutes} Minute" if minutes == 1 else f"{minutes} Minutes")

        if parts:
            self.lbl_preview.setText(", ".join(parts))
        else:
            self.lbl_preview.setText("0 Days")

    def get_value(self) -> float:
        """
        Gets the current duration as a float value in days.

        Returns:
            float: Duration in days.
        """
        years = self.spin_years.value()
        months = self.spin_months.value()
        days = self.spin_days.value()
        hours = self.spin_hours.value()
        minutes = self.spin_minutes.value()

        if not self._converter:
            # Fallback: Use average values
            days_per_year = 365
            days_per_month = 30
            total = (
                years * days_per_year
                + months * days_per_month
                + days
                + (hours * 60 + minutes) / (24 * 60)
            )
            return total

        # Calendar-aware calculation
        total_days = 0.0

        # Calculate years (from start date)
        current_float = self._start_date_float
        for _ in range(years):
            if self._converter:
                date = self._converter.from_float(current_float)
                year_length = self._converter._config.get_year_length(date.year)
                total_days += year_length
                current_float += year_length

        # Calculate months
        for _ in range(months):
            if self._converter:
                date = self._converter.from_float(current_float)
                month_defs = self._converter._config.get_months_for_year(date.year)
                if 0 <= date.month - 1 < len(month_defs):
                    month_days = month_defs[date.month - 1].days
                else:
                    month_days = 30
                total_days += month_days
                current_float += month_days

        # Add days
        total_days += days

        # Add time
        total_days += (hours * 60 + minutes) / (24 * 60)

        return total_days

    def set_value(self, days_float: float):
        """
        Sets the duration from a float value, decomposing into Y/M/D.

        Args:
            days_float: Duration in days.
        """
        if self._updating:
            return

        self._updating = True
        try:
            if days_float <= 0:
                self.spin_years.setValue(0)
                self.spin_months.setValue(0)
                self.spin_days.setValue(0)
                self.spin_hours.setValue(0)
                self.spin_minutes.setValue(0)
                self._update_preview()
                return

            if not self._converter:
                # Fallback without converter
                years = int(days_float // 365)
                remaining = days_float % 365
                months = int(remaining // 30)
                remaining = remaining % 30
                days = int(remaining)
                fractional = remaining - days
                hours = int(fractional * 24)
                minutes = int((fractional * 24 - hours) * 60)

                self.spin_years.setValue(years)
                self.spin_months.setValue(months)
                self.spin_days.setValue(days)
                self.spin_hours.setValue(hours)
                self.spin_minutes.setValue(minutes)
                self._update_preview()
                return

            # Calendar-aware decomposition
            remaining = days_float
            years = 0
            months = 0
            days = 0

            # Calculate years
            current_float = self._start_date_float
            while remaining > 0:
                date = self._converter.from_float(current_float)
                year_length = self._converter._config.get_year_length(date.year)
                if remaining >= year_length:
                    years += 1
                    remaining -= year_length
                    current_float += year_length
                else:
                    break

            # Calculate months
            while remaining > 0:
                date = self._converter.from_float(current_float)
                month_defs = self._converter._config.get_months_for_year(date.year)
                if 0 <= date.month - 1 < len(month_defs):
                    month_days = month_defs[date.month - 1].days
                else:
                    month_days = 30

                if remaining >= month_days:
                    months += 1
                    remaining -= month_days
                    current_float += month_days
                else:
                    break

            # Remaining is days (+ fraction)
            days = int(remaining)
            fractional = remaining - days

            # Convert fraction to hours/minutes
            total_minutes = int(fractional * 24 * 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60

            self.spin_years.setValue(years)
            self.spin_months.setValue(months)
            self.spin_days.setValue(days)
            self.spin_hours.setValue(hours)
            self.spin_minutes.setValue(minutes)

            self._update_preview()

        finally:
            self._updating = False

    def minimumSizeHint(self):
        """
        Returns the minimum size hint to prevent vertical collapse.

        Returns:
            QSize: Minimum size for the duration widget (two rows of controls).
        """
        from PySide6.QtCore import QSize

        return QSize(250, 72)  # Two rows of controls + frame padding

    def sizeHint(self):
        """
        Returns the preferred size hint.

        Returns:
            QSize: Preferred size for comfortable duration input.
        """
        from PySide6.QtCore import QSize

        return QSize(350, 80)  # Comfortable size for two-row layout
