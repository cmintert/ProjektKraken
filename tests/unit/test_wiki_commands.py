"""
Unit tests for ProcessWikiLinksCommand.
"""

import pytest
from unittest.mock import MagicMock, ANY
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.entities import Entity


@pytest.fixture
def mock_db():
    """Mock database service."""
    return MagicMock()


@pytest.fixture
def source_id():
    return "source-123"


def test_process_no_links(mock_db, source_id):
    """Test text with no links does nothing."""
    cmd = ProcessWikiLinksCommand(source_id, "Just plain text.")
    result = cmd.execute(mock_db)

    assert result.success is True
    assert "No links found" in result.message
    mock_db.insert_relation.assert_not_called()


def test_process_creates_relation(mock_db, source_id):
    """Test valid link creates a relation."""
    # Setup
    target_entity = Entity(id="target-999", name="Gandalf", type="Character")
    mock_db.get_all_entities.return_value = [target_entity]
    mock_db.get_relations.return_value = []  # No existing relations

    # DB Service mock should also return ID string for insert_relation
    mock_db.insert_relation.return_value = "new-rel-id"

    text = "Speak to [[Gandalf]] and enter."
    cmd = ProcessWikiLinksCommand(source_id, text)

    # Execute
    result = cmd.execute(mock_db)

    # Verify
    assert result.success is True
    assert "Created 1 new relations" in result.message

    mock_db.insert_relation.assert_called_once()
    # Check arguments passed to insert_relation
    kwargs = mock_db.insert_relation.call_args.kwargs
    assert kwargs["source_id"] == source_id
    assert kwargs["target_id"] == target_entity.id
    assert kwargs["rel_type"] == "mentioned"


def test_process_case_insensitive_match(mock_db, source_id):
    """Test link matching is case-insensitive."""
    target_entity = Entity(id="target-999", name="The Shire", type="Location")
    mock_db.get_all_entities.return_value = [target_entity]
    mock_db.get_relations.return_value = []
    mock_db.insert_relation.return_value = "new-rel-id"

    text = "Visit [[the shire]] today."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(mock_db)

    assert result.success is True
    mock_db.insert_relation.assert_called_once()
    assert mock_db.insert_relation.call_args.kwargs["target_id"] == target_entity.id


def test_process_skips_existing_relation(mock_db, source_id):
    """Test distinct relation is not duplicated."""
    target_entity = Entity(id="target-999", name="Gandalf", type="Character")
    # Existing relation represented as a DICT
    existing_rel = {
        "id": "rel-1",
        "source_id": source_id,
        "target_id": "target-999",
        "rel_type": "mentioned",
    }

    mock_db.get_all_entities.return_value = [target_entity]
    mock_db.get_relations.return_value = [existing_rel]

    text = "Speak to [[Gandalf]]."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(mock_db)

    assert result.success is True
    mock_db.insert_relation.assert_not_called()


def test_process_undo(mock_db, source_id):
    """Test undo deletes created relations."""
    target_entity = Entity(id="target-999", name="Gandalf", type="Character")
    mock_db.get_all_entities.return_value = [target_entity]
    mock_db.get_relations.return_value = []
    mock_db.insert_relation.return_value = "rel-123"

    cmd = ProcessWikiLinksCommand(source_id, "[[Gandalf]]")
    cmd.execute(mock_db)

    # Check internal state
    assert len(cmd._created_relations) == 1
    assert cmd._created_relations[0] == "rel-123"

    # Undo
    cmd.undo(mock_db)

    mock_db.delete_relation.assert_called_once_with("rel-123")
    assert len(cmd._created_relations) == 0
