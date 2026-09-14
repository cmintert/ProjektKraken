"""Rendered interaction contracts for the unified transfer dialog."""

import json

from PySide6.QtCore import Qt

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
