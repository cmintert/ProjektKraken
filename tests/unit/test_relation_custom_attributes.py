import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.relation_dialog import RelationEditDialog


@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


def test_custom_attributes_preservation(app):
    """
    Test that custom (non-standard) attributes are preserved
    when passed to the dialog and retrieved via get_data().
    """
    initial_attributes = {
        "weight": 2.5,  # Standard
        "magic_power": "high",  # Custom
        "hidden_value": 42,  # Custom
    }

    dialog = RelationEditDialog(attributes=initial_attributes)

    # Simulate user NOT changing anything in the UI
    # (The UI only shows standard fields currently)

    _, _, _, result_attributes = dialog.get_data()

    # Check standard attribute
    assert result_attributes.get("weight") == 2.5

    # Check custom attributes - CURRENTLY FAILS
    assert "magic_power" in result_attributes
    assert result_attributes["magic_power"] == "high"
    assert result_attributes["hidden_value"] == 42
