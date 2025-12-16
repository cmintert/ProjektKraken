# Map System Usage Examples

This document provides practical examples of using the ProjektKraken map management system.

## Table of Contents

1. [Creating a Map](#creating-a-map)
2. [Importing Map Images](#importing-map-images)
3. [Adding Markers](#adding-markers)
4. [Placing Objects on Multiple Maps](#placing-objects-on-multiple-maps)
5. [Calculating Distances](#calculating-distances)
6. [Calculating Areas](#calculating-areas)
7. [Updating Marker Positions](#updating-marker-positions)
8. [Deleting Maps and Markers](#deleting-maps-and-markers)
9. [Working with Commands (Undo/Redo)](#working-with-commands-undoredo)

## Creating a Map

```python
from src.core.maps import GameMap
from src.services.db_service import DatabaseService

# Initialize database
db_service = DatabaseService("path/to/world.kraken")
db_service.connect()

# Create a map
world_map = GameMap(
    name="World Map",
    image_filename="assets/maps/world.png",
    real_width=10000.0,      # 10,000 km wide
    distance_unit="km",
    reference_width=2048,     # Original image width in pixels
    reference_height=1024     # Original image height in pixels
)

# Optional: Add metadata
world_map.attributes["checksum"] = "abc123..."
world_map.attributes["notes"] = "Main continent overview"

# Save to database
db_service.insert_map(world_map)
```

## Importing Map Images

```python
from src.core.asset_manager import AssetManager

# Initialize asset manager with project root
asset_manager = AssetManager("/path/to/project")

# Import an image file
source_path = "/path/to/downloads/world_map.png"
relative_path, checksum = asset_manager.import_image(
    source_path,
    filename="world.png"  # Optional custom name
)

# Use the relative path when creating the map
world_map = GameMap(
    name="World Map",
    image_filename=relative_path,  # "assets/maps/world.png"
    real_width=10000.0,
    distance_unit="km",
    reference_width=2048,
    reference_height=1024
)
world_map.attributes["checksum"] = checksum

db_service.insert_map(world_map)
```

## Adding Markers

```python
from src.core.maps import MapMarker
from src.core.entities import Entity

# Create an entity
capital = Entity(name="Capital City", type="location")
capital.description = "The seat of the empire"
db_service.insert_entity(capital)

# Place the entity on a map
marker = MapMarker(
    map_id=world_map.id,
    object_id=capital.id,
    object_type="entity",
    x=0.45,  # 45% from left
    y=0.62   # 62% from top
)

# Optional: Add custom attributes
marker.attributes["icon"] = "castle"
marker.attributes["label"] = "Imperial Capital"
marker.attributes["visible"] = True

db_service.insert_marker(marker)
```

## Placing Objects on Multiple Maps

```python
# Create different scale maps
region_map = GameMap(
    name="Central Region",
    image_filename="assets/maps/region.png",
    real_width=500.0,  # 500 km
    distance_unit="km",
    reference_width=1000,
    reference_height=1000
)

city_map = GameMap(
    name="Capital Detail",
    image_filename="assets/maps/capital.png",
    real_width=10.0,  # 10 km
    distance_unit="km",
    reference_width=1000,
    reference_height=1000
)

db_service.insert_map(region_map)
db_service.insert_map(city_map)

# Place the same entity on all three maps
world_marker = MapMarker(
    map_id=world_map.id,
    object_id=capital.id,
    object_type="entity",
    x=0.45, y=0.62
)

region_marker = MapMarker(
    map_id=region_map.id,
    object_id=capital.id,
    object_type="entity",
    x=0.32, y=0.78
)

city_marker = MapMarker(
    map_id=city_map.id,
    object_id=capital.id,
    object_type="entity",
    x=0.5, y=0.5  # Center of detail map
)

db_service.insert_marker(world_marker)
db_service.insert_marker(region_marker)
db_service.insert_marker(city_marker)

# Query all maps where capital appears
capital_markers = db_service.get_markers_for_object(capital.id, "entity")
print(f"Capital appears on {len(capital_markers)} maps")
```

## Calculating Distances

```python
from src.core.map_math import calculate_distance

# Create two markers
port = Entity(name="Port Town", type="location")
db_service.insert_entity(port)

port_marker = MapMarker(
    map_id=world_map.id,
    object_id=port.id,
    object_type="entity",
    x=0.7, y=0.3
)
db_service.insert_marker(port_marker)

# Calculate distance between capital and port
distance = calculate_distance(
    marker1=world_marker,
    marker2=port_marker,
    game_map=world_map
)

print(f"Distance: {distance:.1f} {world_map.distance_unit}")
# Output: Distance: 3605.6 km
```

## Calculating Areas

```python
from src.core.map_math import calculate_area

# Define a kingdom boundary with markers
kingdom_markers = []
boundary_points = [
    (0.2, 0.3),  # Northwest
    (0.6, 0.2),  # Northeast
    (0.7, 0.6),  # Southeast
    (0.3, 0.7),  # Southwest
]

for i, (x, y) in enumerate(boundary_points):
    # Create a boundary marker entity
    boundary = Entity(name=f"Boundary Point {i+1}", type="location")
    db_service.insert_entity(boundary)
    
    marker = MapMarker(
        map_id=world_map.id,
        object_id=boundary.id,
        object_type="entity",
        x=x, y=y
    )
    db_service.insert_marker(marker)
    kingdom_markers.append(marker)

# Calculate area of the kingdom
area = calculate_area(kingdom_markers, world_map)
print(f"Kingdom area: {area:.0f} {world_map.distance_unit}²")
# Output: Kingdom area: 18000000 km²
```

## Updating Marker Positions

```python
# Move the port marker
port_marker.x = 0.75
port_marker.y = 0.35

db_service.insert_marker(port_marker)  # Upsert updates existing marker

# Or retrieve, modify, and save
existing_marker = db_service.get_marker(port_marker.id)
existing_marker.x = 0.8
existing_marker.y = 0.4
existing_marker.attributes["label"] = "Major Port"
db_service.insert_marker(existing_marker)
```

## Deleting Maps and Markers

```python
# Delete a single marker
db_service.delete_marker(port_marker.id)

# Delete all markers for an object
db_service.delete_markers_for_object(capital.id, "entity")

# Delete a map (cascades to all its markers)
db_service.delete_map(city_map.id)
```

## Working with Commands (Undo/Redo)

```python
from src.commands.map_commands import (
    CreateMapCommand,
    AddMarkerCommand,
    UpdateMarkerCommand,
    DeleteMapCommand
)

# Create map with command pattern
map_data = {
    "name": "Test Map",
    "image_filename": "assets/maps/test.png",
    "real_width": 100.0,
    "distance_unit": "km",
    "reference_width": 1000,
    "reference_height": 1000
}

create_cmd = CreateMapCommand(map_data)
result = create_cmd.execute(db_service)

if result.success:
    print(f"Map created with ID: {result.data['id']}")
    
    # Later, undo the creation
    create_cmd.undo(db_service)
    print("Map creation undone")

# Add marker with command
marker_data = {
    "map_id": world_map.id,
    "object_id": capital.id,
    "object_type": "entity",
    "x": 0.5,
    "y": 0.5
}

add_marker_cmd = AddMarkerCommand(marker_data)
result = add_marker_cmd.execute(db_service)

if result.success:
    # Move marker with command
    update_cmd = UpdateMarkerCommand(
        marker_id=add_marker_cmd.marker.id,
        update_data={"x": 0.6, "y": 0.4}
    )
    result = update_cmd.execute(db_service)
    
    # Undo the move
    update_cmd.undo(db_service)
    print("Marker position reverted")

# Delete with undo support
delete_cmd = DeleteMapCommand(world_map.id)
result = delete_cmd.execute(db_service)

# Restore the deleted map and all its markers
delete_cmd.undo(db_service)
print("Map and markers restored")
```

## Converting Between Pixel and Normalized Coordinates

```python
from src.core.map_math import pixel_to_normalized, normalized_to_pixel

# User clicks at pixel (1024, 512) on a 2048x1024 image
click_x, click_y = 1024, 512
image_width, image_height = 2048, 1024

# Convert to normalized coordinates for storage
norm_x, norm_y = pixel_to_normalized(
    click_x, click_y,
    image_width, image_height
)
print(f"Normalized: ({norm_x}, {norm_y})")  # (0.5, 0.5)

# Convert back for rendering
pixel_x, pixel_y = normalized_to_pixel(
    norm_x, norm_y,
    image_width, image_height
)
print(f"Pixel: ({pixel_x}, {pixel_y})")  # (1024.0, 512.0)
```

## Detecting Image Changes

```python
from src.core.map_math import detect_aspect_ratio_change

# Check if new image has same aspect ratio
old_width, old_height = 1000, 1000
new_width, new_height = 2000, 2000

changed = detect_aspect_ratio_change(
    old_width, old_height,
    new_width, new_height,
    tolerance=0.01  # 1% tolerance
)

if changed:
    print("Aspect ratio changed - migration needed")
else:
    print("Same aspect ratio - markers remain valid")
```

## Best Practices

1. **Always use normalized coordinates**: Never store pixel coordinates in the database.

2. **Store checksums**: Keep image checksums in map.attributes to detect file changes.

3. **Clean up markers**: When deleting entities/events, remember to clean up their markers:
   ```python
   db_service.delete_entity(entity_id)
   db_service.delete_markers_for_object(entity_id, "entity")
   ```

4. **Use commands for UI actions**: Commands support undo/redo which improves UX.

5. **Validate coordinates**: The MapMarker dataclass validates coordinates in __post_init__.

6. **Handle aspect ratio changes**: Use detect_aspect_ratio_change when replacing images.

7. **Project-relative paths**: Always use relative paths like "assets/maps/world.png".

8. **Index queries**: The database has indexes on (map_id) and (object_id, object_type).
