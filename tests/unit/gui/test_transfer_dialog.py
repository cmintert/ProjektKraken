"""Rendered interaction contracts for the unified transfer dialog."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase

from src.core.theme_manager import ThemeManager
from src.gui.dialogs.transfer_dialog import TransferDialog
from src.gui.utils.style_helper import StyleHelper


def test_text_surfaces_use_the_active_theme(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    expected = StyleHelper.get_input_field_style()

    assert dialog.pasted.styleSheet() == expected
    assert dialog.details.styleSheet() == expected
    assert dialog.document_preview.styleSheet() == expected
    assert dialog.diagnostics.styleSheet() == expected
    assert dialog.results.styleSheet() == expected


def test_complete_lore_json_example_is_inserted_as_editable_text(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)

    assert dialog.pasted.toPlainText() == ""
    assert dialog.pasted.placeholderText() == "Paste a lore JSON object here."
    qtbot.mouseClick(dialog.pasted_example, Qt.MouseButton.LeftButton)

    example = json.loads(dialog.pasted.toPlainText())
    assert set(example) == {"exchange_version", "entities", "events", "relations"}
    assert set(example["entities"][0]) == {
        "id",
        "type",
        "name",
        "description",
        "tags",
        "attributes",
        "created_at",
        "modified_at",
    }
    assert set(example["events"][0]) == {
        "id",
        "type",
        "name",
        "lore_date",
        "lore_duration",
        "description",
        "tags",
        "attributes",
        "created_at",
        "modified_at",
    }
    assert example["events"][0]["lore_date"] == "23 AUG 1895"
    assert set(example["relations"][0]) == {
        "id",
        "source_id",
        "target_id",
        "rel_type",
        "attributes",
        "created_at",
    }
    assert not dialog.pasted_example.isEnabled()


def test_format_guidance_and_publishing_options(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    dialog.export_format.setCurrentIndex(dialog.export_format.findData("pdf"))
    assert "PDF import is not supported" in dialog.format_help.text()
    assert dialog.title_edit.isEnabled()
    assert not dialog.scope.isEnabled()
    dialog.export_format.setCurrentIndex(dialog.export_format.findData("json"))
    assert not dialog.title_edit.isEnabled()
    assert dialog.scope.isEnabled()


def test_review_edits_require_recheck_and_results_persist(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    data = {
        "entities": [{"name": "A", "type": "person"}],
        "events": [],
        "relations": [],
    }
    preview = {
        "errors": [],
        "delta": [{"table": "entities", "before": None, "after": {"name": "A"}}],
    }
    dialog.show_import_review(data, preview)
    assert dialog.next.isEnabled()
    dialog.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
    assert not dialog.next.isEnabled()
    dialog.show_result("Completed with warnings", False, False)
    assert dialog.isVisible()
    assert dialog.results.toPlainText() == "Completed with warnings"


def test_relation_review_details_use_resolved_id_not_shared_missing_name(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    rows = [{"id": identity, "rel_type": "allied"} for identity in ("first", "second")]
    preview = {
        "errors": [],
        "actions": [
            {
                "type": "relation",
                "token": f"relations:{index}",
                "id": row["id"],
                "action": "create",
                "reason": "new",
            }
            for index, row in enumerate(rows)
        ],
        "delta": [
            {
                "table": "relations",
                "before": None,
                "after": {"id": row["id"], "attributes": {"evidence": row["id"]}},
            }
            for row in rows
        ],
    }
    dialog.show_import_review({"relations": rows}, preview)
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    assert '"first"' in dialog.diagnostics.toPlainText()
    assert '"second"' not in dialog.diagnostics.toPlainText()


def test_all_sources_visible_and_cancel_is_cooperative(qtbot):
    dialog = TransferDialog()
    qtbot.addWidget(dialog)
    dialog.set_sources([{"path": "one.json"}, {"path": "two.md"}])
    assert dialog.source_list.count() == 2
    dialog.show()
    dialog.set_busy(True)
    with qtbot.waitSignal(dialog.cancel_requested):
        dialog.reject()
    assert dialog.isVisible()


@pytest.mark.parametrize(
    "theme",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_review_calendar_dependency_focus_disabled_and_narrow(
    qtbot,
    qapp,
    theme,
    theme_presentation,
):
    manager = ThemeManager()
    if theme not in manager.themes:
        pytest.skip("Palette key is not shipped")
    previous = manager.current_theme_name
    manager.set_theme(theme, qapp, persist=False)
    try:
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
            qapp.setFont(QFont("Segoe UI", 10))
        dialog = TransferDialog()
        qtbot.addWidget(dialog)
        dialog.resize(780, 560)
        dialog.show()
        preview = {
            "errors": ["Calendar and Event dependency need review."],
            "delta": [],
            "options": {"proposed_ids": {"events:0": "stable-id"}, "import_time": 1},
            "calendar_decisions": [
                {
                    "source_id": "foreign-calendar",
                    "candidates": ["active-calendar"],
                    "message": "Compatible mapping required.",
                }
            ],
            "dependency_decisions": [
                {
                    "source_id": "missing-event",
                    "message": "Missing source for the Event end.",
                }
            ],
        }
        dialog.show_import_review(
            {"events": [{"name": "Imported", "lore_date": None}]}, preview
        )
        assert not dialog.next.isEnabled()
        calendar = dialog._calendar_controls["foreign-calendar"]
        calendar.setCurrentIndex(calendar.findData("active-calendar"))
        dependency = dialog._dependency_controls["missing-event"]
        dependency.setCurrentIndex(dependency.findData("unresolved"))
        dependency.setFocus()
        qtbot.waitUntil(lambda: dependency.hasFocus())
        with qtbot.waitSignal(dialog.review_requested) as emitted:
            dialog._recheck()
        options = emitted.args[0]["import_options"]
        assert options["calendar_mappings"] == {"foreign-calendar": "active-calendar"}
        assert options["unresolved_events"] == ["missing-event"]
        assert options["proposed_ids"]["events:0"] == "stable-id"
        assert options["import_time"] == 1
        output = Path("tmp/krt121-renders")
        output.mkdir(parents=True, exist_ok=True)
        assert dialog.grab().save(str(output / f"{theme}-narrow.png"))
        dialog.resize(1200, 800)
        qapp.processEvents()
        assert dialog.grab().save(str(output / f"{theme}-wide.png"))
    finally:
        manager.set_theme(previous, qapp, persist=False)
