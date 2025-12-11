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
        attributes={
            "race": "Maia",
            "aliases": ["Mithrandir", "Gandalf the Grey", "Gandalf the White"],
        },
    )
    db.insert_entity(gandalf)
    print(f"Created: {gandalf.name} (ID: {gandalf.id})")

    frodo = Entity(
        name="Frodo Baggins",
        type="character",
        description="A hobbit of the Shire, ring-bearer and hero of the War of the Ring.",
        attributes={"race": "Hobbit"},
    )
    db.insert_entity(frodo)
    print(f"Created: {frodo.name} (ID: {frodo.id})")

    aragorn = Entity(
        name="Aragorn",
        type="character",
        description="Ranger of the North, heir to the throne of Gondor, later King Elessar.",
        attributes={"race": "Man", "aliases": ["Strider", "Elessar"]},
    )
    db.insert_entity(aragorn)
    print(f"Created: {aragorn.name} (ID: {aragorn.id})")

    sauron = Entity(
        name="Sauron",
        type="character",
        description="The Dark Lord, primary antagonist and creator of the One Ring.",
        attributes={"race": "Maia", "aliases": ["Dark Lord", "Lord of the Rings"]},
    )
    db.insert_entity(sauron)
    print(f"Created: {sauron.name} (ID: {sauron.id})")

    # Create locations
    shire = Entity(
        name="The Shire",
        type="location",
        description="Homeland of the hobbits, a peaceful region in Eriador.",
        attributes={"type": "region"},
    )
    db.insert_entity(shire)
    print(f"Created: {shire.name} (ID: {shire.id})")

    rivendell = Entity(
        name="Rivendell",
        type="location",
        description="Elven outpost in Middle-earth, founded by Elrond in the Second Age.",
        attributes={"type": "settlement", "aliases": ["Imladris"]},
    )
    db.insert_entity(rivendell)
    print(f"Created: {rivendell.name} (ID: {rivendell.id})")

    mordor = Entity(
        name="Mordor",
        type="location",
        description="Dark realm of Sauron in the southeast of Middle-earth.",
        attributes={"type": "realm"},
    )
    db.insert_entity(mordor)
    print(f"Created: {mordor.name} (ID: {mordor.id})")

    # Create the One Ring artifact
    one_ring = Entity(
        name="The One Ring",
        type="artifact",
        description="Master ring forged by Sauron to control all other Rings of Power. "
        f"Currently carried by [[id:{frodo.id}|Frodo Baggins]].",
        attributes={"power": "dominion over all rings"},
    )
    db.insert_entity(one_ring)
    print(f"Created: {one_ring.name} (ID: {one_ring.id})")

    # Create remaining Fellowship members
    sam = Entity(
        name="Samwise Gamgee",
        type="character",
        description="Frodo's gardener and most faithful companion. He accompanied Frodo to [[id:{frodo_id}|Mount Doom]].",
        attributes={"race": "Hobbit", "aliases": ["Sam"]},
    )
    db.insert_entity(
        sam
    )  # Note: We need early IDs for linking, but we can't link to things not yet created if we resolve immediately.
    # Better strategy: Create all entities first, then run link processing pass on all of them.
    print(f"Created: {sam.name} (ID: {sam.id})")

    merry = Entity(
        name="Meriadoc Brandybuck",
        type="character",
        description="A hobbit of the Shire, known as Merry. He became an Esquire of Rohan.",
        attributes={"race": "Hobbit", "aliases": ["Merry", "Kalimac"]},
    )
    db.insert_entity(merry)
    print(f"Created: {merry.name} (ID: {merry.id})")

    pippin = Entity(
        name="Peregrin Took",
        type="character",
        description="A hobbit of the Shire, known as Pippin. He became a Guard of the Citadel in [[id:{minas_tirith_id}|Minas Tirith]].",
        attributes={"race": "Hobbit", "aliases": ["Pippin", "Razanur"]},
    )
    db.insert_entity(pippin)
    print(f"Created: {pippin.name} (ID: {pippin.id})")

    legolas = Entity(
        name="Legolas Greenleaf",
        type="character",
        description="Prince of the Woodland Realm, a master archer who joined the Fellowship.",
        attributes={"race": "Elf", "father": "Thranduil"},
    )
    db.insert_entity(legolas)
    print(f"Created: {legolas.name} (ID: {legolas.id})")

    gimli = Entity(
        name="Gimli",
        type="character",
        description="Dwarf warrior of the House of Durin, son of Glóin. Developed a close friendship with [[id:{legolas.id}|Legolas]].",
        attributes={"race": "Dwarf", "titles": ["Elf-friend"]},
    )
    db.insert_entity(gimli)
    print(f"Created: {gimli.name} (ID: {gimli.id})")

    boromir = Entity(
        name="Boromir",
        type="character",
        description="Son of the Steward of Gondor. He fell defending Merry and Pippin against Uruk-hai.",
        attributes={"race": "Man", "home": "Gondor"},
    )
    db.insert_entity(boromir)
    print(f"Created: {boromir.name} (ID: {boromir.id})")

    # Other Major Characters
    gollum = Entity(
        name="Gollum",
        type="character",
        description="Originally a hobbit named Sméagol, corrupted by [[id:{one_ring_id}|the One Ring]]. He guided Frodo and Sam into Mordor.",
        attributes={"race": "Hobbit (corrupted)", "aliases": ["Smeagol", "Trahald"]},
    )
    db.insert_entity(gollum)
    print(f"Created: {gollum.name} (ID: {gollum.id})")

    saruman = Entity(
        name="Saruman",
        type="character",
        description="Leader of the Istari who fell into darkness, desiring [[id:{one_ring_id}|the One Ring]] for himself. Ruled from [[id:{isengard_id}|Isengard]].",
        attributes={"race": "Maia", "aliases": ["Saruman the White", "Sharkey"]},
    )
    db.insert_entity(saruman)
    print(f"Created: {saruman.name} (ID: {saruman.id})")

    galadriel = Entity(
        name="Galadriel",
        type="character",
        description="Lady of [[id:{lothlorien_id}|Lothlórien]], one of the greatest Elves in Middle-earth.",
        attributes={"race": "Elf", "ring": "Nenya"},
    )
    db.insert_entity(galadriel)
    print(f"Created: {galadriel.name} (ID: {galadriel.id})")

    elrond = Entity(
        name="Elrond",
        type="character",
        description="Lord of [[id:{rivendell.id}|Rivendell]], bearer of Vilya.",
        attributes={"race": "Half-elven"},
    )
    db.insert_entity(elrond)

    bilbo = Entity(
        name="Bilbo Baggins",
        type="character",
        description="Uncle of [[id:{frodo.id}|Frodo]], original finder of the Ring from [[id:{gollum.id}|Gollum]].",
        attributes={"race": "Hobbit"},
    )
    db.insert_entity(bilbo)

    # More Locations
    moria = Entity(
        name="Moria",
        type="location",
        description="Ancient subterranean kingdom of the Dwarves, also known as Khazad-dûm. "
        "The Fellowship traveled through here and faced a Balrog.",
        attributes={"type": "mine", "aliases": ["Khazad-dûm"]},
    )
    db.insert_entity(moria)
    print(f"Created: {moria.name} (ID: {moria.id})")

    lothlorien = Entity(
        name="Lothlórien",
        type="location",
        description="Golden wood of the Elves, ruled by Celeborn and [[id:{galadriel.id}|Galadriel]].",
        attributes={"type": "forest"},
    )
    db.insert_entity(lothlorien)  # Store ID for Galadriel link update

    isengard = Entity(
        name="Isengard",
        type="location",
        description="Fortress at the southern end of the Misty Mountains, home to [[id:{saruman.id}|Saruman]].",
        attributes={"type": "fortress", "tower": "Orthanc"},
    )
    db.insert_entity(isengard)

    minas_tirith = Entity(
        name="Minas Tirith",
        type="location",
        description="City of the Kings, capital of Gondor. Besieged during the War of the Ring.",
        attributes={"type": "city"},
    )
    db.insert_entity(minas_tirith)

    mount_doom = Entity(
        name="Mount Doom",
        type="location",
        description="Volcano in [[id:{mordor.id}|Mordor]] where the Ring was forged and destroyed.",
        attributes={"aliases": ["Orodruin"]},
    )
    db.insert_entity(mount_doom)

    # Artifacts
    sting = Entity(
        name="Sting",
        type="artifact",
        description="Elven dagger carried by [[id:{bilbo.id}|Bilbo]] and later [[id:{frodo.id}|Frodo]]. glows blue when Orcs are near.",
        attributes={"maker": "Elves of Gondolin"},
    )
    db.insert_entity(sting)

    anduril = Entity(
        name="Andúril",
        type="artifact",
        description="Sword reforged from the shards of Narsil, wielded by [[id:{aragorn.id}|Aragorn]].",
        attributes={"aliases": ["Flame of the West"]},
    )
    db.insert_entity(anduril)

    # Update placeholders in descriptions for complex linking
    # We use a second pass of updates to ensure all IDs are available

    # Update descriptions with real IDs
    sam.description = sam.description.replace("{frodo_id}", frodo.id).replace(
        "{mount_doom_id}", mount_doom.id
    )  # Fixed typo in variable name usage in prep
    pippin.description = pippin.description.replace(
        "{minas_tirith_id}", minas_tirith.id
    )
    gollum.description = gollum.description.replace("{one_ring_id}", one_ring.id)
    saruman.description = saruman.description.replace(
        "{one_ring_id}", one_ring.id
    ).replace("{isengard_id}", isengard.id)
    galadriel.description = galadriel.description.replace(
        "{lothlorien_id}", lothlorien.id
    )

    # Save updates
    for e in [sam, pippin, gollum, saruman, galadriel]:
        db.insert_entity(e)

    # Process wiki links for all entities
    print("\nProcessing wiki links for all entities...")
    for entity in db.get_all_entities():
        # Simple fix for the placeholders we just swapped manually:
        # The auto-linker might find more
        cmd = ProcessWikiLinksCommand(entity.id, entity.description)
        cmd.execute(db)

    print("\nCreating Middle Earth events...")

    # Create key events
    council_elrond = Event(
        name="Council of Elrond",
        lore_date=3018.0,  # Third Age year 3018
        description=f"A great council held at [[id:{rivendell.id}|Rivendell]] where the fate "
        f"of [[id:{one_ring.id}|the One Ring]] was decided. "
        f"[[id:{frodo.id}|Frodo]] volunteered to carry the Ring to [[id:{mordor.id}|Mordor]].",
        type="council",
        attributes={"age": "Third Age"},
    )
    db.insert_event(council_elrond)
    print(f"Created: {council_elrond.name} (Date: TA {int(council_elrond.lore_date)})")

    fellowship_formed = Event(
        name="Formation of the Fellowship",
        lore_date=3018.5,
        description=f"[[id:{gandalf.id}|Gandalf]], [[id:{aragorn.id}|Aragorn]], "
        f"[[id:{frodo.id}|Frodo]], [[id:{sam.id}|Sam]], [[id:{merry.id}|Merry]], [[id:{pippin.id}|Pippin]], "
        f"[[id:{legolas.id}|Legolas]], [[id:{gimli.id}|Gimli]], and [[id:{boromir.id}|Boromir]] "
        f"formed the Fellowship of the Ring.",
        type="alliance",
        attributes={"age": "Third Age"},
    )
    db.insert_event(fellowship_formed)
    print(f"Created: {fellowship_formed.name}")

    moria_journey = Event(
        name="Journey through Moria",
        lore_date=3019.01,
        description=f"The Fellowship passed through [[id:{moria.id}|Moria]]. [[id:{gandalf.id}|Gandalf]] fell fighting the Balrog.",
        type="adventure",
        attributes={"location": "Khazad-dûm"},
    )
    db.insert_event(moria_journey)

    breaking_fellowship = Event(
        name="Breaking of the Fellowship",
        lore_date=3019.02,
        description=f"At Parth Galen, [[id:{boromir.id}|Boromir]] fell. [[id:{frodo.id}|Frodo]] and [[id:{sam.id}|Sam]] left for [[id:{mordor.id}|Mordor]]. "
        f"[[id:{merry.id}|Merry]] and [[id:{pippin.id}|Pippin]] were captured.",
        type="separation",
        attributes={"location": "Parth Galen"},
    )
    db.insert_event(breaking_fellowship)

    helms_deep = Event(
        name="Battle of Helm's Deep",
        lore_date=3019.03,
        description=f"Forces of Rohan led by Theoden and [[id:{aragorn.id}|Aragorn]] defended against [[id:{saruman.id}|Saruman]]'s army from [[id:{isengard.id}|Isengard]].",
        type="battle",
        attributes={"location": "Helm's Deep"},
    )
    db.insert_event(helms_deep)

    pelennor = Event(
        name="Battle of the Pelennor Fields",
        lore_date=3019.04,
        description=f"The greatest battle of the age at [[id:{minas_tirith.id}|Minas Tirith]]. "
        f"Rohan arrived to aid Gondor against the Witch-king and forces of [[id:{mordor.id}|Mordor]].",
        type="battle",
        attributes={"location": "Minas Tirith"},
    )
    db.insert_event(pelennor)

    fall_of_sauron = Event(
        name="Fall of Sauron",
        lore_date=3019.05,
        description=f"[[id:{sauron.id}|Sauron]] was defeated when [[id:{one_ring.id}|the One Ring]] "
        f"was destroyed in [[id:{mount_doom.id}|Mount Doom]] by [[id:{frodo.id}|Frodo]] and [[id:{gollum.id}|Gollum]].",
        type="battle",
        attributes={"age": "Third Age", "significance": "End of the Third Age"},
    )
    db.insert_event(fall_of_sauron)
    print(f"Created: {fall_of_sauron.name}")

    scouring = Event(
        name="Scouring of the Shire",
        lore_date=3019.09,
        description=f"The Hobbits returned to correct wrongs in [[id:{shire.id}|The Shire]] caused by [[id:{saruman.id}|Saruman]].",
        type="conflict",
        attributes={"location": "The Shire"},
    )
    db.insert_event(scouring)

    # Process wiki links for events
    print("\nProcessing wiki links for all events...")
    for event in db.get_all_events():
        cmd = ProcessWikiLinksCommand(event.id, event.description, field="description")
        cmd.execute(db)

    print("\n" + "=" * 60)
    print("Middle Earth database populated successfully!")
    print("=" * 60)
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
    print(
        "\nYou can now open this database in ProjektKraken to explore the wiki links!"
    )
