---
**Project:** ProjektKraken  
**Document:** Map Widget - Polygon & Line Feature Readiness Assessment  
**Date:** 2026-01-10  
**Status:** Technical Analysis
---

# Map Widget: Polygon & Line Feature Readiness Assessment

## Executive Summary

**Current Status:** The map widget is **production-ready for point-based markers** but **NOT ready for polygon and line features**. The architecture is sound but requires additional foundational components to support vector geometry.

**Recommendation:** Implement polygon/line support as a **new feature** in a future release. The current architecture provides a solid foundation, but requires:
1. New data models for polygon/line geometry
2. Extended coordinate system with geometry operations
3. New renderer classes for vector shapes
4. Database schema extensions
5. UI controls for polygon/line creation and editing

---

## 1. Current Architecture Assessment

### 1.1 What Works Well (Point Markers)

The map widget successfully handles:

- ✅ **Point-based markers** with normalized coordinates [0.0, 1.0]
- ✅ **Coordinate transformations** between normalized and scene space
- ✅ **Drag and drop** positioning with real-time updates
- ✅ **SVG icon rendering** with color customization
- ✅ **Trajectory visualization** (lines connecting keyframes)
- ✅ **Scale bar** with metric/imperial units
- ✅ **Context menus** for marker operations
- ✅ **Zoom and pan** with OpenGL acceleration

### 1.2 Current Limitations for Polygons/Lines

The following components are **marker-specific** and do not generalize to polygons/lines:

1. **Data Model** (`src/core/map.py`):
   - No `Polygon` or `LineString` classes
   - Markers only store single (x, y) points
   - No support for vertex arrays or geometry types

2. **Database Schema**:
   - `markers` table only stores `x, y` as single REAL columns
   - No geometry storage (e.g., WKT/WKB format or JSON arrays)

3. **Coordinate System** (`src/gui/widgets/map/coordinate_system.py`):
   - Only provides `to_scene()` and `to_normalized()` for single points
   - No methods for transforming polygon vertex arrays
   - No geometry operations (containment, intersection, buffering)

4. **Rendering**:
   - `MarkerItem` is designed for point symbols (SVG icons, circles)
   - No `PolygonItem` or `LineStringItem` classes
   - No fill/stroke styling for polygons

5. **User Interaction**:
   - No UI for drawing polygons (click to add vertices)
   - No line drawing mode
   - No vertex editing (move, add, remove vertices)
   - No snapping or geometry constraints

---

## 2. Technical Requirements for Polygon/Line Support

### 2.1 Data Model Extensions

**New Classes Needed** (`src/core/map.py`):

```python
from dataclasses import dataclass, field
from typing import List, Tuple, Literal

@dataclass
class GeometryFeature:
    """Base class for geometric features on a map."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    geometry_type: Literal["point", "linestring", "polygon"] = "point"
    style: Dict[str, Any] = field(default_factory=dict)  # Fill, stroke, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)


@dataclass
class PointFeature(GeometryFeature):
    """A point feature with a single coordinate."""
    x: float = 0.0  # Normalized [0.0, 1.0]
    y: float = 0.0  # Normalized [0.0, 1.0]
    geometry_type: Literal["point"] = "point"


@dataclass
class LineStringFeature(GeometryFeature):
    """A line feature with ordered vertices."""
    vertices: List[Tuple[float, float]] = field(default_factory=list)
    geometry_type: Literal["linestring"] = "linestring"


@dataclass
class PolygonFeature(GeometryFeature):
    """A polygon feature with exterior ring and optional holes."""
    exterior_ring: List[Tuple[float, float]] = field(default_factory=list)
    interior_rings: List[List[Tuple[float, float]]] = field(default_factory=list)
    geometry_type: Literal["polygon"] = "polygon"
```

### 2.2 Database Schema Extensions

**New Table: `map_features`**

```sql
CREATE TABLE map_features (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    name TEXT NOT NULL,
    geometry_type TEXT NOT NULL CHECK(geometry_type IN ('point', 'linestring', 'polygon')),
    geometry TEXT NOT NULL,  -- JSON array: [[x1,y1], [x2,y2], ...] normalized coords
    style TEXT,              -- JSON: {"fill": "#FF0000", "stroke": "#000", "strokeWidth": 2}
    attributes TEXT,         -- JSON: flexible metadata
    created_at REAL NOT NULL,
    modified_at REAL NOT NULL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
);
```

**Migration Strategy:**
- Keep existing `markers` table for backward compatibility
- Add `map_features` table alongside
- Eventually migrate markers to features (or keep both)

### 2.3 Coordinate System Extensions

**New Methods** (`src/gui/widgets/map/coordinate_system.py`):

