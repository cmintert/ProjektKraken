"""
Integration tests for longform functionality.

Tests the complete flow of creating, manipulating, and exporting
longform documents with a real in-memory SQLite database.
"""

import pytest
import time
from src.services.db_service import DatabaseService
from src.core.events import Event
from src.core.entities import Entity
from src.services import longform_builder
from src.commands.longform_commands import (
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
    DemoteLongformEntryCommand,
    RemoveLongformEntryCommand,
)


@pytest.fixture
def db_service():
    """Create an in-memory database service for testing."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture
def sample_events(db_service):
    """Create sample events in the database."""
    events = [
        Event(
            id="event-1",
            name="Chapter 1: The Beginning",
            description="Once upon a time...",
            lore_date=100.0,
        ),
        Event(
            id="event-2",
            name="Chapter 2: The Middle",
            description="And then...",
            lore_date=200.0,
        ),
        Event(
            id="event-3",
            name="Chapter 3: The End",
            description="Finally...",
            lore_date=300.0,
        ),
    ]

    for event in events:
        db_service.insert_event(event)

    return events


@pytest.fixture
def sample_entities(db_service):
    """Create sample entities in the database."""
    entities = [
        Entity(
            id="entity-1",
            name="Hero",
            type="character",
            description="The brave hero of our story.",
        ),
        Entity(
            id="entity-2",
            name="Villain",
            type="character",
            description="The evil antagonist.",
        ),
    ]

    for entity in entities:
        db_service.insert_entity(entity)

    return entities


def test_add_items_to_longform(db_service, sample_events):
    """Test adding events to longform document."""
    conn = db_service._connection

    # Add first event
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    # Add second event
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=200.0, parent_id=None, depth=0
    )

    # Read items
    items = longform_builder.read_all_longform_items(conn)

    assert len(items) == 2
    assert items[0]["id"] == "event-1"
    assert items[1]["id"] == "event-2"


def test_build_sequence_ordering(db_service, sample_events):
    """Test building ordered sequence."""
    conn = db_service._connection

    # Add items out of order
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-3", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=200.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=300.0, parent_id=None, depth=0
    )

    # Build sequence
    sequence = longform_builder.build_longform_sequence(conn)

    assert len(sequence) == 3
    assert sequence[0]["id"] == "event-3"
    assert sequence[1]["id"] == "event-1"
    assert sequence[2]["id"] == "event-2"


def test_parent_child_nesting(db_service, sample_events):
    """Test parent-child relationships."""
    conn = db_service._connection

    # Add parent
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    # Add children
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=110.0, parent_id="event-1", depth=1
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-3", position=120.0, parent_id="event-1", depth=1
    )

    # Build sequence
    sequence = longform_builder.build_longform_sequence(conn)

    assert len(sequence) == 3
    assert sequence[0]["id"] == "event-1"
    assert sequence[0]["heading_level"] == 1
    assert sequence[1]["id"] == "event-2"
    assert sequence[1]["heading_level"] == 2
    assert sequence[2]["id"] == "event-3"
    assert sequence[2]["heading_level"] == 2


def test_place_between_siblings(db_service, sample_events):
    """Test placing item between siblings."""
    conn = db_service._connection

    # Add two items
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-3", position=300.0, parent_id=None, depth=0
    )

    # Place event-2 between them
    longform_builder.place_between_siblings_and_set_parent(
        conn, "events", "event-2", ("events", "event-1"), ("events", "event-3"), None
    )

    # Check sequence
    sequence = longform_builder.build_longform_sequence(conn)

    assert len(sequence) == 3
    assert sequence[0]["id"] == "event-1"
    assert sequence[1]["id"] == "event-2"
    assert sequence[2]["id"] == "event-3"

    # Check position is between
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]
    assert 100.0 < event_2["meta"]["position"] < 300.0


def test_reindex_positions(db_service, sample_events):
    """Test reindexing document positions."""
    conn = db_service._connection

    # Add items with weird positions
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=17.3, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=99.999, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-3", position=1523.7, parent_id=None, depth=0
    )

    # Reindex
    longform_builder.reindex_document_positions(conn)

    # Check new positions
    items = longform_builder.read_all_longform_items(conn)
    items.sort(key=lambda x: x["meta"]["position"])

    assert items[0]["meta"]["position"] == 100.0
    assert items[1]["meta"]["position"] == 200.0
    assert items[2]["meta"]["position"] == 300.0


def test_promote_item(db_service, sample_events):
    """Test promoting an item."""
    conn = db_service._connection

    # Create parent and child
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=110.0, parent_id="event-1", depth=1
    )

    # Promote child
    longform_builder.promote_item(conn, "events", "event-2")

    # Check result
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]

    assert event_2["meta"]["depth"] == 0
    assert event_2["meta"]["parent_id"] is None


def test_demote_item(db_service, sample_events):
    """Test demoting an item."""
    conn = db_service._connection

    # Create two siblings
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=200.0, parent_id=None, depth=0
    )

    # Demote second item (make it child of first)
    longform_builder.demote_item(conn, "events", "event-2")

    # Check result
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]

    assert event_2["meta"]["depth"] == 1
    assert event_2["meta"]["parent_id"] == "event-1"


def test_demote_item_no_previous_sibling(db_service, sample_events):
    """Test that demote does nothing when there's no previous sibling."""
    conn = db_service._connection

    # Add single item
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    # Try to demote (should fail gracefully)
    longform_builder.demote_item(conn, "events", "event-1")

    # Check it's unchanged
    items = longform_builder.read_all_longform_items(conn)
    event_1 = items[0]

    assert event_1["meta"]["depth"] == 0
    assert event_1["meta"]["parent_id"] is None


