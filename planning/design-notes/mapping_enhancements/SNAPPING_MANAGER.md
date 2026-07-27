# Snapping Manager — Design & Usage

## Overview

The Snapping Manager provides geometry-aware snapping for the ProjektKraken
map view.  When enabled, vertices "magnetise" to nearby features during
drawing and vertex editing, making it easy to connect roads to intersections,
align borders, and create topologically consistent maps.

## Architecture

```
┌──────────────┐   snap_point()   ┌──────────────────┐
│ MapGraphics  │ ───────────────► │  SnappingManager  │
│    View      │ ◄─────────────── │                    │
│              │   SnapResult     │  scene BSP index   │
└──────────────┘                  │  vertex check      │
                                  │  edge check        │
                                  └──────────────────┘
```

### Key Components

| File | Responsibility |
|------|---------------|
| `src/gui/widgets/map/snapping_manager.py` | Core snapping logic — `SnappingManager`, `SnapResult`, `SnapType`, `point_to_segment_distance` |
| `src/gui/widgets/map/map_graphics_view.py` | Integration — calls `snap_point()` during drawing and vertex editing, renders snap indicators |
| `src/gui/widgets/map_widget.py` | UI — "Snap" toggle button in the toolbar |
| `src/app/constants.py` | Configuration — `MAP_SNAP_*` constants for radius, colours, sizes |

### Data Flow

1. **Mouse moves** in drawing or vertex editing mode.
2. `MapGraphicsView.mouseMoveEvent()` calls `SnappingManager.snap_point()`.
3. The manager converts the screen-pixel snap radius to scene units using the
   current view transform.
4. It queries `QGraphicsScene.items(search_rect)` — the scene's BSP spatial
   index finds candidates in O(log n).
5. For each candidate feature item:
   - **Vertex check**: Euclidean distance to each geometry vertex.
   - **Edge check**: `point_to_segment_distance()` for each segment.
6. Returns a `SnapResult` with the best target (vertex priority > edge).
7. The view shows a colour-coded **snap indicator** and uses the snapped
   position for the next vertex placement.

## Snap Types & Priority

| Priority | Type | Visual | Colour | Use Case |
|----------|------|--------|--------|----------|
| 1 | **Vertex** | ● circle | Yellow (`#f1c40f`) | Snap to existing feature vertex |
| 2 | **Edge** | ● circle | Blue (`#3498db`) | Snap to closest point on a segment |

Vertex snaps always take priority over edge snaps when both are within
the snap radius.

## Configuration

All constants live in `src/app/constants.py`:

```python
MAP_SNAP_RADIUS_PX = 10.0                  # Screen-pixel snap radius
MAP_SNAP_INDICATOR_VERTEX_COLOR = "#f1c40f" # Yellow
MAP_SNAP_INDICATOR_EDGE_COLOR = "#3498db"   # Blue
MAP_SNAP_INDICATOR_RADIUS = 6              # Indicator circle radius (px)
MAP_SNAP_INDICATOR_BORDER_COLOR = "#FFFFFF"
MAP_SNAP_INDICATOR_BORDER_WIDTH = 1.5
```

The snap radius automatically scales with zoom: at higher zoom levels the
radius in scene units shrinks, giving pixel-precise control.

## Usage

### Toggling Snapping

Users can toggle snapping via:
- The **Snap** button in the map toolbar (checkable, enabled by default).

Programmatically:
```python
view.snapping_enabled = False  # disable
view.snapping_enabled = True   # enable
```

### During Drawing Mode

When drawing a path or region, the snap indicator appears as the cursor
approaches a nearby feature.  Clicking places the vertex at the snapped
position.  The rubber-band preview also tracks the snap target.

### During Vertex Editing

When dragging a vertex handle, the SnappingManager checks for cross-feature
snap targets first (other paths/regions).  If none are found, the legacy
same-feature vertex snap is used as a fallback.

### Excluding Items

The `exclude_items` parameter prevents snapping to the feature being
edited.  This is automatically handled — the current editing feature and
its handles are excluded.

## Geometry Math

### Point-to-Segment Distance

The `point_to_segment_distance(P, A, B)` function implements the standard
vector projection algorithm:

1. Compute vector AB and its squared length.
2. Project AP onto AB: `t = dot(AP, AB) / |AB|²`.
3. Clamp `t` to `[0, 1]` (restricts to finite segment).
4. Compute closest point: `C = A + t × AB`.
5. Return `(|PC|, C)`.

This handles degenerate segments (A = B) and endpoints gracefully.

## Testing

Run the snapping tests:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/unit/test_snapping_manager.py -v
```

The test suite includes 25 tests covering:
- Point-to-segment geometry (7 tests)
- SnapResult dataclass (2 tests)
- SnappingManager vertex/edge/priority/radius/zoom/exclude (10 tests)
- Snap indicator show/hide/colours/cleanup (6 tests)
