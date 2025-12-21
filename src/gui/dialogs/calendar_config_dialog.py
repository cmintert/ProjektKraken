"""
Calendar Configuration Dialog Module.

Provides a dialog for editing calendar configurations including
month definitions, week structure, and year variants.
"""

import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)

logger = logging.getLogger(__name__)


class CalendarConfigDialog(QDialog):
    """
    A dialog for creating and editing calendar configurations.

    Provides editors for:
    - Calendar name and epoch
    - Month definitions (name, abbreviation, days)
    - Week day names
    - Live preview of date conversion

    Signals:
        config_saved: Emitted when the user saves a valid configuration.
    """

    config_saved = Signal(CalendarConfig)

    def __init__(
        self,
        parent=None,
        config: Optional[CalendarConfig] = None,
    ):
        """
        Initializes the calendar configuration dialog.

        Args:
            parent: Parent widget.
            config: Optional existing config to edit. If None, creates new.
        """
        super().__init__(parent)
        self.setWindowTitle("Calendar Configuration")
        self.setMinimumSize(600, 500)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._config = config or CalendarConfig.create_default()
        self._validation_errors: List[str] = []

        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        """Sets up the dialog UI components."""
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # --- Header Section ---
        header_group = QGroupBox("Calendar Details")
        header_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Harptos Calendar")
        header_layout.addRow("Calendar Name:", self.name_edit)

        self.epoch_edit = QLineEdit()
        self.epoch_edit.setPlaceholderText("e.g., DR, AD, Year")
        self.epoch_edit.setMaximumWidth(100)
        header_layout.addRow("Epoch Designation:", self.epoch_edit)

        header_group.setLayout(header_layout)
        self.layout.addWidget(header_group)

        # --- Tabs for Months and Week ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Tab 1: Months
        self.month_tab = QWidget()
        month_layout = QVBoxLayout(self.month_tab)

        # Month table
        self.month_table = QTableWidget()
        self.month_table.setColumnCount(3)
        self.month_table.setHorizontalHeaderLabels(["Name", "Abbreviation", "Days"])
        self.month_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.month_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.month_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.month_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.month_table.itemChanged.connect(self._on_month_changed)
        month_layout.addWidget(self.month_table)

        # Month buttons
        month_btn_layout = QHBoxLayout()
        self.btn_add_month = QPushButton("Add Month")
        self.btn_add_month.clicked.connect(self._on_add_month)
        self.btn_remove_month = QPushButton("Remove Selected")
        self.btn_remove_month.clicked.connect(self._on_remove_month)
        month_btn_layout.addWidget(self.btn_add_month)
        month_btn_layout.addWidget(self.btn_remove_month)
        month_btn_layout.addStretch()
        month_layout.addLayout(month_btn_layout)

        self.tabs.addTab(self.month_tab, "Months")

        # Tab 2: Week Days
        self.week_tab = QWidget()
        week_layout = QVBoxLayout(self.week_tab)

        week_info = QLabel("Enter day names separated by commas:")
        week_layout.addWidget(week_info)

        form_layout = QFormLayout()
        self.day_names_edit = QLineEdit()
        self.day_names_edit.setPlaceholderText(
            "e.g., Moonday, Starday, Godsday, Waterday, Earthday, Freeday, Sunday"
        )
        form_layout.addRow("Day Names:", self.day_names_edit)

        self.day_abbrev_edit = QLineEdit()
        self.day_abbrev_edit.setPlaceholderText("e.g., Mo, St, Go, Wa, Ea, Fr, Su")
        form_layout.addRow("Abbreviations:", self.day_abbrev_edit)

        week_layout.addLayout(form_layout)
        week_layout.addStretch()

        self.tabs.addTab(self.week_tab, "Week Days")

        # --- Preview Section ---
        preview_group = QGroupBox("Date Preview")
        preview_layout = QHBoxLayout()

        self.preview_float = QSpinBox()
        self.preview_float.setRange(-1000000, 1000000)
        self.preview_float.setValue(0)
        self.preview_float.valueChanged.connect(self._update_preview)
        preview_layout.addWidget(QLabel("Float:"))
        preview_layout.addWidget(self.preview_float)

        self.preview_label = QLabel("Year 1, Month 1, Day 1")
        self.preview_label.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(QLabel("→"))
        preview_layout.addWidget(self.preview_label)
        preview_layout.addStretch()

        preview_group.setLayout(preview_layout)
        self.layout.addWidget(preview_group)

        # --- Validation Errors ---
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.layout.addWidget(self.error_label)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _load_config(self) -> None:
        """Loads the current config into the UI."""
        self.name_edit.setText(self._config.name)
        self.epoch_edit.setText(self._config.epoch_name)

        # Load months
        self.month_table.blockSignals(True)
        self.month_table.setRowCount(len(self._config.months))
        for row, month in enumerate(self._config.months):
            self.month_table.setItem(row, 0, QTableWidgetItem(month.name))
            self.month_table.setItem(row, 1, QTableWidgetItem(month.abbreviation))

            days_item = QTableWidgetItem(str(month.days))
            days_item.setData(Qt.UserRole, month.days)
            self.month_table.setItem(row, 2, days_item)
        self.month_table.blockSignals(False)

        # Load week
        self.day_names_edit.setText(", ".join(self._config.week.day_names))
        self.day_abbrev_edit.setText(", ".join(self._config.week.day_abbreviations))

        self._update_preview()

    def _on_add_month(self) -> None:
        """Adds a new month row to the table."""
        row = self.month_table.rowCount()
        self.month_table.insertRow(row)
        self.month_table.setItem(row, 0, QTableWidgetItem(f"Month {row + 1}"))
        self.month_table.setItem(row, 1, QTableWidgetItem(f"M{row + 1}"))
        days_item = QTableWidgetItem("30")
        days_item.setData(Qt.UserRole, 30)
        self.month_table.setItem(row, 2, days_item)
        self._update_preview()

    def _on_remove_month(self) -> None:
        """Removes the selected month row."""
        current_row = self.month_table.currentRow()
        if current_row >= 0:
            self.month_table.removeRow(current_row)
            self._update_preview()

    def _on_month_changed(self, item: QTableWidgetItem) -> None:
        """Handles changes to month table cells."""
        # If days column, validate it's a positive integer
        if item.column() == 2:
            try:
                days = int(item.text())
                if days <= 0:
                    raise ValueError("Days must be positive")
                item.setData(Qt.UserRole, days)
            except ValueError:
                item.setBackground(QColor("#ff6b6b"))
                return
            item.setBackground(QColor("transparent"))

        self._update_preview()

    def _build_config_from_ui(self) -> CalendarConfig:
        """
        Builds a CalendarConfig from the current UI state.

        Returns:
            CalendarConfig: The configuration from current form values.
        """
        # Build months
        months = []
        for row in range(self.month_table.rowCount()):
            name_item = self.month_table.item(row, 0)
            abbrev_item = self.month_table.item(row, 1)
            days_item = self.month_table.item(row, 2)

            name = name_item.text() if name_item else f"Month {row + 1}"
            abbrev = abbrev_item.text() if abbrev_item else f"M{row + 1}"
            try:
                days = int(days_item.text()) if days_item else 30
            except ValueError:
                days = 30

            months.append(MonthDefinition(name=name, abbreviation=abbrev, days=days))

        # Build week
        day_names = [
            n.strip() for n in self.day_names_edit.text().split(",") if n.strip()
        ]
        day_abbrevs = [
            a.strip() for a in self.day_abbrev_edit.text().split(",") if a.strip()
        ]

        # Ensure same length
        if len(day_abbrevs) < len(day_names):
            day_abbrevs.extend([d[:2] for d in day_names[len(day_abbrevs) :]])
        elif len(day_abbrevs) > len(day_names):
            day_abbrevs = day_abbrevs[: len(day_names)]

        week = WeekDefinition(day_names=day_names, day_abbreviations=day_abbrevs)

        return CalendarConfig(
            id=self._config.id,
            name=self.name_edit.text() or "Unnamed Calendar",
            months=months,
            week=week,
            year_variants=self._config.year_variants,  # Preserve existing
            epoch_name=self.epoch_edit.text() or "Year",
            created_at=self._config.created_at,
        )

    def _update_preview(self) -> None:
        """Updates the date preview based on current config."""
        try:
            config = self._build_config_from_ui()
            errors = config.validate()

            if errors:
                self.error_label.setText("⚠ " + "; ".join(errors))
                self.error_label.show()
                self.button_box.button(QDialogButtonBox.Save).setEnabled(False)
            else:
                self.error_label.hide()
                self.button_box.button(QDialogButtonBox.Save).setEnabled(True)

                # Preview conversion
                converter = CalendarConverter(config)
                float_val = float(self.preview_float.value())
                formatted = converter.format_date(float_val)
                self.preview_label.setText(formatted)

        except Exception as e:
            self.error_label.setText(f"⚠ Error: {e}")
            self.error_label.show()
            self.button_box.button(QDialogButtonBox.Save).setEnabled(False)

    def _on_save(self) -> None:
        """Handles the save button click."""
        config = self._build_config_from_ui()
        errors = config.validate()

        if errors:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Cannot save:\n" + "\n".join(errors),
            )
            return

        self._config = config
        self.config_saved.emit(config)
        self.accept()

    def get_config(self) -> CalendarConfig:
        """
        Returns the current calendar configuration.

        Returns:
            CalendarConfig: The configuration from the dialog.
        """
        return self._config
