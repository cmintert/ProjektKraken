"""
Test script to populate database with Middle Earth sample data.

This creates entities and events with wiki-style links to demonstrate
the ID-based linking system.
"""

import sys
from src.services.db_service import DatabaseService
from src.core.entities import Entity
from src.core.events import Event
from src.commands.wiki_commands import ProcessWikiLinksCommand


def populate_middle_earth_data(db_path=":memory:"):
    """
    Populates database with Middle Earth sample data.
    
    Args:
        db_path: Path to database file (default: in-memory).
    
    Returns:
        DatabaseService instance with populated data.
    """
    db = DatabaseService(db_path)
    db.connect()
    
    print("Creating Middle Earth entities...")
    
    # Create key characters
    gandalf = Entity(
        name="Gandalf",
        type="character",
        description="A wizard of the Istari order, known as Gandalf the Grey and later Gandalf the White.",
        attributes={"race": "Maia", "aliases": ["Mithrandir", "Gandalf the Grey", "Gandalf the White"]}
    )
    db.insert_entity(gandalf)
    print(f"Created: {gandalf.name} (ID: {gandalf.id})")
    
    frodo = Entity(
        name="Frodo Baggins",
        type="character",
        description="A hobbit of the Shire, ring-bearer and hero of the War of the Ring.",
        attributes={"race": "Hobbit"}
    )
    db.insert_entity(frodo)
    print(f"Created: {frodo.name} (ID: {frodo.id})")
    
    aragorn = Entity(
        name="Aragorn",
        type="character",
        description="Ranger of the North, heir to the throne of Gondor, later King Elessar.",
        attributes={"race": "Man", "aliases": ["Strider", "Elessar"]}
    )
    db.insert_entity(aragorn)
    print(f"Created: {aragorn.name} (ID: {aragorn.id})")
    
    sauron = Entity(
        name="Sauron",
        type="character",
        description="The Dark Lord, primary antagonist and creator of the One Ring.",
        attributes={"race": "Maia", "aliases": ["Dark Lord", "Lord of the Rings"]}
    )
    db.insert_entity(sauron)
    print(f"Created: {sauron.name} (ID: {sauron.id})")
    
    # Create locations
    shire = Entity(
        name="The Shire",
        type="location",
        description="Homeland of the hobbits, a peaceful region in Eriador.",
        attributes={"type": "region"}
    )
    db.insert_entity(shire)
    print(f"Created: {shire.name} (ID: {shire.id})")
    
    rivendell = Entity(
        name="Rivendell",
        type="location",
        description="Elven outpost in Middle-earth, founded by Elrond in the Second Age.",
        attributes={"type": "settlement", "aliases": ["Imladris"]}
    )
    db.insert_entity(rivendell)
    print(f"Created: {rivendell.name} (ID: {rivendell.id})")
    
    mordor = Entity(
        name="Mordor",
        type="location",
        description="Dark realm of Sauron in the southeast of Middle-earth.",
        attributes={"type": "realm"}
    )
    db.insert_entity(mordor)
    print(f"Created: {mordor.name} (ID: {mordor.id})")
    
    # Create the One Ring artifact
    one_ring = Entity(
        name="The One Ring",
        type="artifact",
        description="Master ring forged by Sauron to control all other Rings of Power. "
                    f"Currently carried by [[id:{frodo.id}|Frodo Baggins]].",
        attributes={"power": "dominion over all rings"}
    )
    db.insert_entity(one_ring)
    print(f"Created: {one_ring.name} (ID: {one_ring.id})")
    
    # Process wiki links for the One Ring
    cmd = ProcessWikiLinksCommand(one_ring.id, one_ring.description)
    result = cmd.execute(db)
    print(f"Processed wiki links for One Ring: {result.message}")
    
    print("\nCreating Middle Earth events...")
    
    # Create key events
    council_elrond = Event(
        name="Council of Elrond",
        lore_date=3018.0,  # Third Age year 3018
        description=f"A great council held at [[id:{rivendell.id}|Rivendell]] where the fate "
                    f"of [[id:{one_ring.id}|the One Ring]] was decided. "
                    f"[[id:{frodo.id}|Frodo]] volunteered to carry the Ring to [[id:{mordor.id}|Mordor]].",
        type="council",
        attributes={"age": "Third Age"}
    )
    db.insert_event(council_elrond)
    print(f"Created: {council_elrond.name} (Date: TA {int(council_elrond.lore_date)})")
    
    # Process wiki links for the event
    cmd = ProcessWikiLinksCommand(council_elrond.id, council_elrond.description, field="description")
    result = cmd.execute(db)
    print(f"Processed wiki links for Council: {result.message}")
    
    fellowship_formed = Event(
        name="Formation of the Fellowship",
        lore_date=3018.5,
        description=f"[[id:{gandalf.id}|Gandalf]], [[id:{aragorn.id}|Aragorn]], "
                    f"[[id:{frodo.id}|Frodo]] and six others formed the Fellowship of the Ring "
                    f"to destroy [[id:{one_ring.id}|the One Ring]] in [[id:{mordor.id}|Mordor]].",
        type="alliance",
        attributes={"age": "Third Age"}
    )
    db.insert_event(fellowship_formed)
    print(f"Created: {fellowship_formed.name} (Date: TA {int(fellowship_formed.lore_date)})")
    
    # Process wiki links
    cmd = ProcessWikiLinksCommand(fellowship_formed.id, fellowship_formed.description)
    result = cmd.execute(db)
    print(f"Processed wiki links for Fellowship: {result.message}")
    
    fall_of_sauron = Event(
        name="Fall of Sauron",
        lore_date=3019.0,
        description=f"[[id:{sauron.id}|Sauron]] was defeated when [[id:{one_ring.id}|the One Ring]] "
                    f"was destroyed in the fires of Mount Doom.",
        type="battle",
        attributes={"age": "Third Age", "significance": "End of the Third Age"}
    )
    db.insert_event(fall_of_sauron)
    print(f"Created: {fall_of_sauron.name} (Date: TA {int(fall_of_sauron.lore_date)})")
    
    # Process wiki links
    cmd = ProcessWikiLinksCommand(fall_of_sauron.id, fall_of_sauron.description)
    result = cmd.execute(db)
    print(f"Processed wiki links for Fall of Sauron: {result.message}")
    
    # Add a description with ID-based link to Gandalf
    gandalf.description = (
        f"[[id:{gandalf.id}|Gandalf]] arrived in Middle-earth around TA 1000. "
        f"He played a crucial role in defeating [[id:{sauron.id}|Sauron]] during the War of the Ring. "
        f"He was close friends with [[id:{aragorn.id}|Aragorn]] and mentored [[id:{frodo.id}|Frodo]]."
    )
    db.insert_entity(gandalf)
    
    # Process wiki links for Gandalf
    cmd = ProcessWikiLinksCommand(gandalf.id, gandalf.description)
    result = cmd.execute(db)
    print(f"\nProcessed wiki links for Gandalf: {result.message}")
    
    print("\n" + "="*60)
    print("Middle Earth database populated successfully!")
    print("="*60)
    print(f"\nStatistics:")
    print(f"  Entities: {len(db.get_all_entities())}")
    print(f"  Events: {len(db.get_all_events())}")
    
    # Count relations
    all_relations = []
    for entity in db.get_all_entities():
        all_relations.extend(db.get_relations(entity.id))
    for event in db.get_all_events():
        all_relations.extend(db.get_relations(event.id))
    print(f"  Relations: {len(all_relations)}")
    
    return db


if __name__ == "__main__":
    # Create test database
    db_path = "test_middle_earth.kraken"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    db = populate_middle_earth_data(db_path)
    print(f"\nDatabase saved to: {db_path}")
    print("\nYou can now open this database in ProjektKraken to explore the wiki links!")
