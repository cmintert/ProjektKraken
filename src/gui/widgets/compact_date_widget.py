"""
Compact Date Widget Module.

Provides a polished, calendar-aware date input widget with:
- Year spinbox
- Month dropdown (populated from calendar)
- Day dropdown (adjusts to month length)
- Optional time inputs (hour/minute)
- Calendar popup button
- Live preview of formatted date
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter, CalendarDate
from src.gui.utils.style_helper import StyleHelper


class CompactDateWidget(QWidget):
    """
    A polished date input widget with calendar-aware dropdowns.

    Features:
    - Year spinbox
    - Month dropdown with calendar-specific names
    - Day dropdown that adjusts to month length
    - Hour/Minute inputs for time
    - Calendar popup for visual date selection
    - Live preview of formatted date

    Signals:
        value_changed: Emitted when the date value changes.
    """

    value_changed = Signal(float)

    def __init__(self, parent=None):
        """
        Initializes the compact date widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._converter = None
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

        # Row 1: Date inputs
        date_row = QHBoxLayout()
        date_row.setSpacing(8)

        # Year - allow expanding
        from PySide6.QtWidgets import QSizePolicy

        self.spin_year = QSpinBox()
        self.spin_year.setRange(-9999, 9999)
        self.spin_year.setValue(1)
        self.spin_year.setPrefix("Year ")
        self.spin_year.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        date_row.addWidget(self.spin_year, stretch=2)  # Higher stretch factor

        # Month dropdown - widen stretch
        self.combo_month = QComboBox()
        self.combo_month.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        date_row.addWidget(self.combo_month, stretch=3)  # Widest element

        # Day dropdown - moderate stretch
        self.combo_day = QComboBox()
        self.combo_day.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        date_row.addWidget(self.combo_day, stretch=1)

        # Calendar button with icon
        self.btn_calendar = QPushButton("📅")
        self.btn_calendar.setFixedWidth(32)  # Icon button - fixed small size
        self.btn_calendar.setToolTip("Open calendar picker")
        date_row.addWidget(self.btn_calendar, stretch=0)

        date_row.addStretch()
        main_layout.addLayout(date_row)

        # Row 2: Time inputs
        time_row = QHBoxLayout()
        time_row.setSpacing(8)

        # Hour - allow expanding
        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setValue(0)
        self.spin_hour.setSuffix("h")
        self.spin_hour.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        time_row.addWidget(self.spin_hour, stretch=1)

        # Minute - allow expanding
        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setValue(0)
        self.spin_minute.setSuffix("m")
        self.spin_minute.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        time_row.addWidget(self.spin_minute, stretch=1)

        # Preview label - takes remaining space
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet(StyleHelper.get_preview_label_style())
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        time_row.addWidget(self.lbl_preview, stretch=4)  # Wider for text

        time_row.addStretch()
        main_layout.addLayout(time_row)

        # Initialize with default months
        self._populate_months()
        self._populate_days()

    def _connect_signals(self):
        """Connects internal signals."""
        self.spin_year.valueChanged.connect(self._on_input_changed)
        self.combo_month.currentIndexChanged.connect(self._on_month_changed)
        self.combo_day.currentIndexChanged.connect(self._on_input_changed)
        self.spin_hour.valueChanged.connect(self._on_input_changed)
        self.spin_minute.valueChanged.connect(self._on_input_changed)
        self.btn_calendar.clicked.connect(self._open_calendar_popup)

    def set_calendar_converter(self, converter: CalendarConverter):
        """
        Sets the calendar converter for date calculations.

        Args:
            converter: CalendarConverter instance.
        """
        self._converter = converter
        self._populate_months()
        self._populate_days()
        self._update_preview()

    def _populate_months(self):
        """Populates month dropdown from calendar."""
        self._updating = True
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

        self._updating = False

    def _populate_days(self):
        """Populates day dropdown based on selected month."""
        self._updating = True
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
        self._updating = False

    def _on_month_changed(self, index):
        """Handles month selection change."""
        self._populate_days()
        self._on_input_changed()

    def _on_input_changed(self):
        """Handles any input change."""
        if self._updating:
            return

        self._update_preview()
        value = self.get_value()
        self.value_changed.emit(value)

    def _update_preview(self):
        """Updates the preview label."""
        if not self._converter:
            self.lbl_preview.setText("")
            return

        try:
            value = self.get_value()
            formatted = self._converter.format_date(value)
            self.lbl_preview.setText(formatted)
        except Exception:
            self.lbl_preview.setText("")

    def get_value(self) -> float:
        """
        Gets the current date as a float value.

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
            days = (year - 1) * 365 + (month - 1) * 30 + (day - 1)
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

    def set_value(self, days_float: float):
        """
        Sets the date from a float value.

        Args:
            days_float: Absolute day value.
        """
        if self._updating:
            return

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
            self._updating = False

    def _open_calendar_popup(self):
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
        if popup.exec() == QDialog.Accepted:
            year, month, day = popup.get_selected_date()
            self.spin_year.setValue(year)
            self.combo_month.setCurrentIndex(month - 1)
            self._populate_days()
            self.combo_day.setCurrentIndex(day - 1)


class CalendarPopup(QDialog):
    """
    A popup dialog for visual date selection.

    Shows a grid of days for the selected month.
    """

    def __init__(
        self,
        parent,
        converter: CalendarConverter,
        year: int,
        month: int,
        day: int,
    ):
        """
        Initializes the calendar popup.

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

    def _setup_ui(self):
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
        self.spin_year.setRange(-9999, 9999)
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

    def _refresh_grid(self):
        """Refreshes the day grid."""
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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

    def _select_day(self, day: int):
        """Selects a day and accepts."""
        self._selected_day = day
        self._year = self.spin_year.value()
        self._month = self.combo_month.currentIndex() + 1
        self.accept()

    def get_selected_date(self):
        """Returns the selected date as (year, month, day)."""
        return self._year, self._month, self._selected_day
