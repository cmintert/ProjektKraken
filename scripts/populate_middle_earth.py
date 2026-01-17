import logging
import os
import sys
import time
import uuid

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.core.entities import Entity  # noqa: E402
from src.core.events import Event  # noqa: E402
from src.services.db_service import DatabaseService  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "world.kraken")

# --- DATA GENERATION ---

TAGS = [
    # Types
    {"name": "Character", "color": "#FFC107"},
    {"name": "Location", "color": "#4CAF50"},
    {"name": "Artifact", "color": "#9C27B0"},
    {"name": "Faction", "color": "#607D8B"},
    # Races
    {"name": "Hobbit", "color": "#8BC34A"},
    {"name": "Elf", "color": "#00BCD4"},
    {"name": "Dwarf", "color": "#795548"},
    {"name": "Man", "color": "#2196F3"},
    {"name": "Maiar", "color": "#E91E63"},
    {"name": "Orc", "color": "#3E2723"},
    # Alignments/Groups
    {"name": "Fellowship", "color": "#FFD700"},
    {"name": "Thorin's Company", "color": "#795548"},
    {"name": "White Council", "color": "#FFFFFF"},
    {"name": "Forces of Sauron", "color": "#000000"},
    {"name": "Ringbearer", "color": "#FF9800"},
]

