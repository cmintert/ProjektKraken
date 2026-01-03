"""
Demo Database Creator for ProjektKraken

Creates a sample database showcasing the temporal state system with:
- Sample characters and locations
- Events with temporal relations
- Dynamic event-relative timing examples
"""

from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService


def create_demo_database(db_path: str = "demo.kraken") -> None:
    """Create a demo database with sample temporal data."""
    # Initialize database
    db = DatabaseService(db_path)
    db.connect()

    print(f"Creating demo database: {db_path}")

    # === ENTITIES ===
    print("\n📦 Creating Entities...")

    # Characters
    frodo = Entity(
        id="frodo",
        name="Frodo Baggins",
        type="character",
        attributes={"species": "Hobbit", "home": "Shire", "status": "At Peace"},
    )
    db.insert_entity(frodo)

    gandalf = Entity(
        id="gandalf",
        name="Gandalf the Grey",
        type="character",
        attributes={"species": "Maia", "title": "Wizard"},
    )
    db.insert_entity(gandalf)

    aragorn = Entity(
        id="aragorn",
        name="Aragorn",
        type="character",
        attributes={"species": "Human", "status": "Ranger"},
    )
    db.insert_entity(aragorn)

    # Locations
    shire = Entity(
        id="shire",
        name="The Shire",
        type="location",
        attributes={"region": "Eriador", "description": "Peaceful homeland of Hobbits"},
    )
    db.insert_entity(shire)

    rivendell = Entity(
        id="rivendell",
        name="Rivendell",
        type="location",
        attributes={"region": "Eriador", "description": "Last Homely House"},
    )
    db.insert_entity(rivendell)

    gondor = Entity(
        id="gondor",
        name="Gondor",
        type="location",
        attributes={"region": "South", "description": "Kingdom of Men"},
    )
    db.insert_entity(gondor)

    print("  ✓ Created 6 entities (3 characters, 3 locations)")

    # === EVENTS ===
    print("\n📅 Creating Events...")

    evt_departs_shire = Event(
        id="evt1",
        name="Frodo Departs the Shire",
        lore_date=3018.0,
        type="journey",
        description="Frodo begins his quest to destroy the One Ring",
    )
    db.insert_event(evt_departs_shire)

    evt_council = Event(
        id="evt2",
        name="Council of Elrond",
        lore_date=3018.8,
        type="meeting",
        description="The Fellowship is formed",
    )
    db.insert_event(evt_council)

    evt_coronation = Event(
        id="evt3",
        name="Aragorn's Coronation",
        lore_date=3019.5,
        type="milestone",
        description="Aragorn crowned King of Gondor",
    )
    db.insert_event(evt_coronation)

    evt_return = Event(
        id="evt4",
        name="Return to the Shire",
        lore_date=3021.0,
        type="journey",
        description="Frodo returns home",
    )
    db.insert_event(evt_return)

    print("  ✓ Created 4 events")

    # === TEMPORAL RELATIONS ===
    print("\n🔗 Creating Temporal Relations...")

    # Event 1: Frodo Departs the Shire
    db.insert_relation(
        source_id="evt1",
        target_id="frodo",
        rel_type="involved",
        attributes={
            "valid_from": 3018.0,
            "valid_from_event": True,  # Dynamic: starts when event happens
            "payload": {"status": "Ring Bearer", "carrying": "One Ring"},
        },
    )

    db.insert_relation(
        source_id="evt1",
        target_id="shire",
        rel_type="located_at",
        attributes={
            "valid_from": 3018.0,
            "valid_to": 3018.0,
            "valid_from_event": True,
            "valid_to_event": True,  # Only valid AT the event
        },
    )

    # Event 2: Council of Elrond
    db.insert_relation(
        source_id="evt2",
        target_id="frodo",
        rel_type="involved",
        attributes={
            "valid_from": 3018.8,
            "valid_to": 3018.8,
            "valid_from_event": True,
            "valid_to_event": True,
        },
    )

    db.insert_relation(
        source_id="evt2",
        target_id="gandalf",
        rel_type="involved",
        attributes={
            "valid_from": 3018.8,
            "valid_to": 3018.8,
            "valid_from_event": True,
            "valid_to_event": True,
        },
    )

    db.insert_relation(
        source_id="evt2",
        target_id="aragorn",
        rel_type="involved",
        attributes={
            "valid_from": 3018.8,
            "valid_to": 3018.8,
            "valid_from_event": True,
            "valid_to_event": True,
        },
    )

    db.insert_relation(
        source_id="evt2",
        target_id="rivendell",
        rel_type="located_at",
        attributes={
            "valid_from": 3018.8,
            "valid_to": 3018.8,
            "valid_from_event": True,
            "valid_to_event": True,
        },
    )

    # Event 3: Aragorn's Coronation
    db.insert_relation(
        source_id="evt3",
        target_id="aragorn",
        rel_type="involved",
        attributes={
            "valid_from": 3019.5,
            "valid_from_event": True,  # Becomes king at coronation
            "payload": {"title": "King of Gondor", "status": "Crowned"},
        },
    )

    db.insert_relation(
        source_id="evt3",
        target_id="gondor",
        rel_type="located_at",
        attributes={
            "valid_from": 3019.5,
            "valid_to": 3019.5,
            "valid_from_event": True,
            "valid_to_event": True,
        },
    )

    # Event 4: Return to Shire
    db.insert_relation(
        source_id="evt4",
        target_id="frodo",
        rel_type="involved",
        attributes={
            "valid_from": 3021.0,
            "valid_from_event": True,
            "payload": {"status": "Returning Home", "carrying": None},
        },
    )

    db.insert_relation(
        source_id="evt4",
        target_id="shire",
        rel_type="located_at",
        attributes={
            "valid_from": 3021.0,
            "valid_from_event": True,
        },
    )

    print("  ✓ Created 10 temporal relations with dynamic event binding")

    # Close database
    db.close()

    print("\n✅ Demo database created successfully!")
    print(f"\n📍 Location: {db_path}")
    print("\n🎯 What to try:")
    print("  1. Open Frodo in Entity Inspector")
    print("  2. Move timeline playhead to different years (3018, 3019, 3021)")
    print("  3. Watch 'status' and 'carrying' attributes change")
    print("  4. Open Aragorn and see title change at coronation (3019.5)")
    print("  5. Try editing event dates - watch entity states update automatically!")


if __name__ == "__main__":
    create_demo_database()
