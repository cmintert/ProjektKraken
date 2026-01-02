import pytest

from src.gui.dialogs.relation_dialog import RelationEditDialog


@pytest.fixture
def relation_dialog(qtbot):
    """Fixture for RelationEditDialog."""
    items = [
        ("id-1", "Gandalf", "Character"),
        ("id-2", "Frodo", "Character"),
        ("id-3", "The Shire", "Location"),
    ]
    dialog = RelationEditDialog(suggestion_items=items)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_init(relation_dialog):
    """Test dialog initialization."""
    assert relation_dialog.windowTitle() == "Edit Relation"
    assert (
        relation_dialog.target_edit.placeholderText() == "Search for entity or event..."
    )
    assert relation_dialog.type_edit.currentText() == "involved"
    assert not relation_dialog.bi_check.isChecked()


def test_autocompletion_resolution(relation_dialog, qtbot):
    """Test that selecting a name resolves to the ID."""
    # Simulate typing "Gandalf"
    relation_dialog.target_edit.setText("Gandalf")

    # Get data
    target_id, rel_type, is_bi, _ = relation_dialog.get_data()

    assert target_id == "id-1"
    assert rel_type == "involved"
    assert not is_bi


def test_manual_entry_fallback(relation_dialog):
    """Test that manual entry (not in list) is preserved."""
    relation_dialog.target_edit.setText("Manual-ID-123")

    target_id, _, _, _ = relation_dialog.get_data()

    assert target_id == "Manual-ID-123"


def test_prefill_editing(qtbot):
    """Test pre-filling data for editing."""
    items = [("id-1", "Gandalf", "Character")]
    dialog = RelationEditDialog(
        target_id="id-1",
        rel_type="located_at",
        is_bidirectional=True,
        suggestion_items=items,
    )
    qtbot.addWidget(dialog)

    # Assert display name is shown, not ID
    assert dialog.target_edit.text() == "Gandalf"
    assert dialog.type_edit.currentText() == "located_at"
    assert dialog.bi_check.isChecked()

    # Verify data retrieval converts back to ID
    target_id, _, _, _ = dialog.get_data()  # Expect 4 values now
    assert target_id == "id-1"


def test_attribute_collection(qtbot):
    """Test that attributes are correctly collected from the dialog."""
    dialog = RelationEditDialog()
    qtbot.addWidget(dialog)

    # Checkboxes removed - attributes always enabled implicitly

    # Simulate user input
    dialog.weight_spin.setValue(0.8)
    dialog.confidence_spin.setValue(0.5)
    # Source removed
    dialog.notes_edit.setPlainText(
        "Test Note"
    )  # Assuming using QTextEdit or QPlainTextEdit

    # Get data
    _, _, _, attributes = dialog.get_data()

    assert attributes["weight"] == 0.8
    assert attributes["confidence"] == 0.5
    # Source removed
    assert attributes["notes"] == "Test Note"


def test_default_attributes_omitted(qtbot):
    """Test that default values (1.0) are omitted from attributes dict."""
    dialog = RelationEditDialog()
    qtbot.addWidget(dialog)

    # Leave defaults (Weight 1.0, Confidence 1.0)

    _, _, _, attributes = dialog.get_data()

    assert "weight" not in attributes
    assert "confidence" not in attributes