def test_remove_from_longform(db_service, sample_events):
    """Test removing item from longform."""
    conn = db_service._connection

    # Add item
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    # Verify it exists
    items = longform_builder.read_all_longform_items(conn)
    assert len(items) == 1

    # Remove it
    longform_builder.remove_from_longform(conn, "events", "event-1")

    # Verify it's gone from longform
    items = longform_builder.read_all_longform_items(conn)
    assert len(items) == 0

    # But event still exists in database
    event = db_service.get_event("event-1")
    assert event is not None


def test_export_to_markdown(db_service, sample_events, sample_entities):
    """Test exporting longform to Markdown."""
    conn = db_service._connection

    # Add items
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=110.0, parent_id="event-1", depth=1
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "entities", "entity-1", position=200.0, parent_id=None, depth=0
    )

    # Export
    markdown = longform_builder.export_longform_to_markdown(conn)

    # Verify structure
    assert "# Longform Document: default" in markdown
    assert "# Chapter 1: The Beginning" in markdown
    assert "## Chapter 2: The Middle" in markdown
    assert "# Hero" in markdown
    assert "Once upon a time..." in markdown
    assert "The brave hero" in markdown
    assert "PK-LONGFORM id=event-1" in markdown
    assert "table=events" in markdown


def test_mixed_events_and_entities(db_service, sample_events, sample_entities):
    """Test that events and entities can coexist in longform."""
    conn = db_service._connection

    # Interleave events and entities
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "entities", "entity-1", position=200.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=300.0, parent_id=None, depth=0
    )

    sequence = longform_builder.build_longform_sequence(conn)

    # Note: ensure_all_items_indexed() adds all DB items to longform
    # automatically, so we expect all 3 events + 2 entities = 5 total
    assert len(sequence) == 5

    # Verify that the items we explicitly added are in the right order
    assert sequence[0]["id"] == "event-1"
    assert sequence[0]["table"] == "events"
    assert sequence[1]["id"] == "entity-1"
    assert sequence[1]["table"] == "entities"
    assert sequence[2]["id"] == "event-2"
    assert sequence[2]["table"] == "events"


# Command tests


