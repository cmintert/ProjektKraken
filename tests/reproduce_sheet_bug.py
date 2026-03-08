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


def test_sheet_builder_data_loss(editor, qtbot):
    # 1. Load entity with an attribute
    ent = Entity(id="1", name="Test", type="Character", attributes={"Strength": 10})
    editor.load_entity(ent)

    # 2. Verify both editors have the value
    assert editor.attribute_editor.get_attributes()["Strength"] == 10
    assert editor.sheet_builder.get_attributes()["Strength"] == 10

    # 3. Modify "Strength" in Sheet Builder
    # We'll simulate editing the value edit within the AttributePairWidget
    strength_pair = editor.sheet_builder._pairs["Strength"]
    strength_pair.value_edit.setText("15")

    # 4. Check if Attribute Editor is updated (it probably isn't)
    # This is where the bug manifests
    attr_editor_val = editor.attribute_editor.get_attributes()["Strength"]
    print(f"\nValue in Attribute Editor: {attr_editor_val}")
    print(
        f"Value in Sheet Builder: {editor.sheet_builder.get_attributes()['Strength']}"
    )

    # 5. Simulate Save
    with qtbot.waitSignal(editor.save_requested) as blocker:
        editor.btn_save.click()

    saved_data = blocker.args[0]
    # This assertion is expected to FAIL currently
    assert saved_data["attributes"]["Strength"] == 15, (
        "Sheet builder changes were lost on save!"
    )
