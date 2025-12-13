"""
Calendar Configuration Dialog Unit Tests.

Tests for the CalendarConfigDialog widget.
"""

import pytest

from PySide6.QtWidgets import QDialogButtonBox

from src.gui.dialogs.calendar_config_dialog import CalendarConfigDialog
from src.core.calendar import (
    MonthDefinition,
    WeekDefinition,
    CalendarConfig,
)


@pytest.fixture
def sample_config() -> CalendarConfig:
    """Create a sample calendar config for testing."""
    return CalendarConfig(
        id="dialog-test-001",
        name="Dialog Test Calendar",
        months=[
            MonthDefinition(name="January", abbreviation="Jan", days=31),
            MonthDefinition(name="February", abbreviation="Feb", days=28),
        ],
        week=WeekDefinition(
            day_names=["Monday", "Tuesday"],
            day_abbreviations=["Mo", "Tu"],
        ),
        year_variants=[],
        epoch_name="DT",
    )


class TestCalendarConfigDialogInit:
    """Tests for dialog initialization."""

    def test_creates_with_default_config(self, qapp):
        """Test that dialog creates with default config when none provided."""
        dialog = CalendarConfigDialog()
        config = dialog.get_config()

        assert config is not None
        assert len(config.months) > 0

    def test_creates_with_provided_config(self, qapp, sample_config):
        """Test that dialog loads the provided config."""
        dialog = CalendarConfigDialog(config=sample_config)
        config = dialog.get_config()

        assert config.id == sample_config.id
        assert config.name == sample_config.name

    def test_name_field_populated(self, qapp, sample_config):
        """Test that the name field shows the config name."""
        dialog = CalendarConfigDialog(config=sample_config)

        assert dialog.name_edit.text() == sample_config.name

    def test_epoch_field_populated(self, qapp, sample_config):
        """Test that the epoch field shows the epoch name."""
        dialog = CalendarConfigDialog(config=sample_config)

        assert dialog.epoch_edit.text() == sample_config.epoch_name


class TestCalendarConfigDialogMonthTable:
    """Tests for the month editor table."""

    def test_month_table_row_count(self, qapp, sample_config):
        """Test that month table has correct row count."""
        dialog = CalendarConfigDialog(config=sample_config)

        assert dialog.month_table.rowCount() == 2

    def test_add_month_button(self, qapp, sample_config):
        """Test that add month button adds a row."""
        dialog = CalendarConfigDialog(config=sample_config)
        initial_count = dialog.month_table.rowCount()

        dialog._on_add_month()

        assert dialog.month_table.rowCount() == initial_count + 1

    def test_remove_month_button(self, qapp, sample_config):
        """Test that remove month button removes selected row."""
        dialog = CalendarConfigDialog(config=sample_config)
        dialog.month_table.setCurrentCell(0, 0)
        initial_count = dialog.month_table.rowCount()

        dialog._on_remove_month()

        assert dialog.month_table.rowCount() == initial_count - 1


class TestCalendarConfigDialogValidation:
    """Tests for dialog validation."""

    def test_empty_months_shows_error(self, qapp, sample_config):
        """Test that validation shows error when no months."""
        dialog = CalendarConfigDialog(config=sample_config)

        # Remove all months
        dialog.month_table.setRowCount(0)
        dialog._update_preview()

        # Build config and validate directly
        config = dialog._build_config_from_ui()
        errors = config.validate()

        # Should have validation errors for empty months
        assert len(errors) > 0
        assert any("month" in e.lower() for e in errors)
        # Save button should be disabled
        assert not dialog.button_box.button(QDialogButtonBox.Save).isEnabled()

    def test_valid_config_enables_save(self, qapp, sample_config):
        """Test that valid config enables the save button."""
        dialog = CalendarConfigDialog(config=sample_config)
        dialog._update_preview()

        assert dialog.button_box.button(QDialogButtonBox.Save).isEnabled()


class TestCalendarConfigDialogPreview:
    """Tests for the date preview feature."""

    def test_preview_updates_on_float_change(self, qapp, sample_config):
        """Test that preview updates when float value changes."""
        dialog = CalendarConfigDialog(config=sample_config)
        initial_text = dialog.preview_label.text()

        dialog.preview_float.setValue(100)

        # Should have different text now (different date)
        assert dialog.preview_label.text() != initial_text

    def test_preview_shows_formatted_date(self, qapp, sample_config):
        """Test that preview shows a formatted date string."""
        dialog = CalendarConfigDialog(config=sample_config)
        dialog.preview_float.setValue(0)
        dialog._update_preview()

        text = dialog.preview_label.text()
        assert "Year" in text
        assert "1" in text


class TestCalendarConfigDialogOutput:
    """Tests for getting the config from the dialog."""

    def test_get_config_returns_updated_values(self, qapp, sample_config):
        """Test that get_config reflects UI changes."""
        dialog = CalendarConfigDialog(config=sample_config)

        dialog.name_edit.setText("New Name")
        dialog.epoch_edit.setText("NE")

        # Need to rebuild config
        config = dialog._build_config_from_ui()

        assert config.name == "New Name"
        assert config.epoch_name == "NE"

    def test_config_saved_signal_emitted(self, qapp, sample_config):
        """Test that config_saved signal is emitted on save."""
        dialog = CalendarConfigDialog(config=sample_config)
        signal_received = []

        dialog.config_saved.connect(lambda c: signal_received.append(c))
        dialog._on_save()

        assert len(signal_received) == 1
        assert signal_received[0].id == sample_config.id
