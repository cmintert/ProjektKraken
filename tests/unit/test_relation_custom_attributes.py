import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.relation_dialog import RelationEditDialog


@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


def test_ordinary_relation_attributes_are_not_promoted_to_payload(app):
    """Legacy custom relation keys are not interpreted as state mutations."""
    initial_attributes = {
        "weight": 2.5,  # Standard
        "magic_power": "high",  # Custom
        "hidden_value": 42,  # Custom
    }

    dialog = RelationEditDialog(attributes=initial_attributes)

    _, _, _, result_attributes = dialog.get_data()

    assert result_attributes.get("weight") == 2.5
    assert "payload" not in result_attributes
    assert "magic_power" not in result_attributes
    assert "hidden_value" not in result_attributes
