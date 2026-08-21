"""Tests for the date-free AI-generated description policy."""

from src.core.description_date_policy import find_description_dates
from src.gui.dialogs.generation_review_dialog import GenerationReviewDialog


def test_detects_explicit_calendar_and_lore_dates() -> None:
    text = (
        "It opened on 2025-03-14, in Year 42, on 3 Groen 9, "
        "and at lore date: 120.5."
    )

    violations = find_description_dates(
        text, month_names=("Groen",), era_names=("AF",)
    )

    assert {item.text for item in violations} == {
        "2025-03-14",
        "Year 42",
        "3 Groen 9",
        "lore date: 120.5",
    }


def test_allows_relative_time_durations_and_unrelated_numbers() -> None:
    text = (
        "Years later, after the siege, she served for 12 years. "
        "The wall is 200 metres long and the protocol is version 2.1."
    )

    assert find_description_dates(text, month_names=("Groen",)) == ()


def test_known_lore_date_is_detected_without_a_label() -> None:
    violations = find_description_dates(
        "The change occurred at 120.5.", known_date_values=(120.5,)
    )

    assert [item.text for item in violations] == ["120.5"]


def test_detects_custom_calendar_era() -> None:
    violations = find_description_dates("Founded in 84 AF.", era_names=("AF",))

    assert [item.text for item in violations] == ["84 AF"]


def test_review_dialog_blocks_apply_until_dates_are_removed(qtbot) -> None:
    dialog = GenerationReviewDialog(
        "The gate opened in Year 42.", month_names=("Groen",)
    )
    qtbot.addWidget(dialog)

    assert dialog.date_warning.isVisibleTo(dialog)
    assert not dialog.replace_btn.isEnabled()
    assert not dialog.append_btn.isEnabled()

    dialog.text_edit.setPlainText("The gate opened after the siege.")

    assert dialog.replace_btn.isEnabled()
    assert dialog.append_btn.isEnabled()