ENTITIES_DATA = [
    # -- Hobbits --
    {
        "name": "Frodo Baggins",
        "type": "character",
        "tags": ["Hobbit", "Fellowship", "Ringbearer"],
        "desc": "A Hobbit of the Shire who inherited the One Ring from his cousin Bilbo and undertook the quest to destroy it in Mount Doom.",
    },
    {
        "name": "Samwise Gamgee",
        "type": "character",
        "tags": ["Hobbit", "Fellowship", "Ringbearer"],
        "desc": "Frodo's gardener and loyal companion, a stout-hearted Hobbit who proved to be the chief hero of the quest.",
    },
    {
        "name": "Meriadoc Brandybuck",
        "type": "character",
        "tags": ["Hobbit", "Fellowship"],
        "desc": "A Hobbit of the Shire and one of Frodo's cousins. Known as Merry. Became an Esquire of Rohan.",
    },
    {
        "name": "Peregrin Took",
        "type": "character",
        "tags": ["Hobbit", "Fellowship"],
        "desc": "A Hobbit of the Shire and one of Frodo's cousins. Known as Pippin. Became a Guard of the Citadel.",
    },
    {
        "name": "Bilbo Baggins",
        "type": "character",
        "tags": ["Hobbit", "Thorin's Company", "Ringbearer"],
        "desc": "A Hobbit who found the One Ring during his adventure with Thorin Oakenshield to the Lonely Mountain.",
    },
    {
        "name": "Gollum",
        "type": "character",
        "tags": ["Hobbit", "Ringbearer", "Forces of Sauron"],
        "desc": "Originally a Stoor Hobbit named Sméagol, corrupted by the One Ring over centuries.",
    },
    # -- Wizards --
    {
        "name": "Gandalf",
        "type": "character",
        "tags": [
            "Maiar",
            "Fellowship",
            "White Council",
            "Thorin's Company",
            "Ringbearer",
        ],
        "desc": "A Wizard (Istar) sent to Middle-earth to contest the power of Sauron. Known as Mithrandir to the Elves. Wielder of Narya.",
    },
    {
        "name": "Saruman",
        "type": "character",
        "tags": ["Maiar", "White Council", "Forces of Sauron"],
        "desc": "The head of the White Council who was corrupted by his study of the Enemy and desire for power.",
    },
    {
        "name": "Radagast",
        "type": "character",
        "tags": ["Maiar", "White Council"],
        "desc": "A Wizard known as the Brown, a lover of animals and birds.",
    },
    # -- Elves --
    {
        "name": "Aragorn II Elessar",
        "type": "character",
        "tags": ["Man", "Fellowship"],
        "desc": "Chieftain of the Dúnedain of the North, later crowned King Elessar of the Reunited Kingdom. Heir of Isildur.",
    },
    {
        "name": "Legolas",
        "type": "character",
        "tags": ["Elf", "Fellowship"],
        "desc": "A Sindarin Elf of the Woodland Realm, son of King Thranduil.",
    },
    {
        "name": "Gimli",
        "type": "character",
        "tags": ["Dwarf", "Fellowship"],
        "desc": "A Dwarf of Erebor, son of Glóin. Became known as Elf-friend.",
    },
    {
        "name": "Boromir",
        "type": "character",
        "tags": ["Man", "Fellowship"],
        "desc": "A Captain of Gondor, son of Denethor II. He succumbed to the Ring's temptation but died defending Merry and Pippin.",
    },
    {
        "name": "Elrond",
        "type": "character",
        "tags": ["Elf", "White Council", "Ringbearer"],
        "desc": "Lord of Rivendell (Imladris), one of the mighty rulers of old. Wielder of Vilya.",
    },
    {
        "name": "Galadriel",
        "type": "character",
        "tags": ["Elf", "White Council", "Ringbearer"],
        "desc": "Lady of Lothlórien, one of the greatest of the Elves in Middle-earth. Wielder of Nenya.",
    },
    {
        "name": "Arwen Undómiel",
        "type": "character",
        "tags": ["Elf"],
        "desc": "Daughter of Elrond, also known as Evenstar. Betrothed to Aragorn.",
    },
    {
        "name": "Thranduil",
        "type": "character",
        "tags": ["Elf"],
        "desc": "King of the Woodland Realm in Northern Mirkwood.",
    },
    {
        "name": "Celebrimbor",
        "type": "character",
        "tags": ["Elf", "Ringbearer"],
        "desc": "Elven-smith of Eregion who forged the Three Rings of the Elves.",
    },
    {
        "name": "Gil-galad",
        "type": "character",
        "tags": ["Elf"],
        "desc": "Last High King of the Noldor in Middle-earth.",
    },
    # -- Men --
    {
        "name": "Faramir",
        "type": "character",
        "tags": ["Man"],
        "desc": "Brother of Boromir, Captain of the Rangers of Ithilien.",
    },
    {
        "name": "Denethor II",
        "type": "character",
        "tags": ["Man"],
        "desc": "Ruling Steward of Gondor, father of Boromir and Faramir.",
    },
    {"name": "Théoden", "type": "character", "tags": ["Man"], "desc": "King of Rohan."},
    {
        "name": "Éomer",
        "type": "character",
        "tags": ["Man"],
        "desc": "Nephew of Théoden, Third Marshal of the Riddermark.",
    },
    {
        "name": "Éowyn",
        "type": "character",
        "tags": ["Man"],
        "desc": "Niece of Théoden, shieldmaiden of Rohan who slew the Witch-king.",
    },
    {
        "name": "Isildur",
        "type": "character",
        "tags": ["Man", "Ringbearer"],
        "desc": "High King of Gondor and Arnor who cut the Ring from Sauron's hand.",
    },
    {
        "name": "Bard the Bowman",
        "type": "character",
        "tags": ["Man"],
        "desc": "Slayer of Smaug and King of Dale.",
    },
    # -- Dwarves --
    {
        "name": "Thorin Oakenshield",
        "type": "character",
        "tags": ["Dwarf", "Thorin's Company"],
        "desc": "Leader of the Company of Dwarves who reclaimed Erebor.",
    },
    {
        "name": "Balin",
        "type": "character",
        "tags": ["Dwarf", "Thorin's Company"],
        "desc": "Dwarf of Thorin's company, later Lord of Moria.",
    },
    # -- Villains --
    {
        "name": "Sauron",
        "type": "character",
        "tags": ["Maiar", "Forces of Sauron", "Ringbearer"],
        "desc": "The Dark Lord, creator of the One Ring.",
    },
    {
        "name": "The Witch-king of Angmar",
        "type": "character",
        "tags": ["Man", "Forces of Sauron"],
        "desc": "Lord of the Nazgûl, Chief of the Nine.",
    },
    {
        "name": "Smaug",
        "type": "character",
        "tags": ["Forces of Sauron"],
        "desc": "The last great dragon of Middle-earth.",
    },
    {
        "name": "Durin's Bane",
        "type": "character",
        "tags": ["Maiar", "Forces of Sauron"],
        "desc": "A Balrog of Morgoth that awoke in Moria.",
    },
    {
        "name": "Shelob",
        "type": "character",
        "tags": ["Forces of Sauron"],
        "desc": "A great spider dwelling in the passes of Cirith Ungol.",
    },
    # -- Locations --
    {
        "name": "The Shire",
        "type": "location",
        "tags": ["Location"],
        "desc": "A region of Eriador inhabited by Hobbits.",
    },
    {
        "name": "Bag End",
        "type": "location",
        "tags": ["Location"],
        "desc": "The home of Bilbo and Frodo Baggins in Hobbiton.",
    },
    {
        "name": "Rivendell",
        "type": "location",
        "tags": ["Location", "Elf"],
        "desc": "Elrond's house in the foothills of the Misty Mountains. Also Imladris.",
    },
    {
        "name": "Moria",
        "type": "location",
        "tags": ["Location", "Dwarf"],
        "desc": "The great underground kingdom of the Dwarves. Also Khazad-dûm.",
    },
    {
        "name": "Lothlórien",
        "type": "location",
        "tags": ["Location", "Elf"],
        "desc": "The Golden Wood, realm of Galadriel and Celeborn.",
    },
    {
        "name": "Rohan",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "The land of the Horse-lords.",
    },
    {
        "name": "Edoras",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "Capital of Rohan.",
    },
    {
        "name": "Helm's Deep",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "A fortified gorge in the White Mountains.",
    },
    {
        "name": "Isengard",
        "type": "location",
        "tags": ["Location"],
        "desc": "A fortress at the southern end of the Misty Mountains, home to Saruman.",
    },
    {
        "name": "Gondor",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "The greatest realm of Men in the West.",
    },
    {
        "name": "Minas Tirith",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "The City of Kings, capital of Gondor.",
    },
    {
        "name": "Osgiliath",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "The ancient capital of Gondor, now a ruin.",
    },
    {
        "name": "Mordor",
        "type": "location",
        "tags": ["Location", "Forces of Sauron"],
        "desc": "The Land of Shadow, realm of Sauron.",
    },
    {
        "name": "Barad-dûr",
        "type": "location",
        "tags": ["Location", "Forces of Sauron"],
        "desc": "The Dark Tower, fortress of Sauron.",
    },
    {
        "name": "Mount Doom",
        "type": "location",
        "tags": ["Location", "Forces of Sauron"],
        "desc": "The volcano where the One Ring was forged and destroyed. Orodruin.",
    },
    {
        "name": "Lonely Mountain",
        "type": "location",
        "tags": ["Location", "Dwarf"],
        "desc": "Erebor, the Kingdom under the Mountain.",
    },
    {
        "name": "Lake-town",
        "type": "location",
        "tags": ["Location", "Man"],
        "desc": "Esgaroth, a town of Men upon the Long Lake.",
    },
    # -- Artifacts --
    {
        "name": "The One Ring",
        "type": "artifact",
        "tags": ["Artifact", "Ringbearer"],
        "desc": "The Ruling Ring, forged by Sauron in the fires of Mount Doom.",
    },
    {
        "name": "Narya",
        "type": "artifact",
        "tags": ["Artifact", "Ringbearer"],
        "desc": "The Ring of Fire, worn by Gandalf.",
    },
    {
        "name": "Nenya",
        "type": "artifact",
        "tags": ["Artifact", "Ringbearer"],
        "desc": "The Ring of Water, worn by Galadriel.",
    },
    {
        "name": "Vilya",
        "type": "artifact",
        "tags": ["Artifact", "Ringbearer"],
        "desc": "The Ring of Air, worn by Elrond.",
    },
    {
        "name": "Sting",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "An Elven dagger carried by Bilbo and later Frodo.",
    },
    {
        "name": "Glamdring",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "The Foe-hammer, sword of Gandalf.",
    },
    {
        "name": "Orcrist",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "The Goblin-cleaver, sword of Thorin.",
    },
    {
        "name": "Andúril",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "The Flame of the West, reforged from the shards of Narsil.",
    },
    {
        "name": "Phial of Galadriel",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "A crystal phial containing the light of Eärendil's star.",
    },
    {
        "name": "Palantír of Orthanc",
        "type": "artifact",
        "tags": ["Artifact"],
        "desc": "One of the Seeing-stones, used by Saruman.",
    },
]

