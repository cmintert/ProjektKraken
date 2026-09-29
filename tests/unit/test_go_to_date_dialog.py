"""Exact, calendar-aware timeline navigation input."""

import pytest
from PySide6.QtWidgets import QDialog

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)
from src.gui.dialogs.go_to_date_dialog import GoToDateDialog


@pytest.fixture
def custom_calendar() -> CalendarConverter:
    return CalendarConverter(
        CalendarConfig(
            id="short-year",
            name="Short Year",
            months=[
                MonthDefinition(name="First", abbreviation="Fir", days=7),
                MonthDefinition(name="Second", abbreviation="Sec", days=11),
            ],
            week=WeekDefinition(
                day_names=["One", "Two", "Three"],
                day_abbreviations=["1", "2", "3"],
            ),
            year_variants=[],
            epoch_name="Age",
        )
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 January 1", 1.0),
        ("2 January 1 09:30", 1.0 + 9 / 24 + 30 / 1440),
        ("1 January 0", -366.0),
    ],
)
def test_exact_standard_date_starts_at_selected_instant(
    qtbot, text: str, expected: float
) -> None:
    converter = CalendarConverter(CalendarConfig.create_default())
    dialog = GoToDateDialog(converter, 0.0)
    qtbot.addWidget(dialog)

    dialog.date_input.txt_date.setText(text)
    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.target_time == pytest.approx(expected)


def test_custom_calendar_and_pre_epoch_date(qtbot, custom_calendar) -> None:
    dialog = GoToDateDialog(custom_calendar, 0.0)
    qtbot.addWidget(dialog)
    dialog.date_input.txt_date.setText("3 Second -1 12:15")

    dialog.accept()

    expected = custom_calendar.start_of_day(-1, 2, 3) + 12 / 24 + 15 / 1440
    assert dialog.target_time == pytest.approx(expected)


def test_custom_calendar_rejects_day_outside_month(qtbot, custom_calendar) -> None:
    dialog = GoToDateDialog(custom_calendar, 0.0)
    qtbot.addWidget(dialog)
    dialog.date_input.txt_date.setText("8 First 1")

    dialog.accept()

    assert dialog.target_time is None
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_cancel_preserves_playhead(qtbot) -> None:
    converter = CalendarConverter(CalendarConfig.create_default())
    dialog = GoToDateDialog(converter, 42.25)
    qtbot.addWidget(dialog)
    dialog.date_input.txt_date.setText("2 January 1")

    dialog.reject()

    assert dialog.target_time is None
    assert dialog.result() == QDialog.DialogCode.Rejected


@pytest.mark.parametrize(
    "text",
    [
        "1",
        "January 1",
        "32 January 1",
        "around 2 January 1",
        "calculated 2 January 1",
        "2 January 1?",
        "between 2 January 1 and 4 January 1",
    ],
)
def test_incomplete_invalid_or_uncertain_date_does_not_navigate(
    qtbot, text: str
) -> None:
    converter = CalendarConverter(CalendarConfig.create_default())
    dialog = GoToDateDialog(converter, 0.0)
    qtbot.addWidget(dialog)
    dialog.date_input.txt_date.setText(text)

    dialog.accept()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.target_time is None
    assert dialog.feedback.text()