def test_move_command_execute_undo(db_service, sample_events):
    """Test MoveLongformEntryCommand execute and undo."""
    conn = db_service._connection

    # Setup initial state
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    old_meta = {"position": 100.0, "parent_id": None, "depth": 0}
    new_meta = {"position": 200.0, "parent_id": None, "depth": 0}

    # Create and execute command
    cmd = MoveLongformEntryCommand("events", "event-1", old_meta, new_meta)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify new position
    items = longform_builder.read_all_longform_items(conn)
    assert items[0]["meta"]["position"] == 200.0

    # Undo
    cmd.undo(db_service)

    # Verify old position restored
    items = longform_builder.read_all_longform_items(conn)
    assert items[0]["meta"]["position"] == 100.0


def test_promote_command_execute_undo(db_service, sample_events):
    """Test PromoteLongformEntryCommand execute and undo."""
    conn = db_service._connection

    # Setup parent-child
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=110.0, parent_id="event-1", depth=1
    )

    old_meta = {"position": 110.0, "parent_id": "event-1", "depth": 1}

    # Execute promote
    cmd = PromoteLongformEntryCommand("events", "event-2", old_meta)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify promoted
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]
    assert event_2["meta"]["depth"] == 0

    # Undo
    cmd.undo(db_service)

    # Verify restored
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]
    assert event_2["meta"]["depth"] == 1
    assert event_2["meta"]["parent_id"] == "event-1"


def test_demote_command_execute_undo(db_service, sample_events):
    """Test DemoteLongformEntryCommand execute and undo."""
    conn = db_service._connection

    # Setup two siblings
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=200.0, parent_id=None, depth=0
    )

    old_meta = {"position": 200.0, "parent_id": None, "depth": 0}

    # Execute demote
    cmd = DemoteLongformEntryCommand("events", "event-2", old_meta)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify demoted
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]
    assert event_2["meta"]["depth"] == 1
    assert event_2["meta"]["parent_id"] == "event-1"

    # Undo
    cmd.undo(db_service)

    # Verify restored
    items = longform_builder.read_all_longform_items(conn)
    event_2 = [i for i in items if i["id"] == "event-2"][0]
    assert event_2["meta"]["depth"] == 0
    assert event_2["meta"]["parent_id"] is None


def test_remove_command_execute_undo(db_service, sample_events):
    """Test RemoveLongformEntryCommand execute and undo."""
    conn = db_service._connection

    # Setup item
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )

    old_meta = {"position": 100.0, "parent_id": None, "depth": 0}

    # Execute remove
    cmd = RemoveLongformEntryCommand("events", "event-1", old_meta)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify removed
    items = longform_builder.read_all_longform_items(conn)
    assert len(items) == 0

    # Undo
    cmd.undo(db_service)

    # Verify restored
    items = longform_builder.read_all_longform_items(conn)
    assert len(items) == 1
    assert items[0]["id"] == "event-1"


def test_title_override(db_service, sample_events):
    """Test title override functionality."""
    conn = db_service._connection

    # Add with title override
    longform_builder.insert_or_update_longform_meta(
        conn,
        "events",
        "event-1",
        position=100.0,
        parent_id=None,
        depth=0,
        title_override="Custom Chapter Title",
    )

    # Export and verify
    markdown = longform_builder.export_longform_to_markdown(conn)

    assert "# Custom Chapter Title" in markdown
    assert "Chapter 1: The Beginning" not in markdown.split("<!--")[1]


def test_deeply_nested_structure(db_service, sample_events):
    """Test deeply nested document structure."""
    conn = db_service._connection

    # Create nested structure
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-1", position=100.0, parent_id=None, depth=0
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-2", position=110.0, parent_id="event-1", depth=1
    )
    longform_builder.insert_or_update_longform_meta(
        conn, "events", "event-3", position=111.0, parent_id="event-2", depth=2
    )

    sequence = longform_builder.build_longform_sequence(conn)

    assert len(sequence) == 3
    assert sequence[0]["heading_level"] == 1
    assert sequence[1]["heading_level"] == 2
    assert sequence[2]["heading_level"] == 3

    # Export and check heading levels
    markdown = longform_builder.export_longform_to_markdown(conn)

    assert "# Chapter 1" in markdown
    assert "## Chapter 2" in markdown
    assert "### Chapter 3" in markdown