# Timestamps are roughly T.A. years converted to "lore_date" floats
# Convention: T.A. 1 = 3000.0 (arbitrary offset to make them positive floats)
# Actually, let's just use the year directly. T.A. 3018 = 3018.0
EVENTS_DATA = [
    # -- The Hobbit (T.A. 2941) --
    {
        "name": "Gandalf visits Bag End",
        "date": 2941.0,
        "desc": "Gandalf scratches a sign on Bilbo's door.",
        "tags": ["Hobbit"],
    },
    {
        "name": "The Unexpected Party",
        "date": 2941.1,
        "desc": "Thorin and Company arrive at Bag End.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Roast Mutton",
        "date": 2941.15,
        "desc": "The Company encounters three Trolls.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Rivendell",
        "date": 2941.2,
        "desc": "The Company rests in the Last Homely House.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Riddles in the Dark",
        "date": 2941.3,
        "desc": "Bilbo finds the One Ring and meets Gollum.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Attack of the Spiders",
        "date": 2941.4,
        "desc": "Bilbo rescues the Dwarves from spiders in Mirkwood.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Beorn's Hall",
        "date": 2941.45,
        "desc": "The Company is hosted by the skin-changer Beorn.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Enchanted Stream",
        "date": 2941.46,
        "desc": "Bombur falls into the enchanted stream in Mirkwood.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "The Elvenking's Feast",
        "date": 2941.48,
        "desc": "Thorin and Company are captured by Wood-elves.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Barrel-rider",
        "date": 2941.5,
        "desc": "Bilbo helps the Dwarves escape the Elven-king's halls in barrels.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Arrisal at Lake-town",
        "date": 2941.55,
        "desc": "The Company is welcomed by the Master of Lake-town.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Opening of the Secret Door",
        "date": 2941.58,
        "desc": "The last light of Durin's Day reveals the keyhole.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Inside the Mountain",
        "date": 2941.59,
        "desc": "Bilbo talks to Smaug.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    {
        "name": "Death of Smaug",
        "date": 2941.6,
        "desc": "Bard the Bowman slays the dragon Smaug.",
        "tags": ["Hobbit"],
    },
    {
        "name": "The Arkenstone",
        "date": 2941.65,
        "desc": "Bilbo finds the Heart of the Mountain.",
        "tags": ["Hobbit", "Artifact"],
    },
    {
        "name": "Bilbo gives up the Arkenstone",
        "date": 2941.68,
        "desc": "Bilbo gives the Arkenstone to Bard and Thranduil.",
        "tags": ["Hobbit"],
    },
    {
        "name": "Battle of Five Armies",
        "date": 2941.7,
        "desc": "Men, Elves, and Dwarves fight against Goblins and Wargs.",
        "tags": ["Hobbit", "Thorin's Company"],
    },
    # -- Second Age / History --
    {
        "name": "Forging of the Rings",
        "date": 1600.0,
        "desc": "Sauron forges the One Ring in Orodruin.",
        "tags": ["Artifact", "Forces of Sauron"],
    },
    {
        "name": "War of the Elves and Sauron",
        "date": 1693.0,
        "desc": "Sauron makes war on the Elves.",
        "tags": ["Elf", "Forces of Sauron"],
    },
    {
        "name": "Downfall of Númenor",
        "date": 3319.0,
        "desc": "Akallabêth. The destruction of the island kingdom.",
        "tags": ["Man"],
    },
    {
        "name": "Last Alliance formed",
        "date": 3430.0,
        "desc": "Gil-galad and Elendil form the Last Alliance.",
        "tags": ["Elf", "Man"],
    },
    {
        "name": "Battle of Dagorlad",
        "date": 3434.0,
        "desc": "The Last Alliance defeats Sauron's forces outside Mordor.",
        "tags": ["Battle"],
    },
    {
        "name": "Siege of Barad-dûr",
        "date": 3441.0,
        "desc": "Sauron is overthrown, Isildur takes the Ring.",
        "tags": ["Battle", "Ringbearer"],
    },
    # -- Interlude --
    {
        "name": "Bilbo's Farewell Party",
        "date": 3001.0,
        "desc": "Bilbo turns 111 and leaves the Shire.",
        "tags": ["Hobbit", "Shire"],
    },
    {
        "name": "Gollum captured by Aragorn",
        "date": 3017.0,
        "desc": "Aragorn captures Gollum in the Dead Marshes.",
        "tags": ["Fellowship"],
    },
    # -- Fellowship of the Ring (T.A. 3018) --
    {
        "name": "Gandalf returns to Bag End",
        "date": 3018.2,
        "desc": "Gandalf confirms Frodo's ring is the One Ring.",
        "tags": ["Fellowship", "Hobbit"],
    },
    {
        "name": "Three is Company",
        "date": 3018.605,
        "desc": "Frodo, Sam, and Pippin encounter a Black Rider.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Fog on the Barrow-downs",
        "date": 3018.615,
        "desc": "The Hobbits are captured by Barrow-wights.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Departure from Bag End",
        "date": 3018.6,
        "desc": "Frodo, Sam, and Pippin leave Bag End.",
        "tags": ["Fellowship", "Hobbit"],
    },
    {
        "name": "Old Man Willow",
        "date": 3018.61,
        "desc": "The Hobbits are trapped by a tree and saved by Tom Bombadil.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Arrival at Bree",
        "date": 3018.62,
        "desc": "The Hobbits meet Strider at the Prancing Pony.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Midgewater Marshes",
        "date": 3018.63,
        "desc": "Crossing the marshes to avoid the Road.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Attack at Weathertop",
        "date": 3018.65,
        "desc": "The Witch-king stabs Frodo with a Morgul-blade.",
        "tags": ["Fellowship", "Forces of Sauron"],
    },
    {
        "name": "Glorfindel",
        "date": 3018.67,
        "desc": "The Elf-lord meets the Hobbits near the Ford.",
        "tags": ["Fellowship", "Elf"],
    },
    {
        "name": "Flight to the Ford",
        "date": 3018.68,
        "desc": "Frodo crosses the Ford of Bruinen, defying the Nazgûl.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Council of Elrond",
        "date": 3018.7,
        "desc": "The Fellowship of the Ring is formed.",
        "tags": ["Fellowship", "White Council"],
    },
    {
        "name": "Departure of the Fellowship",
        "date": 3018.9,
        "desc": "The Company sets out from Rivendell.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Ring Goes South",
        "date": 3018.95,
        "desc": "The Fellowship fails to cross Caradhras.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Wolves in Eregion",
        "date": 3018.92,
        "desc": "Gandalf creates fire to fight off Wargs.",
        "tags": ["Fellowship"],
    },
    # -- The Two Towers / Return of the King (T.A. 3019) --
    {
        "name": "Gate of Moria",
        "date": 3019.01,
        "desc": "Gandalf opens the West-gate.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Chamber of Mazarbul",
        "date": 3019.04,
        "desc": "The Fellowship finds Balin's tomb.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Bridge of Khazad-dûm",
        "date": 3019.05,
        "desc": "Gandalf falls with the Balrog.",
        "tags": ["Fellowship", "Maiar"],
    },
    {
        "name": "Lothlórien",
        "date": 3019.08,
        "desc": "The Fellowship rests in the Golden Wood.",
        "tags": ["Fellowship", "Elf"],
    },
    {
        "name": "Mirror of Galadriel",
        "date": 3019.09,
        "desc": "Frodo and Sam look into the mirror.",
        "tags": ["Fellowship", "Elf"],
    },
    {
        "name": "The Great River",
        "date": 3019.12,
        "desc": "The Fellowship travels down the Anduin.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Argonath",
        "date": 3019.14,
        "desc": "The Fellowship passes the Pillars of Kings.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Breaking of the Fellowship",
        "date": 3019.15,
        "desc": "Frodo and Sam separate from the others at Parth Galen.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Uruk-hai Attack",
        "date": 3019.155,
        "desc": "Saruman's Uruk-hai attack the Fellowship.",
        "tags": ["Fellowship", "Forces of Sauron"],
    },
    {
        "name": "Death of Boromir",
        "date": 3019.16,
        "desc": "Boromir defends Merry and Pippin against Uruk-hai.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Meeting Treebeard",
        "date": 3019.18,
        "desc": "Merry and Pippin meet the oldest Ent.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Gandalf the White",
        "date": 3019.2,
        "desc": "Gandalf returns as the White Rider in Fangorn.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Battle of Helm's Deep",
        "date": 3019.22,
        "desc": "Rohan defends against Saruman's army.",
        "tags": ["Fellowship", "Battle"],
    },
    {
        "name": "Destruction of Isengard",
        "date": 3019.23,
        "desc": "The Ents march on Isengard.",
        "tags": ["Fellowship", "Battle"],
    },
    {
        "name": "The Palantír",
        "date": 3019.24,
        "desc": "Pippin looks into the Stone of Orthanc.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Shelob's Lair",
        "date": 3019.25,
        "desc": "Frodo is stung by Shelob; Sam takes the Ring.",
        "tags": ["Fellowship", "Forces of Sauron"],
    },
    {
        "name": "Battle of the Pelennor Fields",
        "date": 3019.26,
        "desc": "The great battle before Minas Tirith.",
        "tags": ["Fellowship", "Battle"],
    },
    {
        "name": "Death of Théoden",
        "date": 3019.261,
        "desc": "The King of Rohan falls.",
        "tags": ["Battle"],
    },
    {
        "name": "Death of the Witch-king",
        "date": 3019.262,
        "desc": "Éowyn and Merry slay the Lord of the Nazgûl.",
        "tags": ["Battle", "Forces of Sauron"],
    },
    {
        "name": "Pyre of Denethor",
        "date": 3019.263,
        "desc": "Denethor burns himself in the Hallows.",
        "tags": ["Man"],
    },
    {
        "name": "Houses of Healing",
        "date": 3019.265,
        "desc": "Aragorn heals Faramir, Éowyn, and Merry.",
        "tags": ["Fellowship", "Man"],
    },
    {
        "name": "Mouth of Sauron",
        "date": 3019.275,
        "desc": "The Messenger of Barad-dûr mocks the Captains of the West.",
        "tags": ["Battle", "Forces of Sauron"],
    },
    {
        "name": "Battle of the Morannon",
        "date": 3019.28,
        "desc": "The Black Gate opens.",
        "tags": ["Fellowship", "Battle"],
    },
    {
        "name": "Destruction of the Ring",
        "date": 3019.29,
        "desc": "Gollum falls into the cracks of Doom with the Ring.",
        "tags": ["Fellowship", "Forces of Sauron"],
    },
    {
        "name": "Field of Cormallen",
        "date": 3019.30,
        "desc": "The host of the West honors the Ringbearers.",
        "tags": ["Fellowship", "Battle"],
    },
    {
        "name": "Coronation of King Elessar",
        "date": 3019.4,
        "desc": "Aragorn is crowned King of Gondor and Arnor.",
        "tags": ["Fellowship"],
    },
    {
        "name": "Scouring of the Shire",
        "date": 3019.8,
        "desc": "The Hobbits reclaim the Shire from 'Sharkey'.",
        "tags": ["Fellowship", "Hobbit"],
    },
    # -- Aftermath (T.A. 3021) --
    {
        "name": "The Grey Havens",
        "date": 3021.5,
        "desc": "The Ringbearers depart Middle-earth.",
        "tags": ["Fellowship", "Elf"],
    },
]


