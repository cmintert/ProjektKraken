# API Reference

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Reference documentation for key classes, services, and APIs in ProjektKraken.

---

## Table of Contents

1. [Core Models](#core-models)
2. [Commands](#commands)
3. [Services](#services)
4. [Repositories](#repositories)
5. [GUI Widgets](#gui-widgets)
6. [Utilities](#utilities)

---

## Core Models

### Event

**Location**: `src/core/events.py`

Represents a timestamped event in the world timeline.

```python
@dataclass
class Event:
    """Timeline event with precise temporal placement."""
    
    id: str
    name: str
    lore_date: float
    type: str = "generic"
    lore_duration: float = 0.0
    description: str = ""
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Event':
        """Deserialize from dictionary."""
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `to_dict()` | Convert to dictionary for serialization |
| `from_dict(data)` | Create Event from dictionary |

**Example Usage:**

```python
from src.core.events import Event

# Create event
event = Event(
    name="The Fall of Rome",
    lore_date=476.0,
    type="political",
    description="The Western Roman Empire falls."
)

# Serialize
data = event.to_dict()

# Deserialize
event2 = Event.from_dict(data)
```

---

### Entity

**Location**: `src/core/entities.py`

Represents a persistent element in the world (character, location, etc.).

```python
@dataclass
class Entity:
    """Persistent world element."""
    
    id: str
    name: str
    type: str = "generic"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Entity':
        """Deserialize from dictionary."""
```

**Entity Types:**
- `character` - People, sentient beings
- `location` - Places, regions
- `faction` - Groups, organizations
- `item` - Objects, artifacts
- `concept` - Abstract ideas

---

### Relation

**Location**: `src/core/relations.py`

Represents a directed relationship between two items.

```python
@dataclass
class Relation:
    """Directed relationship between items."""
    
    id: str
    source_id: str
    target_id: str
    rel_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Relation':
        """Deserialize from dictionary."""
```

**Common Relation Types:**
- `caused` - Causal relationship
- `involved` - Participation
- `influenced` - Indirect effect
- `located_at` - Spatial relationship
- `member_of` - Membership
- `owns` - Ownership

---

## Commands

### BaseCommand

**Location**: `src/commands/base_command.py`

Abstract base class for all commands (Command Pattern).

```python
class BaseCommand(ABC):
    """Abstract base for all commands."""
    
    def __init__(self, service: DatabaseService):
        self.service = service
        self.id = str(uuid.uuid4())
    
    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass
    
    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "id": self.id,
            "type": self.__class__.__name__
        }
    
    @classmethod
    def from_dict(cls, data: dict, service: DatabaseService):
        """Deserialize from persistence."""
        pass
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `execute()` | Perform the action |
| `undo()` | Reverse the action |
| `to_dict()` | Serialize to dictionary |
| `from_dict(data, service)` | Deserialize from dictionary |

---

### CreateEventCommand

**Location**: `src/commands/event_commands.py`

Command to create a new event.

```python
class CreateEventCommand(BaseCommand):
    """Create a new event."""
    
    def __init__(
        self,
        service: DatabaseService,
        name: str,
        lore_date: float,
        type: str = "generic",
        **kwargs
    ):
        super().__init__(service)
        self.name = name
        self.lore_date = lore_date
        self.type = type
        self.kwargs = kwargs
        self.event_id = None
    
    def execute(self) -> None:
        """Create the event."""
        repo = EventRepository(self.service)
        event = Event(
            name=self.name,
            lore_date=self.lore_date,
            type=self.type,
            **self.kwargs
        )
        repo.create(event)
        self.event_id = event.id
    
    def undo(self) -> None:
        """Delete the created event."""
        repo = EventRepository(self.service)
        repo.delete(self.event_id)
```

**Usage:**

```python
from src.commands.event_commands import CreateEventCommand

cmd = CreateEventCommand(
    service=db_service,
    name="The Battle",
    lore_date=1234.0,
    type="war"
)
cmd.execute()

# Later, undo
cmd.undo()
```

---

### AddRelationCommand

**Location**: `src/commands/relation_commands.py`

Command to add a relationship between two items.

```python
class AddRelationCommand(BaseCommand):
    """Add a relation between two items."""
    
    def __init__(
        self,
        service: DatabaseService,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict] = None
    ):
        super().__init__(service)
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.attributes = attributes or {}
        self.relation_id = None
    
    def execute(self) -> None:
        """Create the relation."""
        repo = RelationRepository(self.service)
        relation = Relation(
            source_id=self.source_id,
            target_id=self.target_id,
            rel_type=self.rel_type,
            attributes=self.attributes
        )
        repo.create(relation)
        self.relation_id = relation.id
    
    def undo(self) -> None:
        """Remove the relation."""
        repo = RelationRepository(self.service)
        repo.delete(self.relation_id)
```

---

## Services

### DatabaseService

**Location**: `src/services/db_service.py`

Low-level database interface for SQLite operations.

```python
class DatabaseService:
    """SQLite database interface."""
    
    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path)
        self._configure()
    
    def _configure(self) -> None:
        """Configure database settings."""
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
    
    def execute(
        self,
        sql: str,
        params: tuple = ()
    ) -> List[sqlite3.Row]:
        """Execute SQL query."""
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        self.connection.commit()
        return cursor.fetchall()
    
    def initialize_schema(self) -> None:
        """Create database tables."""
        # Creates all tables
        pass
    
    def close(self) -> None:
        """Close database connection."""
        self.connection.close()
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `execute(sql, params)` | Execute parameterized SQL query |
| `initialize_schema()` | Create all database tables |
| `close()` | Close database connection |

---

### HistoryService

**Location**: `src/services/history_service.py`

Manages persistent command history for undo/redo.

```python
class HistoryService:
    """Manages command history persistence."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    def record(
        self,
        cmd: BaseCommand,
        session_id: str
    ) -> None:
        """Save command to history."""
        data = cmd.to_dict()
        self.db.execute(
            "INSERT INTO command_history VALUES (?, ?, ?, ?)",
            (cmd.id, session_id, cmd.__class__.__name__, json.dumps(data))
        )
    
    def restore_session(
        self,
        session_id: str
    ) -> List[BaseCommand]:
        """Load commands from previous session."""
        rows = self.db.execute(
            "SELECT * FROM command_history WHERE session_id = ?",
            (session_id,)
        )
        return [self._deserialize(row) for row in rows]
    
    def clear_history(self, session_id: str) -> None:
        """Clear command history for session."""
        self.db.execute(
            "DELETE FROM command_history WHERE session_id = ?",
            (session_id,)
        )
```

---

## Repositories

### EventRepository

**Location**: `src/services/repositories/event_repository.py`

Data access layer for Event operations.

```python
class EventRepository:
    """Repository for Event database operations."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    def create(self, event: Event) -> Event:
        """Create new event in database."""
        sql = """
            INSERT INTO events (id, name, lore_date, type, description, attributes)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            event.id,
            event.name,
            event.lore_date,
            event.type,
            event.description,
            json.dumps(event.attributes)
        )
        self.db.execute(sql, params)
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """Retrieve event by ID."""
        sql = "SELECT * FROM events WHERE id = ?"
        rows = self.db.execute(sql, (event_id,))
        if rows:
            return Event.from_dict(dict(rows[0]))
        return None
    
    def update(self, event: Event) -> Event:
        """Update existing event."""
        sql = """
            UPDATE events
            SET name = ?, lore_date = ?, type = ?, description = ?, attributes = ?
            WHERE id = ?
        """
        params = (
            event.name,
            event.lore_date,
            event.type,
            event.description,
            json.dumps(event.attributes),
            event.id
        )
        self.db.execute(sql, params)
        return event
    
    def delete(self, event_id: str) -> bool:
        """Delete event from database."""
        sql = "DELETE FROM events WHERE id = ?"
        self.db.execute(sql, (event_id,))
        return True
    
    def list_all(self) -> List[Event]:
        """List all events."""
        sql = "SELECT * FROM events ORDER BY lore_date"
        rows = self.db.execute(sql)
        return [Event.from_dict(dict(row)) for row in rows]
    
    def find_by_date_range(
        self,
        start_date: float,
        end_date: float
    ) -> List[Event]:
        """Find events in date range."""
        sql = "SELECT * FROM events WHERE lore_date BETWEEN ? AND ?"
        rows = self.db.execute(sql, (start_date, end_date))
        return [Event.from_dict(dict(row)) for row in rows]
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `create(event)` | Create new event |
| `get(event_id)` | Retrieve event by ID |
| `update(event)` | Update existing event |
| `delete(event_id)` | Delete event |
| `list_all()` | List all events |
| `find_by_date_range(start, end)` | Find events in date range |

---

### RelationRepository

**Location**: `src/services/repositories/relation_repository.py`

Data access layer for Relation operations.

```python
class RelationRepository:
    """Repository for Relation database operations."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    def create(self, relation: Relation) -> Relation:
        """Create new relation."""
        # Implementation
        pass
    
    def get(self, relation_id: str) -> Optional[Relation]:
        """Retrieve relation by ID."""
        pass
    
    def find_by_source(self, source_id: str) -> List[Relation]:
        """Find all relations from source."""
        sql = "SELECT * FROM relations WHERE source_id = ?"
        rows = self.db.execute(sql, (source_id,))
        return [Relation.from_dict(dict(row)) for row in rows]
    
    def find_by_target(self, target_id: str) -> List[Relation]:
        """Find all relations to target."""
        sql = "SELECT * FROM relations WHERE target_id = ?"
        rows = self.db.execute(sql, (target_id,))
        return [Relation.from_dict(dict(row)) for row in rows]
    
    def delete(self, relation_id: str) -> bool:
        """Delete relation."""
        sql = "DELETE FROM relations WHERE id = ?"
        self.db.execute(sql, (relation_id,))
        return True
```

---

## GUI Widgets

### EntityEditor

**Location**: `src/gui/widgets/entity_editor.py`

Widget for editing entity properties.

```python
class EntityEditor(QWidget):
    """Widget for editing entity properties."""
    
    # Signals
    entity_updated = pyqtSignal(dict)
    relation_requested = pyqtSignal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entity = None
        self._setup_ui()
        self._connect_signals()
    
    def set_entity(self, entity: dict) -> None:
        """Display entity data."""
        self._entity = entity
        self._update_display()
    
    def get_entity(self) -> dict:
        """Get current entity data."""
        return self._entity
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        data = self._collect_form_data()
        self.entity_updated.emit(data)
```

**Signals:**

| Signal | Parameters | Description |
|--------|-----------|-------------|
| `entity_updated` | `dict` | Emitted when entity is modified |
| `relation_requested` | `str, str, str` | Emitted when relation is requested |

---

### TimelineWidget

**Location**: `src/gui/widgets/timeline/timeline_widget.py`

Interactive timeline visualization widget.

```python
class TimelineWidget(QWidget):
    """Interactive timeline visualization."""
    
    # Signals
    event_selected = pyqtSignal(str)
    date_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = []
        self._playhead = 0.0
        self._setup_ui()
    
    def set_events(self, events: List[dict]) -> None:
        """Set events to display."""
        self._events = events
        self._render()
    
    def set_playhead(self, date: float) -> None:
        """Set playhead position."""
        self._playhead = date
        self._render()
    
    def zoom_in(self) -> None:
        """Zoom in on timeline."""
        pass
    
    def zoom_out(self) -> None:
        """Zoom out on timeline."""
        pass
```

---

## Utilities

### ThemeManager

**Location**: `src/core/theme_manager.py`

Manages UI themes and styling.

```python
class ThemeManager:
    """Manages application themes."""
    
    @staticmethod
    def load_theme(theme_name: str) -> dict:
        """Load theme configuration."""
        with open("themes.json") as f:
            themes = json.load(f)
        return themes.get(theme_name, themes["default"])
    
    @staticmethod
    def apply_theme(app: QApplication, theme: dict) -> None:
        """Apply theme to application."""
        palette = QPalette()
        # Apply colors from theme
        app.setPalette(palette)
    
    @staticmethod
    def get_color(theme: dict, key: str) -> str:
        """Get color from theme."""
        return theme["colors"].get(key, "#000000")
```

---

### CalendarConverter

**Location**: `src/core/calendar.py`

Converts between float dates and calendar dates.

```python
class CalendarConverter:
    """Converts between float dates and calendar strings."""
    
    def __init__(self, calendar_config: dict):
        self.config = calendar_config
    
    def float_to_calendar(self, lore_date: float) -> str:
        """Convert float date to calendar string."""
        # Example: 450.5 -> "Year 1, Month 3, Day 15"
        pass
    
    def calendar_to_float(self, calendar_str: str) -> float:
        """Convert calendar string to float date."""
        # Example: "Year 1, Month 3, Day 15" -> 450.5
        pass
    
    def parse_natural_language(self, text: str) -> float:
        """Parse natural language date."""
        # Example: "2 weeks later" -> relative float
        pass
```

---

## Usage Examples

### Creating and Executing Commands

```python
from src.services.db_service import DatabaseService
from src.commands.event_commands import CreateEventCommand

# Initialize database
db = DatabaseService("world.kraken")
db.initialize_schema()

# Create command
cmd = CreateEventCommand(
    service=db,
    name="The Great War",
    lore_date=1914.0,
    type="war"
)

# Execute
cmd.execute()

# Get created event
from src.services.repositories.event_repository import EventRepository
repo = EventRepository(db)
event = repo.get(cmd.event_id)
print(f"Created event: {event.name}")

# Undo
cmd.undo()

# Verify deleted
event = repo.get(cmd.event_id)
assert event is None
```

### Using Repositories

```python
from src.services.repositories.entity_repository import EntityRepository
from src.core.entities import Entity

# Create repository
repo = EntityRepository(db_service)

# Create entity
entity = Entity(
    name="Gandalf",
    type="character",
    description="A wise wizard"
)
repo.create(entity)

# Retrieve entity
entity = repo.get(entity.id)

# Update entity
entity.description = "A very wise wizard"
repo.update(entity)

# List all entities
all_entities = repo.list_all()

# Delete entity
repo.delete(entity.id)
```

---

## Next Steps

- **[Testing Guide](TESTING.md)** - Learn how to test your code
- **[Contributing Guide](CONTRIBUTING.md)** - Contribute to the project
- **[Development Guide](DEVELOPMENT.md)** - Development workflow

---

**Navigation:**  
[← Testing](TESTING.md) • [Back to Index](INDEX.md) • [Contributing →](CONTRIBUTING.md)