```python
def to_scene_array(self, vertices: List[Tuple[float, float]]) -> List[QPointF]:
    """
    Converts an array of normalized coordinates to scene coordinates.
    
    Args:
        vertices: List of (x, y) normalized tuples.
    
    Returns:
        List[QPointF]: Points in scene coordinates.
    """
    return [self.to_scene(x, y) for x, y in vertices]


def to_normalized_array(self, scene_points: List[QPointF]) -> List[Tuple[float, float]]:
    """
    Converts an array of scene coordinates to normalized coordinates.
    
    Args:
        scene_points: List of QPointF in scene space.
    
    Returns:
        List[Tuple[float, float]]: Normalized (x, y) tuples.
    """
    return [self.to_normalized(p) for p in scene_points]


def polygon_contains_point(self, polygon: List[Tuple[float, float]], point: Tuple[float, float]) -> bool:
    """
    Tests if a point is inside a polygon using ray casting algorithm.
    
    Args:
        polygon: List of (x, y) vertices (closed ring).
        point: (x, y) tuple to test.
    
    Returns:
        bool: True if point is inside polygon.
    """
    # Ray casting implementation
    pass
```

### 2.4 Rendering Components

**New Classes** (`src/gui/widgets/map/`):

#### `polygon_item.py`

```python
class PolygonItem(QGraphicsPolygonItem):
    """
    A draggable/editable polygon feature on the map.
    
    Supports:
    - Fill and stroke styling
    - Vertex editing (move, add, remove)
    - Selection and context menu
    - Serialization to/from normalized coordinates
    """
    
    def __init__(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]],
        style: Dict[str, Any],
        coord_system: MapCoordinateSystem
    ) -> None:
        # Implementation
        pass
```

#### `linestring_item.py`

```python
class LineStringItem(QGraphicsPathItem):
    """
    A draggable/editable line string feature on the map.
    
    Supports:
    - Stroke styling (color, width, dash pattern)
    - Vertex editing
    - Arrow heads for directionality
    - Serialization
    """
    
    def __init__(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]],
        style: Dict[str, Any],
        coord_system: MapCoordinateSystem
    ) -> None:
        # Implementation
        pass
```

#### `vertex_handle.py`

```python
class VertexHandle(QGraphicsEllipseItem):
    """
    A draggable control point for polygon/line editing.
    
    Features:
    - Hover effects
    - Drag to move vertex
    - Context menu to delete vertex
    - Signals for geometry changes
    """
    
    vertex_moved = Signal(int, float, float)  # index, new_x, new_y
    vertex_deleted = Signal(int)  # index
```

### 2.5 User Interface Extensions

**MapGraphicsView Additions:**

```python
class MapGraphicsView(QGraphicsView):
    # Existing signals...
    
    # New signals for polygon/line features
    polygon_created = Signal(str, list)  # feature_id, vertices
    line_created = Signal(str, list)     # feature_id, vertices
    feature_edited = Signal(str, list)   # feature_id, new_vertices
    feature_deleted = Signal(str)        # feature_id
    
    # New modes
    def set_drawing_mode(self, mode: Literal["marker", "line", "polygon"]) -> None:
        """Enable drawing mode for different geometry types."""
        pass
    
    def add_polygon(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]],
        style: Dict[str, Any]
    ) -> None:
        """Add a polygon feature to the map."""
        pass
    
    def add_linestring(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]],
        style: Dict[str, Any]
    ) -> None:
        """Add a line string feature to the map."""
        pass
```

**Toolbar Additions:**

- "Draw Line" button (toggle drawing mode)
- "Draw Polygon" button (toggle drawing mode)
- "Edit Feature" button (enable vertex editing)
- Style picker (color, line width, fill opacity)

### 2.6 Service Layer

**New Repository** (`src/services/repositories/map_feature_repository.py`):

```python
class MapFeatureRepository:
    """Repository for geometric map features (polygons, lines)."""
    
    def create_feature(self, feature: GeometryFeature) -> None:
        """Persist a new feature to the database."""
        pass
    
    def get_features_for_map(self, map_id: str) -> List[GeometryFeature]:
        """Load all features for a given map."""
        pass
    
    def update_feature_geometry(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]]
    ) -> None:
        """Update feature geometry after editing."""
        pass
    
    def delete_feature(self, feature_id: str) -> None:
        """Delete a feature from the database."""
        pass
```

### 2.7 Command Pattern

**New Commands** (`src/commands/map_feature_commands.py`):

```python
class CreatePolygonCommand(BaseCommand):
    """Command to create a polygon feature."""
    pass

class CreateLineStringCommand(BaseCommand):
    """Command to create a line string feature."""
    pass

class EditFeatureGeometryCommand(BaseCommand):
    """Command to edit feature vertices (supports undo/redo)."""
    pass

class DeleteFeatureCommand(BaseCommand):
    """Command to delete a feature."""
    pass
```

---