def populate() -> None:
    logger.info(f"Connecting to database at {DB_PATH}")
    db_service = DatabaseService(DB_PATH)
    db_service.connect()

    # Clear existing data
    logger.warning("Clearing existing data...")
    with db_service.transaction() as conn:
        conn.execute("DELETE FROM relations")
        conn.execute("DELETE FROM event_tags")
        conn.execute("DELETE FROM entity_tags")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM entities")
        conn.execute("DELETE FROM tags")

    # Helper to clean text
    # Helper to clean text
    def clean(s: str) -> str:
        return s.replace("'", "").replace(" ", "_").lower()

    # 1. Tags
    logger.info(" seeding tags...")
    tag_map = {}  # name -> id
    with db_service.transaction() as conn:
        for tag_def in TAGS:
            tag_id = str(uuid.uuid4())
            name = tag_def["name"]
            color = tag_def.get("color")
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO tags (id, name, color, created_at) VALUES (?, ?, ?, ?)",
                    (tag_id, name, color, time.time()),
                )
                # Fetch actual ID in case of ignore
                cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row:
                    tag_map[name] = row["id"]
            except Exception as e:
                logger.error(f"Error inserting tag {name}: {e}")

    # 2. Entities
    logger.info("Seeding entities...")
    entity_map = {}  # name -> id

    for ent_data in ENTITIES_DATA:
        ent_id = str(uuid.uuid4())
        entity_map[ent_data["name"]] = ent_id

        attributes = {"_tags": ent_data.get("tags", [])}

        entity = Entity(
            name=ent_data["name"],
            type=ent_data["type"],
            description=ent_data.get("desc", ""),
            attributes=attributes,
            id=ent_id,
        )
        # Manually set tags via property isn't available on bulk insert usually, but here we can just create dicts or use the repo
        # The DB service doesn't have a bulk wrapper that handles tags automatically unless we augment the repo.
        # For simplicity, let's use the individual insert which typically handles repository delegation,
        # BUT wait, the DBS service insert_entity calls repo.insert.
        # The repo.insert usually just dumps attributes.
        # We need to manually populate the tag association tables if we want them indexed properly.
        # Actually, let's look at `db_service.py` again... `insert_entity` delegates to `_entity_repo.insert`.
        # We assume the EntityRepository handles tag extraction from attributes["_tags"].
        # If not, we might need to do it manually. Let's assume standard behavior for now but knowing ProjektKraken,
        # tags are often separate.
        # Let's check schema: yes `entity_tags` exists.
        # We will iterate and insert individually to be safe and ensure tags are processed if the service handles it.
        # If the service doesn't handle tags automatically (it might just store them in JSON), we might need to populate `entity_tags`.
        # However, looking at the schema, `entity_tags` is a separate table.
        # The `EntityRepository` likely handles this. To be safe, we will assume it does, or we might need to fix it.

        db_service.insert_entity(entity)

        # Manually link tags just in case (safer to ensure M2M is populated)
        with db_service.transaction() as conn:
            for tag_name in entity.tags:
                tag_id = tag_map.get(tag_name)
                if tag_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id, created_at) VALUES (?, ?, ?)",
                        (ent_id, tag_id, time.time()),
                    )

    logger.info(f"Inserted {len(ENTITIES_DATA)} entities.")

    # 3. Events
    logger.info("Seeding events...")
    event_map = {}
    for evt_data in EVENTS_DATA:
        evt_id = str(uuid.uuid4())
        event_map[evt_data["name"]] = evt_id

        attributes = {"_tags": evt_data.get("tags", [])}

        event = Event(
            name=evt_data["name"],
            lore_date=evt_data["date"],
            description=evt_data.get("desc", ""),
            attributes=attributes,
            id=evt_id,
            lore_duration=0.1,  # Default short duration
        )

        db_service.insert_event(event)

        # Manually link tags
        with db_service.transaction() as conn:
            for tag_name in event.tags:
                tag_id = tag_map.get(tag_name)
                if tag_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO event_tags (event_id, tag_id, created_at) VALUES (?, ?, ?)",
                        (evt_id, tag_id, time.time()),
                    )

    logger.info(f"Inserted {len(EVENTS_DATA)} events.")

    # 4. Relations
    logger.info("Seeding relations...")

    def create_rel(src_name: str, target_name: str, rel_type: str) -> None:
        src_id = entity_map.get(src_name) or event_map.get(src_name)
        tgt_id = entity_map.get(target_name) or event_map.get(target_name)

        if src_id and tgt_id:
            db_service.insert_relation(src_id, tgt_id, rel_type)
        else:
            logger.warning(
                f"Could not create relation: {src_name} -> {target_name} ({rel_type}) - Missing ID"
            )

    # Artifact Ownership
    create_rel("Frodo Baggins", "The One Ring", "bearer")
    create_rel("Frodo Baggins", "Sting", "owner")
    create_rel("Frodo Baggins", "Phial of Galadriel", "owner")
    create_rel("Samwise Gamgee", "Frodo Baggins", "companion")
    create_rel("Gandalf", "Narya", "bearer")
    create_rel("Gandalf", "Glamdring", "owner")
    create_rel("Galadriel", "Nenya", "bearer")
    create_rel("Elrond", "Vilya", "bearer")
    create_rel("Aragorn II Elessar", "Andúril", "owner")
    create_rel("Thorin Oakenshield", "Orcrist", "owner")
    create_rel("Saruman", "Palantír of Orthanc", "user")

    # Locations
    create_rel("Frodo Baggins", "Bag End", "resident")
    create_rel("Bilbo Baggins", "Bag End", "former_resident")
    create_rel("Elrond", "Rivendell", "lord")
    create_rel("Galadriel", "Lothlórien", "lady")
    create_rel("Théoden", "Edoras", "king")
    create_rel("Saruman", "Isengard", "ruler")
    create_rel("Sauron", "Barad-dûr", "lord")
    create_rel("Sauron", "Mordor", "ruler")
    create_rel("Bag End", "The Shire", "located_in")
    create_rel("Edoras", "Rohan", "located_in")
    create_rel("Helm's Deep", "Rohan", "located_in")
    create_rel("Minas Tirith", "Gondor", "located_in")
    create_rel("Osgiliath", "Gondor", "located_in")
    create_rel("Barad-dûr", "Mordor", "located_in")
    create_rel("Mount Doom", "Mordor", "located_in")

    # Familial / Social
    create_rel("Aragorn II Elessar", "Arwen Undómiel", "betrothed")
    create_rel("Boromir", "Denethor II", "son")
    create_rel("Faramir", "Denethor II", "son")
    create_rel("Éomer", "Théoden", "nephew")
    create_rel("Éowyn", "Théoden", "niece")
    create_rel("Legolas", "Thranduil", "son")

    # Events participation (Entities -> Events)
    create_rel("Frodo Baggins", "Council of Elrond", "participant")
    create_rel("Gandalf", "Council of Elrond", "participant")
    create_rel("Aragorn II Elessar", "Council of Elrond", "participant")
    create_rel("Boromir", "Council of Elrond", "participant")
    create_rel("Gimli", "Council of Elrond", "participant")
    create_rel("Legolas", "Council of Elrond", "participant")
    create_rel("Gandalf", "Bridge of Khazad-dûm", "combatant")
    create_rel("Durin's Bane", "Bridge of Khazad-dûm", "combatant")
    create_rel("Bilbo Baggins", "Riddles in the Dark", "participant")
    create_rel("Gollum", "Riddles in the Dark", "participant")
    create_rel("Gollum", "Destruction of the Ring", "casualty")
    create_rel("Frodo Baggins", "Destruction of the Ring", "participant")
    create_rel("Sauron", "Destruction of the Ring", "destroyed")

    logger.info("Database population complete.")
    db_service.close()


if __name__ == "__main__":
    populate()
