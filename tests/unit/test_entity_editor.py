import pytest

from src.core.entities import Entity
from src.gui.widgets.entity_editor import EntityEditorWidget


@pytest.fixture
def editor(qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


def test_editor_init(editor):
    assert editor.name_edit is not None
    assert editor._content_widget.isHidden()  # Hidden until entity loaded
    assert not editor._empty_state.isHidden()  # Empty state shown on init


def test_timeline_card_width_tracks_description_editor(editor):
    assert editor.timeline_display.maximumWidth() == editor.desc_edit.maximumWidth()

    editor.desc_edit._toggle_toc()

    assert editor.timeline_display.maximumWidth() == editor.desc_edit.maximumWidth()


def test_timeline_card_forwards_event_navigation(editor, qtbot):
    with qtbot.waitSignal(editor.navigate_to_relation) as blocker:
        editor.timeline_display.event_clicked.emit("event-1")

    assert blocker.args == ["event-1"]


def test_context_attachment_opens_gallery_tab(editor):
    editor._show_context_attachment("attachment-id")

    assert editor.inspector.get_main_tabs().currentWidget() is editor.tab_gallery


def test_load_entity(editor):
    ent = Entity(id="1", name="Test Entity", type="Character", description="Desc")
    editor.load_entity(ent)

    assert editor.name_edit.text() == "Test Entity"
    assert editor.type_edit.currentText() == "Character"
    assert editor.desc_edit.toPlainText() == "Desc"
    assert editor.isEnabled() is True


def test_temporal_state_hides_internal_attributes(editor):
    entity = Entity(id="1", name="Test Entity", type="Character")
    editor.load_entity(entity)

    editor.display_temporal_state(
        entity.id,
        {
            "entity_id": entity.id,
            "description": "Temporal description",
            "attributes": {"visible": "shown", "_internal": "preserved"},
        },
    )

    assert editor.desc_edit.get_wiki_text() == "Temporal description"
    assert editor.attribute_editor.table.rowCount() == 1
    assert editor.attribute_editor.table.item(0, 0).text() == "visible"
    assert editor.attribute_editor.get_attributes()["_internal"] == "preserved"


def test_temporal_state_is_read_only_and_does_not_mark_dirty(editor):
    entity = Entity(
        id="1",
        name="Grey Ford",
        type="Location",
        description="Base description",
        attributes={"controller": "Crown"},
    )
    editor.load_entity(entity)

    editor.display_temporal_state(
        entity.id,
        {
            "entity_id": entity.id,
            "description": "Ruined remains",
            "attributes": {"controller": "Northern League", "status": "Ruined"},
        },
        playhead_time=736.0,
    )

    assert editor.desc_edit.get_wiki_text() == "Ruined remains"
    assert editor.attribute_editor.get_attributes()["status"] == "Ruined"
    assert editor.name_edit.text() == "Grey Ford"
    assert editor.type_edit.currentText() == "Location"
    assert editor._is_dirty is False
    assert editor.name_edit.isReadOnly()
    assert not editor.attribute_editor.isEnabled()

    editor.display_temporal_state(
        entity.id,
        {
            "entity_id": entity.id,
            "description": "Earlier state",
            "attributes": {"controller": "Crown"},
        },
        playhead_time=731.0,
    )
    assert editor.desc_edit.get_wiki_text() == "Earlier state"
    assert editor.attribute_editor.get_attributes() == {"controller": "Crown"}
    assert editor._is_dirty is False

    editor.load_entity(entity)
    assert editor.desc_edit.get_wiki_text() == "Base description"
    assert editor.attribute_editor.get_attributes() == {"controller": "Crown"}
    assert editor._is_dirty is False


def test_save_clicked(editor, qtbot):
    ent = Entity(id="1", name="Old Name", type="Generic")
    editor.load_entity(ent)

    # Change Name
    editor.name_edit.setText("New Name")

    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    assert isinstance(saved_data, dict)
    assert saved_data["name"] == "New Name"
    assert saved_data["id"] == "1"


def test_add_relation_flow(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(ent)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("target_id", "caused", True, {})

    # Patch the class where it is defined
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.add_relation_requested) as blocker:
        editor.btn_add_rel.click()

    # Signal: source, target, type, attributes, bidirectional
    assert blocker.args == ["1", "target_id", "caused", {}, True]


def test_remove_relation(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(
        ent, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock msgbox
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)

    with qtbot.waitSignal(editor.remove_relation_requested) as blocker:
        editor.btn_remove_rel.click()

    assert blocker.args[0] == "r1"


def test_automatic_mentions_are_read_only(editor):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(
        ent, relations=[{"id": "r1", "target_id": "t1", "rel_type": "mentions"}]
    )
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)
    removed = []
    updated = []
    editor.remove_relation_requested.connect(removed.append)
    editor.update_relation_requested.connect(lambda *args: updated.append(args))

    editor._update_relation_button_states()
    editor._on_remove_relation_item(item)
    editor._on_edit_relation(item)

    assert not editor.btn_remove_rel.isEnabled()
    assert not editor.btn_edit_rel.isEnabled()
    assert removed == []
    assert updated == []


def test_edit_relation_flow(editor, qtbot, monkeypatch):
    ent = Entity(id="1", name="Source", type="Generic")
    editor.load_entity(
        ent, relations=[{"id": "r1", "target_id": "t1", "rel_type": "caused"}]
    )

    # Select item
    item = editor.rel_list.item(0)
    editor.rel_list.setCurrentItem(item)

    # Mock RelationEditDialog
    from unittest.mock import MagicMock

    import src.gui.dialogs.relation_dialog

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = True
    mock_dialog.get_data.return_value = ("new_target", "related_to", True, {})

    # Mock bi_check for setVisible call
    mock_dialog.bi_check = MagicMock()

    # Patch the class
    monkeypatch.setattr(
        src.gui.dialogs.relation_dialog,
        "RelationEditDialog",
        lambda *args, **kwargs: mock_dialog,
    )

    with qtbot.waitSignal(editor.update_relation_requested) as blocker:
        editor.btn_edit_rel.click()

    # args: rel_id, target_id, new_type, attributes
    assert blocker.args == ["r1", "new_target", "related_to", {}]


def test_wikilink_insertion_has_no_immediate_relation_writer(editor):
    """Wikilinks are reconciled only when the editor is saved."""
    assert not hasattr(editor, "_on_wikilink_added")
    assert not hasattr(editor.desc_edit, "link_added")


def test_sheet_builder_data_loss(editor, qtbot):
    """Test that manipulating the sheet builder updates the attribute editor and
    saves correctly.
    """
    ent = Entity(id="1", name="Test", type="Character", attributes={"Strength": 10})
    editor.load_entity(ent)

    # Verify both editors start with the value
    assert editor.attribute_editor.get_attributes()["Strength"] == 10
    assert "Strength" in editor.sheet_builder.get_attributes()
    assert editor.sheet_builder.get_attributes()["Strength"] == 10

    # Modify "Strength" in Sheet Builder
    strength_pair = editor.sheet_builder._pairs["Strength"]
    strength_pair.value_edit.setText("15")

    # Check if Attribute Editor is updated
    assert editor.attribute_editor.get_attributes()["Strength"] == 15

    # Simulate Save
    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    assert saved_data["attributes"]["Strength"] == 15
