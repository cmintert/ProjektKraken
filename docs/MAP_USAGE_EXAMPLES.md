---
**Project:** ProjektKraken  
**Document:** Map System Usage Guide  
**Last Updated:** 2026-01-01  
**Commit:** `199b38b`  
---

# Map System Usage Guide

## Overview

The Map System in ProjektKraken allows you to visualize entities and events on custom map images. Maps use a normalized coordinate system [0.0, 1.0] to position markers independently of image size.

## Core Concepts

### Maps

A **Map** represents an image file that can display markers. Maps are stored in the database with metadata like name and description.

```python
from src.core.map import Map

# Create a map
my_map = Map(
    name="World Map",
    image_path="/path/to/world_map.png",
    description="Main world geography"
)
```

### Markers

A **Marker** is a point on a map that links to an entity or event. Markers store their position using normalized coordinates [0.0, 1.0]:

- `x=0.0` is the left edge, `x=1.0` is the right edge
- `y=0.0` is the top edge, `y=1.0` is the bottom edge

```python
from src.core.marker import Marker

# Create a marker at the center of the map
marker = Marker(
    map_id=my_map.id,
    object_id=entity.id,
    object_type="entity",
    x=0.5,  # Horizontal center
    y=0.5,  # Vertical center
    label="Capital City"
)
```

### Normalized Coordinates

Normalized coordinates allow markers to maintain their relative position even if:
- The map image is displayed at different sizes
- The map is zoomed or resized in the UI
- The map image file is replaced with a different resolution

Example positions:
- `(0.0, 0.0)` = Top-left corner
- `(1.0, 0.0)` = Top-right corner
- `(0.0, 1.0)` = Bottom-left corner
- `(1.0, 1.0)` = Bottom-right corner
- `(0.5, 0.5)` = Center

## Database Operations

### Creating Maps and Markers

```python
from src.services.db_service import DatabaseService
from src.core.map import Map
from src.core.marker import Marker

# Initialize database
db = DatabaseService("world.kraken")
db.connect()

# Create a map
world_map = Map(name="World Map", image_path="/maps/world.png")
db.insert_map(world_map)

# Create a marker for an entity
castle_marker = Marker(
    map_id=world_map.id,
    object_id="entity-castle-123",
    object_type="entity",
    x=0.35,
    y=0.42,
    label="Dragon's Keep"
)
marker_id = db.insert_marker(castle_marker)
```

### Querying Markers

```python
# Get all markers on a specific map
markers = db.get_markers_for_map(world_map.id)

# Get all markers for a specific entity (across all maps)
entity_markers = db.get_markers_for_object("entity-castle-123", "entity")

# Get a specific marker by its composite key
marker = db.get_marker_by_composite(
    map_id=world_map.id,
    object_id="entity-castle-123",
    object_type="entity"
)
```

### Updating Marker Position

```python
# Update marker position
castle_marker.x = 0.40
castle_marker.y = 0.45
db.insert_marker(castle_marker)  # Upsert
```

## Upsert Behavior and ID Semantics

⚠️ **Important:** The `insert_marker` method upserts on the composite key `(map_id, object_id, object_type)`.

### What This Means

When you call `insert_marker`, the database checks if a marker already exists for:
- The same map (`map_id`)
- The same object (`object_id`)
- The same object type (`object_type`)

If a match is found:
- The existing row is **updated** with the new values
- The **existing row's ID is retained**
- The returned ID may differ from `marker.id`

### Example: Upsert Behavior

```python
# First insert
marker1 = Marker(
    map_id="map-123",
    object_id="entity-456",
    object_type="entity",
    x=0.3,
    y=0.4
)
id1 = db.insert_marker(marker1)  # Returns "marker-abc"

# Second insert with same composite key but different ID
marker2 = Marker(
    map_id="map-123",      # Same map
    object_id="entity-456", # Same object
    object_type="entity",   # Same type
    x=0.8,                  # Different position
    y=0.9
)
id2 = db.insert_marker(marker2)  # Returns "marker-abc" (same as id1!)

# Only one marker exists in the database
# Its position was updated to (0.8, 0.9)
# Its ID remains "marker-abc"
```

