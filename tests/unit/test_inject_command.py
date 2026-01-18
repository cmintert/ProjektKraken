"""
Unit tests for InjectTemplateCommand.
"""

from unittest.mock import MagicMock

import pytest

from src.commands.inject_commands import InjectTemplateCommand
from src.core.entities import Entity
from src.core.fast_inject import FastInjectManager, FastInjectTemplate


@pytest.fixture
def manager(tmp_path):
    return FastInjectManager(tmp_path)


@pytest.fixture
def mock_db_service():
    """Mock database service."""
    service = MagicMock()
    service.update_entity = MagicMock()
    service.update_event = MagicMock()
    return service


def test_command_execute_entity(manager, mock_db_service):
    """Test executing command on an entity."""
    entity = Entity(name="Hero", type="Character", attributes={"HP": 100})
    template = FastInjectTemplate(
        name="Buff", attributes={"HP": 200, "MP": 50}, tags=["Buffed"]
    )

    cmd = InjectTemplateCommand(entity, template, manager, overwrite=True)
    result = cmd.execute(mock_db_service)

    assert result.success is True
    assert entity.attributes["HP"] == 200
    assert entity.attributes["MP"] == 50
    assert "Buffed" in entity.tags

    # Verify DB call
    mock_db_service.update_entity.assert_called_once_with(entity)


def test_command_undo_entity(manager, mock_db_service):
    """Test undoing command on an entity."""
    entity = Entity(name="Hero", type="Character", attributes={"HP": 100})
    entity.tags = ["Base"]

    template = FastInjectTemplate(
        name="Buff", attributes={"HP": 200, "MP": 50}, tags=["Buffed"]
    )

    cmd = InjectTemplateCommand(entity, template, manager, overwrite=True)
    cmd.execute(mock_db_service)

    # Verify State before undo
    assert entity.attributes["HP"] == 200

    # Undo
    cmd.undo(mock_db_service)

    # State should be restored
    assert entity.attributes["HP"] == 100  # Restored
    assert "MP" not in entity.attributes  # Removed (was added)
    assert "Buffed" not in entity.tags  # Removed
    assert "Base" in entity.tags  # Preserved

    # Verify DB update called again for undo
    assert mock_db_service.update_entity.call_count == 2


def test_command_no_overwrite(manager, mock_db_service):
    """Test command honoring overwrite flag."""
    entity = Entity(name="Hero", type="Character", attributes={"Class": "Warrior"})
    template = FastInjectTemplate(name="Mage", attributes={"Class": "Mage"})

    cmd = InjectTemplateCommand(entity, template, manager, overwrite=False)
    cmd.execute(mock_db_service)

    assert entity.attributes["Class"] == "Warrior"  # Unchanged


def test_command_undo_type(manager, mock_db_service):
    """Test undoing type changes."""
    entity = Entity(name="Hero", type="OriginalType")
    template = FastInjectTemplate(name="TypeSwap", type_value="NewType")

    cmd = InjectTemplateCommand(entity, template, manager)
    cmd.execute(mock_db_service)

    assert entity.type == "NewType"

    cmd.undo(mock_db_service)

    assert entity.type == "OriginalType"
    assert mock_db_service.update_entity.call_count == 2
