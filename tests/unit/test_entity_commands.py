"""
Unit tests for entity commands.
"""

from unittest.mock import MagicMock

import pytest

from src.commands.entity_commands import (
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)
from src.core.entities import Entity


@pytest.fixture
def mock_db():
    """Mock database service."""
    return MagicMock()


@pytest.fixture
def sample_entity():
    """Sample entity for testing."""
    return Entity(name="Test Entity", type="Character")


def test_create_entity_success(mock_db, sample_entity):
    """Test successful entity creation."""
    # Pass dict
    cmd = CreateEntityCommand(sample_entity.to_dict())

    result = cmd.execute(mock_db)

    assert result.success is True
    # Verify entity was inserted. We can't check identity (new object), but equality
    mock_db.insert_entity.assert_called_once()
    inserted = mock_db.insert_entity.call_args[0][0]
    assert inserted.name == sample_entity.name
    assert cmd._is_executed is True


def test_create_entity_undo(mock_db, sample_entity):
    """Test undoing entity creation."""
    cmd = CreateEntityCommand(sample_entity.to_dict())
    cmd.execute(mock_db)

    # Get created ID
    created = cmd._entity

    cmd.undo(mock_db)

    mock_db.delete_entity.assert_called_once_with(created.id)
    assert cmd._is_executed is False


def test_update_entity_success(mock_db):
    """Test successful entity update."""
    old_entity = Entity(id="test-id", name="Old Name", type="Character")
    update_data = {"name": "New Name", "type": "NPC"}

    mock_db.get_entity.return_value = old_entity
    cmd = UpdateEntityCommand("test-id", update_data)

    result = cmd.execute(mock_db)

    assert result.success is True
    # Verify DB was called with a new entity containing updated values
    args, _ = mock_db.insert_entity.call_args
    updated_entity = args[0]
    assert updated_entity.id == "test-id"
    assert updated_entity.name == "New Name"
    assert updated_entity.type == "NPC"
    assert cmd._is_executed is True
    assert cmd._previous_entity == old_entity


def test_update_entity_undo(mock_db):
    """Test undoing entity update."""
    old_entity = Entity(id="test-id", name="Old Name", type="Character")
    update_data = {"name": "New Name", "type": "NPC"}

    mock_db.get_entity.return_value = old_entity
    cmd = UpdateEntityCommand("test-id", update_data)
    cmd.execute(mock_db)
    mock_db.insert_entity.reset_mock()

    cmd.undo(mock_db)

    mock_db.insert_entity.assert_called_once_with(old_entity)
    assert cmd._is_executed is False


def test_delete_entity_success(mock_db, sample_entity):
    """Test successful entity deletion."""
    mock_db.get_entity.return_value = sample_entity
    cmd = DeleteEntityCommand(sample_entity.id)

    result = cmd.execute(mock_db)

    assert result.success is True
    mock_db.delete_entity.assert_called_once_with(sample_entity.id)
    assert cmd._is_executed is True
    assert cmd._backup_entity == sample_entity


def test_delete_entity_undo(mock_db, sample_entity):
    """Test undoing entity deletion."""
    mock_db.get_entity.return_value = sample_entity
    cmd = DeleteEntityCommand(sample_entity.id)
    cmd.execute(mock_db)
    mock_db.insert_entity.reset_mock()

    cmd.undo(mock_db)

    mock_db.insert_entity.assert_called_once_with(sample_entity)
    assert cmd._is_executed is False
