# API Reference

This document provides a comprehensive reference for ProjektKraken's code API.

## Table of Contents

1. [Core Module](#core-module)
2. [Services API](#services-api)
3. [Commands API](#commands-api)
4. [GUI Widgets API](#gui-widgets-api)
5. [Utility Modules](#utility-modules)
6. [CLI Tools](#cli-tools)

---

## Core Module

The `src/core/` module contains domain models and pure business logic with zero external dependencies.

### Events (`src/core/events.py`)

#### `Event`

Represents a point or span in time.

```python
@dataclass
class Event:
    name: str                              # Display name
    lore_date: float                       # Timeline position (1.0 = 1 day)
    description: str = ""                  # Rich text description
    type: str = "generic"                  # Event category
    lore_duration: float = 0.0             # Duration (0.0 = instant)
    attributes: Dict[str, Any] = field(default_factory=dict)  # Custom fields
    
    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
```

**Methods:**

- `to_dict() -> Dict[str, Any]` - Serialize to dictionary
- `from_dict(data: Dict[str, Any]) -> Event` - Deserialize from dictionary
- `tags` property - Get/set tags (stored in `attributes["_tags"]`)

**Example:**

```python
from src.core.events import Event

event = Event(
    name="Battle of Five Armies",
    lore_date=2941.0,
    lore_duration=0.1,  # ~2.4 hours
    type="battle",
    description="The climactic battle in the north..."
)

# Access attributes
print(event.name)  # "Battle of Five Armies"
print(event.lore_date)  # 2941.0

# Serialize
data = event.to_dict()

# Tags
event.tags = ["battle", "war"]
print(event.tags)  # ["battle", "war"]
```

---

### Entities (`src/core/entities.py`)

#### `Entity`

Represents timeless objects (characters, locations, artifacts).

```python
@dataclass
class Entity:
    name: str                              # Display name
    type: str                              # Entity category (person, place, etc.)
    description: str = ""                  # Rich text description
    attributes: Dict[str, Any] = field(default_factory=dict)  # Custom fields
    
    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
```

**Methods:**

- `to_dict() -> Dict[str, Any]` - Serialize to dictionary
- `from_dict(data: Dict[str, Any]) -> Entity` - Deserialize from dictionary
- `tags` property - Get/set tags

**Common Types:**

- `person` - Characters, NPCs
- `place` - Locations, settlements
- `organization` - Factions, groups
- `artifact` - Items, relics

**Example:**

```python
from src.core.entities import Entity

entity = Entity(
    name="Gandalf",
    type="person",
    description="Istari wizard..."
)

# Custom attributes
entity.attributes["race"] = "Maiar"
entity.attributes["aliases"] = ["Mithrandir", "The Grey"]
entity.attributes["arrival_date"] = 1000.0
```

---

### Relations (`src/core/relations.py`)

#### `Relation`

Represents a directed relationship between events and entities.

```python
@dataclass
class Relation:
    source_id: str                         # Source object ID
    target_id: str                         # Target object ID
    rel_type: str                          # Relationship type
    attributes: Dict[str, Any] = field(default_factory=dict)  # Metadata
    
    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
```

**Methods:**

- `to_dict() -> Dict[str, Any]` - Serialize
- `from_dict(data: Dict[str, Any]) -> Relation` - Deserialize

**Common Relation Types:**

- `caused` - Event caused by event/entity
- `located_in` - Object located in place
- `participated_in` - Entity participated in event
- `allied_with` - Entity allied with entity
- `parent_child` - Parent/child relationship

**Example:**

```python
from src.core.relations import Relation

relation = Relation(
    source_id=event_id,
    target_id=entity_id,
    rel_type="participated_in",
    attributes={"role": "commander"}
)
```

---

### Calendar (`src/core/calendar.py`)

#### `CalendarConfig`

Custom calendar configuration.

```python
@dataclass
class CalendarConfig:
    name: str
    epoch_name: str
    epoch_offset: float
    day_zero: float
    ticks_per_day: int
    months: List[MonthConfig]
    week_days: List[str]
    leap_year_rule: str
```

#### `CalendarConverter`

Converts between lore dates and calendar dates.

```python
class CalendarConverter:
    def lore_to_calendar(self, lore_date: float) -> CalendarDate
    def calendar_to_lore(self, calendar_date: CalendarDate) -> float
```

**Example:**

```python
from src.core.calendar import CalendarConfig, CalendarConverter

# Load calendar config
config = CalendarConfig.from_dict(data)
converter = CalendarConverter(config)

# Convert lore date to calendar
cal_date = converter.lore_to_calendar(2941.0)
print(f"Year {cal_date.year}, {cal_date.month_name} {cal_date.day}")
```

---

### Theme Manager (`src/core/theme_manager.py`)

#### `ThemeManager`

Singleton for managing UI themes.

```python
class ThemeManager:
    @staticmethod
    def instance() -> "ThemeManager"
    
    def get_theme(self) -> Dict[str, str]
    def get_color(self, key: str) -> str
    def apply_stylesheet(self, widget: QWidget) -> None
```

**Theme Keys:**

- `surface` - Background color
- `on_surface` - Text color
- `primary` - Accent color
- `border` - Border color
- `hover` - Hover state color

**Example:**

```python
from src.core.theme_manager import ThemeManager

tm = ThemeManager.instance()

# Get theme colors
surface = tm.get_color("surface")
primary = tm.get_color("primary")

# Apply to widget
tm.apply_stylesheet(my_widget)
```

---

## Services API

The `src/services/` module provides data access and background services.

### DatabaseService (`src/services/db_service.py`)

Main database interface using the Hybrid Schema pattern.

```python
class DatabaseService:
    def __init__(self, db_path: str = ":memory:") -> None
    def connect(self) -> None
    def close(self) -> None
    def commit(self) -> None
    def rollback(self) -> None
    
    # Repositories
    @property
    def event_repo(self) -> EventRepository
    
    @property
    def entity_repo(self) -> EntityRepository
    
    @property
    def relation_repo(self) -> RelationRepository
    
    @property
    def calendar_repo(self) -> CalendarRepository
    
    @property
    def map_repo(self) -> MapRepository
    
    @contextmanager
    def transaction(self) -> Iterator[None]
```

**Example:**

```python
from src.services.db_service import DatabaseService

db = DatabaseService("myworld.kraken")
db.connect()

try:
    # Use repositories
    events = db.event_repo.get_all()
    
    # Transaction
    with db.transaction():
        db.event_repo.insert(event)
        db.relation_repo.insert(relation)
finally:
    db.close()
```

---

### Repositories (`src/services/repositories/`)

Repository pattern for CRUD operations.

#### `EventRepository`

```python
class EventRepository(BaseRepository[Event]):
    def insert(self, event: Event) -> None
    def update(self, event: Event) -> None
    def delete(self, event_id: str) -> None
    def get_by_id(self, event_id: str) -> Optional[Event]
    def get_all(self) -> List[Event]
    def exists(self, event_id: str) -> bool
    
    # Event-specific
    def get_sorted_by_date(self) -> List[Event]
    def get_in_range(self, start: float, end: float) -> List[Event]
    def get_by_type(self, event_type: str) -> List[Event]
```

#### `EntityRepository`

```python
class EntityRepository(BaseRepository[Entity]):
    # Standard CRUD + type filtering, name search
    def get_by_type(self, entity_type: str) -> List[Entity]
    def search_by_name(self, query: str) -> List[Entity]
```

#### `RelationRepository`

```python
class RelationRepository(BaseRepository[Relation]):
    # Standard CRUD + graph operations
    def get_by_source(self, source_id: str) -> List[Relation]
    def get_by_target(self, target_id: str) -> List[Relation]
    def get_by_type(self, rel_type: str) -> List[Relation]
    def delete_by_source(self, source_id: str) -> None
    def delete_by_target(self, target_id: str) -> None
```

---

### Worker (`src/services/worker.py`)

Background thread for database operations.

```python
class DatabaseWorker:
    def submit_task(
        self,
        task_fn: Callable,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> None
    
    def stop(self) -> None
```

**Example:**

```python
from src.services.worker import DatabaseWorker

worker = DatabaseWorker()

# Submit background task
worker.submit_task(
    task_fn=lambda: db.event_repo.get_all(),
    on_success=lambda events: print(f"Loaded {len(events)} events"),
    on_error=lambda err: print(f"Error: {err}")
)

# Cleanup
worker.stop()
```

---

### SearchService (`src/services/search_service.py`)

Full-text search across events and entities.

```python
class SearchService:
    def search_events(self, query: str) -> List[Event]
    def search_entities(self, query: str) -> List[Entity]
    def search_all(self, query: str) -> Dict[str, List]
```

**Example:**

```python
from src.services.search_service import SearchService

search = SearchService(db_service)
results = search.search_events("battle")

for event in results:
    print(event.name)
```

---

## Commands API

The `src/commands/` module implements the Command Pattern for undo/redo.

### BaseCommand (`src/commands/base_command.py`)

Abstract base class for all commands.

```python
class BaseCommand(ABC):
    @abstractmethod
    def execute(self, db_service: DatabaseService) -> Union[bool, CommandResult]
    
    @abstractmethod
    def undo(self, db_service: DatabaseService) -> None
    
    @abstractmethod
    def to_dict(self) -> Dict
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict) -> "BaseCommand"
    
    def get_description(self) -> str
    
    @property
    def is_executed(self) -> bool
```

#### `CommandResult`

Standardized command result.

```python
@dataclass
class CommandResult:
    success: bool
    message: str = ""
    errors: Dict[str, str] = field(default_factory=dict)
    data: Dict = field(default_factory=dict)
    command_name: str = ""
```

---

### Event Commands (`src/commands/event_commands.py`)

#### `CreateEventCommand`

```python
class CreateEventCommand(BaseCommand):
    def __init__(
        self,
        name: str,
        lore_date: float,
        description: str = "",
        type: str = "generic",
        lore_duration: float = 0.0,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None
```

#### `UpdateEventCommand`

```python
class UpdateEventCommand(BaseCommand):
    def __init__(self, event_id: str, updates: Dict[str, Any]) -> None
```

#### `DeleteEventCommand`

```python
class DeleteEventCommand(BaseCommand):
    def __init__(self, event_id: str) -> None
```

**Example:**

```python
from src.commands.event_commands import CreateEventCommand

cmd = CreateEventCommand(
    name="New Event",
    lore_date=100.0,
    type="generic"
)

result = cmd.execute(db_service)
if result.success:
    event_id = result.data["event_id"]
    print(f"Created event: {event_id}")

# Undo
cmd.undo(db_service)
```

---

### Entity Commands (`src/commands/entity_commands.py`)

Similar structure to Event Commands:

- `CreateEntityCommand`
- `UpdateEntityCommand`
- `DeleteEntityCommand`

---

### Relation Commands (`src/commands/relation_commands.py`)

- `CreateRelationCommand`
- `DeleteRelationCommand`
- `UpdateRelationCommand`

---

### Composite Commands (`src/commands/composite_command.py`)

Execute multiple commands as one atomic operation.

```python
class CompositeCommand(BaseCommand):
    def __init__(self, commands: List[BaseCommand]) -> None
```

**Example:**

```python
from src.commands.composite_command import CompositeCommand

# Create event with relations in one command
cmd = CompositeCommand([
    CreateEventCommand(name="Battle", lore_date=100.0),
    CreateRelationCommand(
        source_id=event_id,
        target_id=entity_id,
        rel_type="participated_in"
    )
])

result = cmd.execute(db_service)
# Both execute or both fail (atomic)
```

---

## GUI Widgets API

The `src/gui/widgets/` module contains PySide6 widgets following the "dumb UI" principle.

### EventEditor (`src/gui/widgets/event_editor.py`)

```python
class EventEditorWidget(QWidget):
    # Signals
    save_requested = Signal(dict)          # Event data
    add_relation_requested = Signal(str, str, str, dict, bool)
    delete_relation_requested = Signal(str)
    wiki_link_clicked = Signal(str)
    
    # Methods
    def load_event(
        self,
        event: Event,
        relations: Optional[List[Dict]] = None
    ) -> None
    
    def clear(self) -> None
    def get_form_data(self) -> Dict[str, Any]
```

---

### EntityEditor (`src/gui/widgets/entity_editor.py`)

```python
class EntityEditorWidget(QWidget):
    # Signals
    save_requested = Signal(dict)
    add_relation_requested = Signal(str, str, str, dict, bool)
    delete_relation_requested = Signal(str)
    wiki_link_clicked = Signal(str)
    
    # Methods
    def load_entity(
        self,
        entity: Entity,
        relations: Optional[List[Dict]] = None
    ) -> None
    
    def clear(self) -> None
    def get_form_data(self) -> Dict[str, Any]
```

---

### TimelineWidget (`src/gui/widgets/timeline/`)

Complex timeline visualization widget.

```python
class TimelineWidget(QWidget):
    # Signals
    event_selected = Signal(str)           # Event ID
    event_double_clicked = Signal(str)
    date_range_changed = Signal(float, float)
    
    # Methods
    def set_events(self, events: List[Event]) -> None
    def set_view_range(self, start: float, end: float) -> None
    def zoom_in(self) -> None
    def zoom_out(self) -> None
    def pan(self, delta_x: float) -> None
```

---

### UnifiedList (`src/gui/widgets/unified_list.py`)

Searchable list of events and entities.

```python
class UnifiedListWidget(QWidget):
    # Signals
    item_selected = Signal(str, str)       # ID, type ("event" or "entity")
    item_double_clicked = Signal(str, str)
    
    # Methods
    def load_items(
        self,
        events: List[Event],
        entities: List[Entity]
    ) -> None
    
    def filter_by_type(self, type_filter: str) -> None
    def search(self, query: str) -> None
```

---

### WikiTextEdit (`src/gui/widgets/wiki_text_edit.py`)

Rich text editor with wiki link support.

```python
class WikiTextEdit(QTextEdit):
    # Signals
    wiki_link_clicked = Signal(str)        # Entity name
    
    # Methods
    def set_text(self, text: str) -> None
    def get_text(self) -> str
    def insert_wiki_link(self, entity_name: str) -> None
```

---

## Utility Modules

### Text Parser (`src/services/text_parser.py`)

Parse wiki links in text.

```python
class TextParser:
    @staticmethod
    def parse_wiki_links(text: str) -> List[str]
    
    @staticmethod
    def replace_wiki_links(
        text: str,
        link_fn: Callable[[str], str]
    ) -> str
```

**Example:**

```python
from src.services.text_parser import TextParser

text = "[[Gandalf]] met [[Frodo]] in [[The Shire]]."
links = TextParser.parse_wiki_links(text)
# Returns: ["Gandalf", "Frodo", "The Shire"]
```

---

### Date Parser (`src/core/date_parser.py`)

Parse natural language dates.

```python
class DateParser:
    @staticmethod
    def parse(text: str) -> Optional[float]
```

**Example:**

```python
from src.core.date_parser import DateParser

lore_date = DateParser.parse("Year 2941")
# Returns: 2941.0
```

---

## CLI Tools

The `src/cli/` module provides command-line tools.

### Available Commands

Run with: `python -m src.cli.<command>`

#### `timeline`

Display timeline in terminal.

```bash
python -m src.cli.timeline myworld.kraken
```

#### `event`

Create, update, or delete events.

```bash
python -m src.cli.event create myworld.kraken "Event Name" 100.0
python -m src.cli.event update myworld.kraken event-id --name "New Name"
python -m src.cli.event delete myworld.kraken event-id
```

#### `entity`

Create, update, or delete entities.

```bash
python -m src.cli.entity create myworld.kraken "Entity Name" person
```

#### `graph`

Export relationship graph.

```bash
python -m src.cli.graph myworld.kraken output.html
```

#### `backup`

Create database backup.

```bash
python -m src.cli.backup myworld.kraken backup.kraken
```

#### `obsidian`

Export to Obsidian vault.

```bash
python -m src.cli.obsidian myworld.kraken ~/ObsidianVault/
```

---

## Type Definitions

### Common Types

```python
from typing import Dict, List, Optional, Any, Callable

# IDs are always strings (UUIDs)
EventID = str
EntityID = str
RelationID = str

# Lore dates are floats (1.0 = 1 day)
LoreDate = float

# Attributes are flexible JSON
Attributes = Dict[str, Any]
```

---

## Additional Resources

- [Architecture Guide](ARCHITECTURE.md) - System design
- [Database Schema](DATABASE.md) - Database structure
- [Development Guide](DEVELOPMENT.md) - Setup and standards
- [Testing Guide](TESTING.md) - Testing practices

---

## Questions?

- **Issues:** https://github.com/yourusername/ProjektKraken/issues
- **Discussions:** https://github.com/yourusername/ProjektKraken/discussions
- **API Docs:** https://projektkraken.readthedocs.io