### Retrieving the Canonical Marker

After an upsert, use `get_marker_by_composite` to retrieve the actual marker with its correct ID:

```python
# Insert (might be upsert)
new_marker = Marker(
    map_id=map_id,
    object_id=entity_id,
    object_type="entity",
    x=0.5,
    y=0.5
)
returned_id = db.insert_marker(new_marker)

# Get the canonical marker
canonical_marker = db.get_marker_by_composite(map_id, entity_id, "entity")
print(f"Actual marker ID: {canonical_marker.id}")  # Use this ID going forward
```

## Using Commands

Commands provide undo/redo support for map operations.

### Creating a Map

```python
from src.commands.map_commands import CreateMapCommand

cmd = CreateMapCommand({
    "name": "Dungeon Level 1",
    "image_path": "/maps/dungeon1.png",
    "description": "First level of the ancient dungeon"
})
result = cmd.execute(db)

if result.success:
    map_id = result.data["id"]
    print(f"Created map: {map_id}")

# Undo if needed
cmd.undo(db)
```

### Creating a Marker

```python
from src.commands.map_commands import CreateMarkerCommand

cmd = CreateMarkerCommand({
    "map_id": map_id,
    "object_id": entity_id,
    "object_type": "entity",
    "x": 0.25,
    "y": 0.75,
    "label": "Boss Room"
})
result = cmd.execute(db)

if result.success:
    # Note: returned ID may differ due to upsert behavior
    actual_marker_id = result.data["id"]
```

### Updating a Marker Position

```python
from src.commands.map_commands import UpdateMarkerCommand

cmd = UpdateMarkerCommand(
    marker_id=marker_id,
    update_data={"x": 0.6, "y": 0.7}
)
result = cmd.execute(db)

# Undo to restore previous position
cmd.undo(db)
```

## Using the MapWidget

The `MapWidget` provides an interactive UI for viewing and editing markers.

### Basic Setup

```python
from PySide6.QtWidgets import QApplication
from src.gui.widgets.map_widget import MapWidget

app = QApplication([])
widget = MapWidget()

# Load a map image
widget.load_map("/path/to/map.png")

# Add markers
widget.add_marker("marker1", "entity", 0.3, 0.4)
widget.add_marker("marker2", "event", 0.7, 0.8)

widget.show()
app.exec()
```

### Handling Marker Drag Events

The `MapWidget` emits a `marker_position_changed` signal when a user drags a marker:

```python
from src.commands.map_commands import UpdateMarkerCommand

def on_marker_moved(marker_id, x, y):
    """
    Called when user drags a marker to a new position.
    
    Args:
        marker_id: ID of the moved marker
        x: New normalized X coordinate [0.0, 1.0]
        y: New normalized Y coordinate [0.0, 1.0]
    """
    # Create command to persist the change
    cmd = UpdateMarkerCommand(
        marker_id=marker_id,
        update_data={"x": x, "y": y}
    )
    result = cmd.execute(db_service)
    
    if result.success:
        print(f"Marker {marker_id} moved to ({x:.3f}, {y:.3f})")

# Connect signal
widget.marker_position_changed.connect(on_marker_moved)
```

### Complete Integration Example

