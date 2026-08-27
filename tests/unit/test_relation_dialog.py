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


def test_unknown_manual_entry_is_not_returned_as_an_id(relation_dialog):
    """Arbitrary text must never cross the dialog boundary as a target ID."""
    relation_dialog.target_edit.setText("Manual-ID-123")

    target_id, _, _, _ = relation_dialog.get_data()

    assert target_id == ""


def test_duplicate_names_require_disambiguated_selection(qtbot):
    dialog = RelationEditDialog(
        suggestion_items=[
            ("id-1", "Springfield", "Place"),
            ("id-2", "Springfield", "Event"),
        ]
    )
    qtbot.addWidget(dialog)

    dialog.target_edit.setText("Springfield")
    assert dialog.get_data()[0] == ""

    display = next(
        text
        for text, item_id in dialog._display_to_id.items()
        if item_id == "id-2"
    )
    dialog.target_edit.setText(display)
    assert dialog.get_data()[0] == "id-2"


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


def test_entity_to_entity_has_no_state_changes_ui(qtbot):
    dialog = RelationEditDialog(
        suggestion_items=[("entity-1", "Target", "entity")]
    )
    qtbot.addWidget(dialog)
    dialog.target_edit.setText("Target")

    assert not hasattr(dialog, "state_changes_group")
    assert "payload" not in dialog.get_data()[3]


def test_event_to_entity_round_trips_payload_v2(qtbot):
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        source_event_name="Battle",
        suggestion_items=[
            ("entity-1", "Grey Ford", "entity"),
            ("event-2", "Later Event", "event"),
        ],
        attributes={
            "payload": {
                "attributes": {"status": "Ruined", "ruler": None},
                "unset_attributes": ["garrison"],
                "description": "",
            }
        },
    )
    qtbot.addWidget(dialog)

    assert not dialog.state_changes_group.isHidden()
    _, _, _, attributes = dialog.get_data()
    assert attributes["payload"] == {
        "attributes": {"status": "Ruined", "ruler": None},
        "unset_attributes": ["garrison"],
        "description": "",
    }


def test_event_to_event_hides_and_omits_mutation_controls(qtbot):
    dialog = RelationEditDialog(
        target_id="event-2",
        source_event_date=100.0,
        source_event_name="Source Event",
        suggestion_items=[
            ("entity-1", "Grey Ford", "entity"),
            ("event-2", "Target Event", "event"),
        ],
        attributes={"payload": {"attributes": {"status": "Ruined"}}},
    )
    qtbot.addWidget(dialog)

    assert dialog.state_changes_group.isHidden()
    assert "payload" not in dialog.get_data()[3]

    dialog.target_edit.setText("Grey Ford")
    assert not dialog.state_changes_group.isHidden()
    assert dialog.get_data()[3]["payload"]["attributes"]["status"] == "Ruined"


def test_empty_event_to_entity_mutation_omits_payload(qtbot):
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        suggestion_items=[("entity-1", "Target", "entity")],
    )
    qtbot.addWidget(dialog)

    assert "payload" not in dialog.get_data()[3]


def test_change_description_checkbox_reveals_editor(qtbot):
    """Description edits are only shown and enabled when explicitly requested."""
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        suggestion_items=[("entity-1", "Target", "entity")],
    )
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.state_description_edit.isHidden()
    assert not dialog.state_description_edit.isEnabled()

    dialog.change_description_check.setChecked(True)

    assert not dialog.state_description_edit.isHidden()
    assert dialog.state_description_edit.isEnabled()


def test_tall_event_relation_keeps_approval_buttons_below_scrollable_form(qtbot):
    """Long event relation forms scroll without hiding the approval actions."""
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        suggestion_items=[("entity-1", "Target", "entity")],
        attributes={
            "payload": {
                "attributes": {f"key_{index}": "value" for index in range(12)},
                "unset_attributes": [f"remove_{index}" for index in range(8)],
                "description": "A long state-change description.",
            }
        },
    )
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(
        lambda: dialog.form_scroll_area.verticalScrollBar().maximum() > 0
    )

    assert dialog.form_scroll_area.geometry().bottom() < dialog.button_box.geometry().top()


def test_relation_dialog_themes_scroll_area_and_fits_attribute_rows(qtbot):
    """The scroll viewport is themed and state rows do not consume spare space."""
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        suggestion_items=[("entity-1", "Target", "entity")],
        attributes={"payload": {"attributes": {"status": "dead"}}},
    )
    qtbot.addWidget(dialog)
    dialog.show()

    table = dialog.state_attribute_editor.table
    expected_table_height = (
        table.horizontalHeader().height()
        + table.rowHeight(0)
        + (2 * table.frameWidth())
    )

    assert "QDialog" in dialog.styleSheet()
    assert "QScrollArea" in dialog.form_scroll_area.styleSheet()
    assert table.height() == expected_table_height
    assert dialog.unset_attributes_list.height() == (
        2 * dialog.unset_attributes_list.frameWidth()
    )

    dialog.unset_attributes_list.addItem("garrison")
    assert dialog.unset_attributes_list.height() > (
        2 * dialog.unset_attributes_list.frameWidth()
    )


@pytest.mark.parametrize("invalid_key", ["status", "_tags", "name"])
def test_invalid_state_changes_keep_dialog_open(
    qtbot, monkeypatch, invalid_key
):
    dialog = RelationEditDialog(
        target_id="entity-1",
        source_event_date=100.0,
        suggestion_items=[("entity-1", "Target", "entity")],
    )
    qtbot.addWidget(dialog)
    dialog.state_attribute_editor.load_attributes({invalid_key: "Changed"})
    if invalid_key == "status":
        dialog.unset_attributes_list.addItem("status")

    warnings = []
    monkeypatch.setattr(
        "src.gui.dialogs.relation_dialog.QMessageBox.warning",
        lambda *args: warnings.append(args),
    )
    dialog.accept()

    assert dialog.result() == 0
    assert warnings