## 3. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Define data models (`GeometryFeature`, `PolygonFeature`, `LineStringFeature`)
- [ ] Add `map_features` database table and migration script
- [ ] Extend `MapCoordinateSystem` with array transformations
- [ ] Write unit tests for data models and coordinate transformations

### Phase 2: Rendering (Week 3-4)
- [ ] Implement `PolygonItem` class with basic rendering
- [ ] Implement `LineStringItem` class with basic rendering
- [ ] Implement `VertexHandle` for interactive editing
- [ ] Add selection and hover effects
- [ ] Write integration tests with `MapGraphicsView`

### Phase 3: User Interaction (Week 5-6)
- [ ] Add drawing modes to `MapGraphicsView` (line/polygon)
- [ ] Implement click-to-add-vertex workflow
- [ ] Add context menus for features
- [ ] Implement vertex editing (drag, delete, add)
- [ ] Add style picker UI controls

### Phase 4: Persistence & Commands (Week 7-8)
- [ ] Implement `MapFeatureRepository`
- [ ] Create command classes for CRUD operations
- [ ] Integrate with undo/redo stack
- [ ] Add CLI commands for feature management
- [ ] Write end-to-end tests

### Phase 5: Polish (Week 9-10)
- [ ] Add snapping (vertex-to-vertex, grid snapping)
- [ ] Implement geometry validation (self-intersecting polygons)
- [ ] Add keyboard shortcuts for drawing modes
- [ ] Write comprehensive documentation
- [ ] User acceptance testing

---

## 4. Alternatives & Trade-offs

### Option A: Shapely Integration (Recommended)

**Pros:**
- Mature geometry library (GEOS-based)
- Robust algorithms (intersection, buffer, simplification)
- Well-tested and widely used

**Cons:**
- Additional dependency (~10MB binary)
- Overhead for simple use cases

**Example:**
```python
from shapely.geometry import Polygon, LineString

# Define polygon in normalized coordinates
polygon = Polygon([(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)])
print(polygon.area)  # Calculate area
print(polygon.contains(Point(0.5, 0.5)))  # Point-in-polygon test
```

### Option B: Pure Qt/PySide6 (Current Approach)

**Pros:**
- No external dependencies
- Tight integration with Qt Graphics Framework
- Lightweight

**Cons:**
- Manual implementation of geometry algorithms
- Reinventing the wheel
- More potential for bugs

### Option C: GeoJSON Storage

Store geometry in GeoJSON format instead of custom JSON arrays:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[0.1, 0.1], [0.9, 0.1], [0.5, 0.9], [0.1, 0.1]]]
  },
  "properties": {
    "name": "Region Alpha",
    "fill": "#FF0000"
  }
}
```

**Pros:**
- Industry standard format
- Interoperable with GIS tools
- Human-readable

**Cons:**
- Slightly more complex parsing
- Overkill for simple use cases

---

## 5. Testing Requirements

### Unit Tests

- `test_polygon_feature.py` - Test data model serialization
- `test_linestring_feature.py` - Test data model serialization
- `test_coordinate_system_arrays.py` - Test array transformations
- `test_polygon_item.py` - Test rendering and interaction
- `test_vertex_handle.py` - Test vertex editing

### Integration Tests

- `test_map_polygon_workflow.py` - End-to-end polygon creation
- `test_map_line_workflow.py` - End-to-end line creation
- `test_feature_persistence.py` - Database CRUD operations
- `test_feature_undo_redo.py` - Command pattern undo/redo

### Performance Tests

- Rendering 1000+ polygons without lag
- Smooth vertex dragging with 50+ vertices
- Fast map loading with complex geometries

---

## 6. Documentation Requirements

### User Documentation

- Tutorial: "Drawing Regions on Maps"
- Tutorial: "Creating Travel Routes with Lines"
- Reference: Map Feature Properties and Styling

### Developer Documentation

- Architecture: Map Feature System Design
- API Reference: `MapFeatureRepository`
- API Reference: `PolygonItem`, `LineStringItem`
- Contributing Guide: Adding New Geometry Types

---

## 7. Conclusion

**The map widget is production-ready for its current scope (point markers)** but requires significant architectural extensions to support polygons and lines. The existing codebase is well-structured and maintainable, making it a solid foundation for future enhancements.

**Estimated Effort:**
- **Full polygon/line support:** 8-10 weeks (1 developer)
- **Minimal viable implementation:** 4-5 weeks (basic rendering, no editing)

**Priority:**
- Low (if only markers are needed for MVP)
- High (if world maps with regions/borders are essential)

**Next Steps:**
1. Validate use cases with stakeholders (Do users need regions? Travel routes?)
2. Prototype basic polygon rendering (1-week spike)
3. Review with team before committing to full implementation
4. Consider using Shapely to accelerate development

---

**Document Status:** Ready for Review  
**Author:** GitHub Copilot  
**Reviewers:** Project Maintainers