```python
from PySide6.QtWidgets import QMainWindow, QApplication
from src.gui.widgets.map_widget import MapWidget
from src.services.db_service import DatabaseService
from src.commands.map_commands import CreateMapCommand, CreateMarkerCommand, UpdateMarkerCommand
from src.core.entities import Entity

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseService("world.kraken")
        self.db.connect()
        
        # Setup UI
        self.map_widget = MapWidget()
        self.setCentralWidget(self.map_widget)
        
        # Connect signals
        self.map_widget.marker_position_changed.connect(self._on_marker_moved)
        
        # Load map
        self._load_map()
    
    def _load_map(self):
        # Create or load a map
        cmd = CreateMapCommand({
            "name": "World Map",
            "image_path": "/maps/world.png"
        })
        result = cmd.execute(self.db)
        
        if result.success:
            self.current_map_id = result.data["id"]
            self.map_widget.load_map("/maps/world.png")
            self._load_markers()
    
    def _load_markers(self):
        # Load existing markers from database
        markers = self.db.get_markers_for_map(self.current_map_id)
        
        for marker in markers:
            self.map_widget.add_marker(
                marker.id,
                marker.object_type,
                marker.x,
                marker.y
            )
    
    def _on_marker_moved(self, marker_id, x, y):
        # Persist marker position change
        cmd = UpdateMarkerCommand(
            marker_id=marker_id,
            update_data={"x": x, "y": y}
        )
        cmd.execute(self.db)
    
    def add_entity_marker(self, entity_id):
        # Add a marker for an entity at center of map
        cmd = CreateMarkerCommand({
            "map_id": self.current_map_id,
            "object_id": entity_id,
            "object_type": "entity",
            "x": 0.5,
            "y": 0.5,
            "label": "New Location"
        })
        result = cmd.execute(self.db)
        
        if result.success:
            actual_id = result.data["id"]
            
            # Add to widget
            self.map_widget.add_marker(actual_id, "entity", 0.5, 0.5)

# Run application
app = QApplication([])
window = MapWindow()
window.show()
app.exec()
```

## Best Practices

### 1. Always Use get_marker_by_composite After Upsert

```python
# ❌ Don't assume the marker ID you created is the one in the database
marker = Marker(map_id=m_id, object_id=e_id, object_type="entity", x=0.5, y=0.5)
db.insert_marker(marker)
# marker.id might not match what's in the database!

# ✅ Retrieve the canonical marker after insert
returned_id = db.insert_marker(marker)
canonical = db.get_marker_by_composite(m_id, e_id, "entity")
# Use canonical.id for future operations
```

### 2. Clamp Coordinates to [0.0, 1.0]

```python
def clamp(value, min_val=0.0, max_val=1.0):
    return max(min_val, min(max_val, value))

marker.x = clamp(user_input_x)
marker.y = clamp(user_input_y)
```

### 3. Use Commands for Undo/Redo Support

```python
# ❌ Don't modify database directly in UI code
db.insert_marker(marker)  # No undo support

# ✅ Use commands for user actions
cmd = CreateMarkerCommand(marker_data)
cmd.execute(db)
# Can call cmd.undo(db) later
```

### 4. Keep UI "Dumb"

The `MapWidget` should only emit signals, not persist data:

```python
# ❌ Don't put database code in widget
class MapWidget:
    def on_marker_moved(self, marker_id, x, y):
        self.db.update_marker(marker_id, x, y)  # BAD!

# ✅ Emit signal and let app layer handle persistence
class MapWidget:
    marker_position_changed = Signal(str, float, float)
    
    def on_marker_moved(self, marker_id, x, y):
        self.marker_position_changed.emit(marker_id, x, y)  # GOOD!
```

## Troubleshooting

### Markers Don't Appear on Map

- Ensure the map image loaded successfully: `widget.load_map()` returns `True`
- Check that markers have valid normalized coordinates [0.0, 1.0]
- Verify markers were added after loading the map

### Marker IDs Don't Match

This is expected due to upsert behavior. Use `get_marker_by_composite()` to retrieve the actual marker ID.

### Dragging Doesn't Emit Signals

- Ensure the marker has `ItemIsMovable` and `ItemSendsGeometryChanges` flags
- Connect to `marker_position_changed` signal before loading markers
- Check that the `pixmap_item` exists (map loaded successfully)

## Related Documentation

- [Database Best Practices](DATABASE.md)
- [Command Pattern](../src/commands/base_command.py)
- [QGraphicsView Documentation](https://doc.qt.io/qtforpython/PySide6/QtWidgets/QGraphicsView.html)
