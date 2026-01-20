"""Unit tests for ImportService."""

from unittest.mock import MagicMock

from src.core.entities import Entity
from src.core.events import Event
from src.services.import_service import ImportService


def test_parse_only_valid_batch():
    """Test parsing a valid batch JSON."""
    service = ImportService(MagicMock())
    json_data = {
        "entities": [{"name": "E1"}],
        "events": [{"name": "Ev1"}],
        "relations": [],
    }
    result = service.parse_only(json_data)
    assert len(result["entities"]) == 1
    assert len(result["events"]) == 1
    assert result["entities"][0]["name"] == "E1"


def test_parse_only_single_entity():
    """Test heuristic detection of single entity."""
    service = ImportService(MagicMock())
    json_data = {"name": "Single Entity", "type": "character"}
    result = service.parse_only(json_data)
    assert len(result["entities"]) == 1
    assert len(result["events"]) == 0
    assert result["entities"][0]["name"] == "Single Entity"


def test_parse_only_single_event():
    """Test heuristic detection of single event."""
    service = ImportService(MagicMock())
    json_data = {"name": "Single Event", "lore_date": 100.0}
    result = service.parse_only(json_data)
    assert len(result["entities"]) == 0
    assert len(result["events"]) == 1
    assert result["events"][0]["name"] == "Single Event"


def test_import_batch_creates_items():
    """Test that import_batch calls DB insert methods."""
    mock_db = MagicMock()
    service = ImportService(mock_db)

    # Setup name resolution mocks
    mock_db.get_entities.return_value = []
    mock_db.get_events.return_value = []

    data = {
        "entities": [{"name": "Ent1", "type": "place"}],
        "events": [{"name": "Evt1", "lore_date": 50.0}],
    }

    result = service.import_batch(data)

    assert result.success is True
    assert len(result.created_entities) == 1
    assert len(result.created_events) == 1

    # Verify DB calls
    mock_db.insert_entity.assert_called_once()
    mock_db.insert_event.assert_called_once()

    # Check arguments
    entity_arg = mock_db.insert_entity.call_args[0][0]
    assert isinstance(entity_arg, Entity)
    assert entity_arg.name == "Ent1"

    event_arg = mock_db.insert_event.call_args[0][0]
    assert isinstance(event_arg, Event)
    assert event_arg.name == "Evt1"


def test_import_relation_name_resolution():
    """Test that relation targets are resolved by name."""
    mock_db = MagicMock()
    service = ImportService(mock_db)

    # Create mock items existing in DB
    existing_entity = Entity(name="TargetEntity", type="place")
    # Mock get_entities to return our target
    mock_db.get_entities.return_value = [existing_entity]
    mock_db.get_events.return_value = []
    mock_db._relation_repo.find_existing.return_value = None  # No existing relation

    # Import data with relation pointing to TargetEntity
    data = {
        "entities": [
            {
                "name": "SourceEntity",
                "relations": [{"target_name": "TargetEntity", "rel_type": "linked"}],
            }
        ]
    }

    result = service.import_batch(data)

    assert result.success is True
    # Should resolve TargetEntity to its ID and insert relation
    mock_db.insert_relation.assert_called_once()
    args = mock_db.insert_relation.call_args[0]
    # source_id (newly created), target_id (existing), type, attrs
    assert args[1] == existing_entity.id
    assert args[2] == "linked"


def test_import_relation_missing_target():
    """Test that relation is skipped if target not found."""
    mock_db = MagicMock()
    service = ImportService(mock_db)

    mock_db.get_entities.return_value = []
    mock_db.get_events.return_value = []

    data = {
        "entities": [
            {
                "name": "Source",
                "relations": [{"target_name": "Ghost", "rel_type": "haunts"}],
            }
        ]
    }

    result = service.import_batch(data)

    assert result.success is True  # Overall success
    assert len(result.created_relations) == 0
    assert len(result.warnings) > 0
    assert "Ghost" in result.warnings[0]

    mock_db.insert_relation.assert_not_called()


def test_import_prevents_duplicate_relations():
    """Test that importing the same relations multiple times doesn't create duplicates."""
    from src.services.db_service import DatabaseService

    db = DatabaseService(":memory:")
    db.connect()
    import_service = ImportService(db)

    data = {
        "entities": [
            {"name": "Entity A", "type": "character"},
            {"name": "Entity B", "type": "location"},
        ],
        "relations": [
            {
                "source_name": "Entity A",
                "target_name": "Entity B",
                "rel_type": "located_in",
            }
        ],
    }

    # First import
    result1 = import_service.import_batch(data)
    assert result1.success
    assert len(result1.created_relations) == 1

    # Second import - should not create duplicate
    result2 = import_service.import_batch(data)
    assert result2.success
    assert len(result2.created_relations) == 0  # No new relations created

    # Verify only one relation exists in DB
    all_relations = db._relation_repo.get_all()
    assert len(all_relations) == 1

    db.close()
