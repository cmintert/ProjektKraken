# ProjektKraken: Temporal Map Markers
## Architectural Specification and Implementation Strategy

## 1. Executive Summary: The Fourth Dimension in Digital Cartography
The visualization of geospatial data has traditionally been bound by the constraints of static representation—a snapshot of a world frozen in a single moment. However, the narrative requirements of ProjektKraken, specifically in the domains of storytelling, world-building, and historical simulation, demand a fundamental paradigm shift. The "Temporal Map Markers" initiative represents the critical evolution from static 2D maps to dynamic 4D visualizations. This report provides an exhaustive technical analysis and implementation roadmap for this feature, aiming to transform the map from a passive reference image into a living, breathing non-linear editor (NLE) for spatial history.

The core objective is to visualize the state and movement of entities—characters, armies, political borders—as a function of a global time variable, $t$. This requires the system to handle not just the spatial coordinates $(x, y)$, but the temporal existence and trajectory of thousands of entities simultaneously. The architectural challenge is threefold: designing a data model that efficiently queries state at any given $t$; building a rendering pipeline capable of updating thousands of graphical items at 60 frames per second (FPS) within the Python/Qt ecosystem; and constructing a user interface that bridges the gap between spatial manipulation and temporal scrubbing.

Analysis of the technical requirements and available frameworks, particularly PySide6 (Qt for Python), confirms that this vision is achievable. The Qt Graphics View Framework provides the necessary scene graph capabilities, while specific optimization strategies—such as OpenGL viewport integration, spatial indexing bypasses, and coordinate caching—can overcome the inherent performance bottlenecks of high-frequency updates in Python. This document outlines the mathematical foundations for trajectory interpolation, the synchronization logic for a master clock architecture, and the specific user interaction patterns required to enable "Live Puppeteering" and timeline scrubbing.

---

## 2. Theoretical Framework and Core Vision

### 2.1 The Limitations of Static Cartography
In traditional Geographic Information Systems (GIS) and fantasy map tools, an entity’s location is defined by a static coordinate tuple $P = (x, y)$. To represent movement, users are often forced to create multiple static markers (e.g., "Army at Start," "Army at Battle," "Army at End") or rely on separate map layers that must be manually toggled. This approach fractures the narrative continuity. It fails to convey velocity, simultaneous action, or the causal relationships between moving bodies. For a storytelling platform like ProjektKraken, the map must be a canvas for events, not just locations.

### 2.2 The Temporal Coordinate System
The "Temporal Map" architecture redefines the fundamental nature of a map marker. An entity $E$ is no longer a static point but a function of time:

$$P(t) = (x(t), y(t))$$

This function is defined over an existence interval $[t_{start}, t_{end}]$.
* **Global Time ($t$)**: A monotonic floating-point value controlled by a central clock.
* **Keyframes**: Discrete snapshots of the entity's state (position, rotation, opacity, metadata) at specific times.
* **Continuity**: The system must derive the state of the entity at any arbitrary time $t$ by interpolating between the nearest defined keyframes.

This shift necessitates a "Non-Linear Editor (NLE) on Map" philosophy. Much like video editing software allows editors to scrub through video frames, ProjektKraken must allow users to scrub through the "history" of their world. The map becomes the viewport, and the underlying data model becomes a collection of temporal tracks.

### 2.3 Core Use Case Analysis
The architecture is driven by three distinct use cases, each imposing unique technical constraints:
1. **Tracking Journeys (The Trajectory Problem)**:
   * *Scenario*: Visualizing a character's travel across a continent.
   * *Constraint*: Movement is rarely linear. Characters follow winding roads or rivers. The system must support complex interpolation (Bezier curves) and visual Motion Paths to show the "past" and "future" trajectory.
2. **Historical Borders (The Vertex Animation Problem)**:
   * *Scenario*: A kingdom expands its territory over 500 years.
   * *Constraint*: This involves animating `QPolygonF` items. Unlike point markers, regions may change topology. The system must interpolate vertex positions while maintaining the integrity of the shape.
3. **Battle Maneuvers (The Swarm Problem)**:
   * *Scenario*: A tactical view of a battle with 1,000 individual troop units.
   * *Constraint*: Performance is paramount. Updating the position of 1,000 independent items every 16ms (to achieve 60fps) is a stress test for the Python Global Interpreter Lock (GIL) and the Qt event loop.

---

## 3. Data Architecture and Storage Models
The foundation of the temporal map is the data structure used to store and retrieve time-based attributes.

### 3.1 The Temporal JSON Schema
To support the "Time" dimension, the data model for a marker must extend standard GeoJSON-like structures. A "Temporal Entity" is defined by a `timeline` property containing a sorted list of keyframes. This structure must be robust enough to handle position, but also extensible for other animated properties (e.g., opacity, color, scale).

**Proposed Data Schema:**

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Unique identifier for the entity. |
| `name` | String | Display name (e.g., "The One Ring"). |
| `existence` | Object | Defines the lifespan: `{ "start": 0, "end": 3019 }`. |
| `timeline` | List | A time-sorted list of keyframe objects. |

**Keyframe Structure:**
```json
{
  "t": 150.5,
  "pos": [0.45, 0.88],
  "interpolation": "cubic-bezier",
  "control_points": [[0.5, 0.5], [0.6, 0.6]],
  "attributes": {
    "opacity": 1.0,
    "label": "Camp at Amon Sul"
  }
}
```
This schema implies that the state of an entity between two keyframes is derived. If interpolation is "linear," the system computes a weighted average. If "cubic-bezier," it evaluates the curve equation.

### 3.2 Keyframe Storage and Retrieval Efficiency
During playback, the system requests the position of every entity at the current frame. If an entity has 10,000 keyframes (e.g., a highly detailed recorded path), iterating through the list to find the correct interval is computationally expensive ($O(N)$).

**Optimization: Binary Search (Bisect)**
To maximize performance, keyframes must be maintained as a strictly sorted list by time $t$. This allows the use of the binary search algorithm to locate the insertion point for the current time $t$. Python’s standard library `bisect` module provides a highly efficient C-implemented bisection algorithm.
* **Mechanism**: `bisect.bisect_right(keyframes, t)` returns the index $i$ where $t$ would be inserted.
* **Interval**: The current state is derived from `keyframes[i-1]` (start of interval) and `keyframes[i]` (end of interval).
* **Complexity**: This reduces the lookup cost from $O(N)$ to $O(\log N)$, which is critical when scrubbing through long histories with thousands of data points.

### 3.3 Calendar Integration: Mapping $t$ to Dates
A request from the "Future Roadmap" is to map the abstract float $t$ to actual calendar dates (e.g., "Year 3018, March 25").

**The Epoch System**:
The system should operate internally on a float $t$ (representing atomic units, e.g., hours or days since a global epoch). A translation layer handles the conversion to human-readable dates.
* **Calendar Model**: A `CalendarSystem` class defines the rules (months per year, days per month, leap year logic).
* **Mapping**:
$$Date = Epoch + t \times UnitScale$$
This separation of concerns allows the underlying animation engine to work with fast float arithmetic while the UI layer handles the complex string formatting of fantasy dates.

---

## 4. The Rendering Pipeline: Qt Graphics View Framework
The visual implementation relies on the Qt Graphics View Framework (accessible via PySide6), which utilizes a Model-View-Controller (MVC) architecture specifically designed for managing large numbers of 2D items.

### 4.1 The Scene Graph (QGraphicsScene)
The `QGraphicsScene` acts as the spatial data model. It manages the geometry of all items (markers, paths, terrain) and handles collision detection.
* **Coordinate System**: The scene operates in logical coordinates (Map Units), independent of the screen resolution or zoom level.
* **Coordinate Mapping**: Interaction requires constant translation between View (Pixel) and Scene (Map) coordinates.
    * `view.mapToScene(QPoint)`: Converts mouse pixel coordinates to map locations.
    * `view.mapFromScene(QPointF)`: Converts map locations to screen pixels (essential for static UI overlays).
* **Spatial Indexing**: The scene uses a Binary Space Partitioning (BSP) tree by default to rapidly locate items. While efficient for static scenes, this index can become a bottleneck for moving items, as the tree must be rebuilt whenever an item changes position.

### 4.2 The Viewport (QGraphicsView)
The `QGraphicsView` is the widget that renders the scene. It handles the transformation matrix (zoom/pan) and user input events.
* **Render Engine**: By default, `QGraphicsView` uses a raster paint engine (CPU-based). For high-performance animation of thousands of items, this is often insufficient.
* **OpenGL Acceleration**: The viewport can be backed by a `QOpenGLWidget`, forcing Qt to use the GPU for composition and rendering. This is a critical optimization for the "Battle Maneuvers" use case.
* **Y-Axis Inversion**: Standard GIS coordinates have $Y$ pointing Up (North), while Qt screen coordinates have $Y$ pointing Down. To align these, apply a scale transformation to the view: `view.scale(1, -1)`. This allows the scene logic to remain consistent with Cartesian GIS standards.
* **Infinite Canvas Policy**: To implement a modern "drag-to-pan" map style, disable the default scrollbars:
    ```python
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    ```

```python
view = QGraphicsView(scene)
view.setViewport(QOpenGLWidget())
# Invert Y axis to match GIS conventions
view.scale(1, -1)
```

### 4.3 The Temporal Marker Item (QGraphicsItem)
Each map marker is a subclass of `QGraphicsItem` (or `QGraphicsObject` if signals are needed).
* **Paint Method**: The `paint()` method draws the visual representation (e.g., an SVG icon or a circle).
* **Bounding Rect**: The `boundingRect()` method defines the area requiring updates. Accurately defining this is crucial for the view to optimize repaints.
* **State Updates**: Unlike standard items, a temporal marker does not store a fixed position. Instead, it subscribes to the global clock and updates its position via `setPos()` whenever the time changes.

---

## 5. Algorithmic Core: Interpolation and Trajectory
To create smooth motion from discrete keyframes, the system must employ robust interpolation algorithms.

### 5.1 Linear Interpolation (Lerp)
For strategic movements (e.g., "Army moves from City A to City B"), linear interpolation is sufficient and computationally cheap.
Given:
* Start Keyframe: $K_1$ at $t_1$, pos $P_1$
* End Keyframe: $K_2$ at $t_2$, pos $P_2$
* Current Time: $t$ where $t_1 \le t \le t_2$

The normalized progress factor $\alpha$ is:
$$\alpha = \frac{t - t_1}{t_2 - t_1}$$

The position $P(t)$ is:
$$P(t) = P_1 + (P_2 - P_1) \times \alpha$$

### 5.2 Bezier Interpolation (Organic Movement)
For tracking journeys along rivers or roads, linear movement looks robotic. Cubic Bezier curves provide the necessary smoothness. A cubic Bezier segment is defined by four points: $P_0$ (start), $P_1$ (control 1), $P_2$ (control 2), and $P_3$ (end).

The equation for a point on the curve is:
$$B(\tau) = (1-\tau)^3P_0 + 3(1-\tau)^2\tau P_1 + 3(1-\tau)\tau^2 P_2 + \tau^3P_3$$

**The Parameterization Challenge**:
In the standard Bezier equation, $\tau$ varies from 0 to 1. However, simply mapping the time progress $\alpha$ to $\tau$ results in non-uniform speed along the curve (the marker speeds up and slows down depending on the curvature).
* **Solution**: For strict constant-speed travel, the system must perform arc-length parameterization (remapping $\alpha$ to distance).
* **Approximation**: For the scale of ProjektKraken, a direct mapping ($\tau \approx \alpha$) is often visually acceptable and significantly faster to compute than numerical integration of arc length. If "perfect" speed is required, a lookup table (LUT) of arc lengths can be pre-calculated for each segment.

### 5.3 Region Animation (Polygon Morphing)
Animating the borders of a kingdom requires interpolating `QPolygonF` objects.
* **Topology Consistency**: Morphing between two polygons works best if they have the same number of vertices.
* **Algorithm**:
    1. Ensure $K_1$ (Polygon A) and $K_2$ (Polygon B) have $N$ vertices. (If not, vertex insertion is required).
    2. For each vertex index $i$, linearly interpolate between $V_{A,i}$ and $V_{B,i}$.
    3. Reconstruct the `QPolygonF` at time $t$ with the new vertex positions.

This allows regions to expand, contract, or shift smoothly over time.

---

## 6. Time Management Architecture
The synchronization of the entire application relies on a robust "Master Clock" architecture.

### 6.1 The Master Clock Controller
Unlike simple animations that might use `QPropertyAnimation` on individual items, a global timeline requires a centralized controller. This `MasterClock` is a `QObject` that maintains the authoritative current time $t$.
* **Signal Propagation**: The clock emits a `timeChanged(float t)` signal.
* **Subscription**: The `QGraphicsScene` or individual `TemporalMarker` items connect to this signal.
* **Scrubbing Logic**: When the user drags the timeline scrubber, the clock updates $t$ directly without advancing the internal timer.
* **Playback Logic**: When "Play" is active, a `QTimer` fires (e.g., every 16ms), incrementing $t$ by a delta ($\Delta t$) determined by the playback speed.

### 6.2 Handling "Time Skips" and Non-Linear Access
When the user scrubs the timeline (jumps from $t=100$ to $t=5000$), the system must handle the state change gracefully.
* **Instant Updates**: The interpolation logic is stateless; it depends only on the current $t$. Therefore, a jump is handled identically to a sequential update: binary search for the new interval, calculate position, update view.
* **Event Triggers**: If the system supports "Events" (e.g., "Battle starts at $t=300$"), the clock logic must detect if an event timestamp was crossed during the jump, although for pure visualization, calculating the static state is usually sufficient.

---

## 7. User Interface: The Timeline Widget
The "Timeline Widget" is the primary interface for temporal manipulation, docking at the bottom of the map view.

### 7.1 Architecture of the Timeline
The timeline is effectively a custom `QWidget` that draws a representation of time.
* **The Ruler**: A horizontal bar rendering time ticks. It requires a coordinate transform to map "Pixels" to "Time Units" (Zooming the timeline).
* **The Playhead**: A vertical indicator representing the current $t$ of the Master Clock.
* **Tracks**: Rows corresponding to selected entities. Each track displays the keyframes (diamonds) and existence duration (bars) of that entity.

### 7.2 Synchronization Logic
The Timeline and the Map must be tightly coupled:
1. **Timeline $\rightarrow$ Map**: Dragging the playhead emits `set_time(t)` to the Master Clock, which updates the Map markers.
2. **Map $\rightarrow$ Timeline**: Selecting a marker on the map adds its "Track" to the timeline widget. Dragging a keyframe node on the map (spatial edit) updates the keyframe's time/position in the data model, which triggers a repaint of the timeline track.

### 7.3 Zoom and Pan on the Time Axis
Users need to switch between "Tactical Time" (seconds/minutes) and "Historical Time" (years/centuries).
* **Implementation**: The Timeline Widget handles `wheelEvent`. Scrolling modifies a `scale_factor` (pixels per time unit).
* **Rendering**: The drawing logic uses this scale factor to determine the interval of tick marks (e.g., labeling every 10 years vs every 10 minutes).

---

## 8. Interaction Design: The "NLE on Map"
The user interface must facilitate not just viewing, but creating these complex journeys.

### 8.1 Live Puppeteering (Recording Mode)
A unique feature of ProjektKraken is the ability to "act out" a journey.
* **Mechanism**:
    1. User toggles "Record" mode.
    2. User drags a marker on the map.
    3. A `QTimer` samples the mouse position at a fixed interval (e.g., 100ms) or on every `mouseMoveEvent`.
    4. Each sample is saved as a keyframe: `{ t: current_time, x: mouse_x, y: mouse_y }`.
* **Smoothing**: Raw mouse input is jittery and dense. Post-processing is required. The Douglas-Peucker algorithm or simple distance-based filtering can reduce the number of keyframes while preserving the shape of the motion.

### 8.2 Motion Path Visualization and Editing
When a marker is selected, its path becomes visible.
* **Visual Component**: A `QGraphicsPathItem` draws the trajectory.
* **Node Editing**: The keyframes appear as small, draggable handles along the path.
* **Interaction**:
    * **Click & Drag Node**: Updates the $(x, y)$ of that keyframe.
    * **Right Click Node**: Opens a context menu to change interpolation (e.g., "Switch to Bezier").
    * **Tangent Handles**: If Bezier is selected, two additional handles (control points) appear, allowing the user to shape the curve.

### 8.3 Selection Challenges in a Dynamic Scene
Selecting a moving object is difficult.
* **Hit Testing**: Qt's `QGraphicsView` handles hit testing via `itemAt()`. However, if the item is moving 60 times a second, the user might miss.
* **Selection Implementation**:
    * **Flags**: Enable selection on items using `item.setFlag(QGraphicsItem.ItemIsSelectable, True)`.
    * **Retrieval**: Use `scene.selectedItems()` to get the current selection.
    * **Rubberband**: Enable rectangular selection with `view.setDragMode(QGraphicsView.RubberBandDrag)`.
* **Pause-on-Click**: A common UX pattern is to pause the Master Clock momentarily when the user presses the mouse button down, allowing for easier selection and manipulation.

---

## 9. Performance Engineering: Rendering at Scale
The requirement to support "thousands of markers" at 60fps is the most significant technical risk. The Python Global Interpreter Lock (GIL) and the overhead of crossing the Python/C++ boundary in PySide6 can lead to performance degradation.

### 9.1 Optimizing the Scene Graph
* **Disable Spatial Indexing (NoIndex)**:
The `QGraphicsScene` uses a BSP tree to index items. When an item moves, the tree must be updated. For 1,000 moving items, this re-indexing is expensive.
    * **Strategy**: For the layer containing moving units, call `scene.setItemIndexMethod(QGraphicsScene.NoIndex)`. This disables the index. Collision detection becomes $O(N)$, but the frame update cost drops significantly.
* **Item Coordinate Cache**:
Complex markers (e.g., detailed SVG sigils) are expensive to paint.
    * **Strategy**: Enable `QGraphicsItem.ItemCoordinateCache`. Qt renders the item to an offscreen pixmap and reuses it as long as the item's appearance doesn't change (even if it moves). This shifts the load from the CPU (painting) to the GPU (texture blitting).

### 9.2 The OpenGL Viewport Solution
Standard `QWidget` viewports perform rasterization on the CPU.
* **Strategy**: Set the `QGraphicsView` viewport to `QOpenGLWidget`.
* **Benefit**: This unlocks hardware acceleration. Modern GPUs can handle the composition of thousands of textured quads (the cached markers) with ease, bypassing the CPU bottleneck of software rasterization.

### 9.3 Level of Detail (LOD)
Rendering full details for 1,000 units when zoomed out is wasteful.
* **Strategy**: Implement LOD in the `paint()` method.
    * **High Zoom**: Draw full SVG marker.
    * **Medium Zoom**: Draw simplified geometric shape.
    * **Low Zoom**: Draw a single pixel or dot.
* **Implementation**: Use `QStyleOptionGraphicsItem.levelOfDetailFromTransform` to determine the current zoom factor and branch the painting logic accordingly.

### 9.4 Batching Updates
To avoid 1,000 separate Python-to-C++ calls per frame:
* **Strategy**: Vectorize the math. Use `numpy` to calculate the positions of all 1,000 units for time $t$ in a single batch operation. While updating the `QGraphicsItem` positions still requires a loop, the heavy lifting of interpolation is done in optimized C code via `numpy`.
* **Thread Safety**: **Critical Warning**: Qt Widgets are NOT thread-safe. Do not attempt to update `QGraphicsItem` positions from a background thread.
    * **Pattern**: Calculate positions in a worker thread (or `numpy` op), then emit a signal with the result. A slot on the main thread receives the data and efficiently calls `setPos` on the items.

---

## 10. Advanced Features and Future Roadmap

### 10.1 Ghost Trails (Motion History)
Visualizing where an entity was is crucial for understanding battle maneuvers.
* **Implementation Options**:
    1. **Particle System**: Spawn fading "ghost" items behind the marker. Drawback: Explodes the item count (1,000 units $\times$ 10 ghosts = 10,000 items).
    2. **Path Stroking (Recommended)**: Each marker maintains a `QPolygonF` of its last $N$ positions. The `paint()` method draws this polyline.
* **Fading Effect**: Using a `QLinearGradient` brush along the path allows the trail to fade out smoothly without managing transparency for separate items. This is far more performant than particle systems in a `QGraphicsView` context.

### 10.2 Visibility and Existence Intervals
Entities that "die" or haven't been "born" must be hidden.
* **Optimization**: Simply calling `hide()` is not enough if the system still iterates over them.
* **Active List**: Maintain a separate list of "Active Entities" for the current time window. Only update and render items in this list. When $t$ crosses an existence boundary ($t_{start}$ or $t_{end}$), move the entity between the "Active" and "Inactive" lists.

---

## 11. Implementation Roadmap

**Phase 1: The Core Engine**
1. Implement `TemporalEntity` class and JSON schema.
2. Build `MasterClock` and basic `QTimer` playback loop.
3. Implement `bisect` based keyframe lookup.

**Phase 2: The Viewer**
1. Set up `QGraphicsScene` with `QOpenGLWidget` viewport.
2. Implement `TemporalMarker` item with `setPos` updates.
3. Create the Timeline Widget with basic scrubbing.

**Phase 3: Interaction & Recording**
1. Implement "Record" mode with mouse sampling.
2. Add Motion Path visualization (`QGraphicsPathItem`).
3. Implement node dragging and Bezier control points.

**Phase 4: Optimization & Scale**
1. Profile with 1,000 items.
2. Implement `ItemCoordinateCache` and `NoIndex`.
3. Add Level of Detail (LOD) logic.

---

## 12. Comparison of Optimization Techniques

| Technique | Implementation Effort | Performance Gain | Use Case |
| :--- | :--- | :--- | :--- |
| **Binary Search (Bisect)** | Low | High ($O(\log N)$ lookup) | Playback/Scrubbing of long histories. |
| **OpenGL Viewport** | Medium | Very High (GPU Render) | Rendering 1000+ items; Battle Maneuvers. |
| **Item Coordinate Cache** | Low | High (Texture Blitting) | Complex SVG markers moving without scaling. |
| **NoIndex (BSP Bypass)** | Low | High (Update Speed) | Constant movement of many items. |
| **LOD (Level of Detail)** | Medium | Medium (Paint reduction) | Viewing the whole world map (Zoomed out). |

## 13. Current Implementation Status (Jan 2026)

### Completed Groundwork
* **Rendering Engine**: `MapGraphicsView` has been upgraded to use `QOpenGLWidget` as the viewport. This provides the GPU acceleration foundation required for future high-load scenarios.
* **Coordinate System**: A strict **Cartesian 2D** abstraction layer (`MapCoordinateSystem`) has been implemented.
    *   It cleanly separates Normalized [0, 1] logic from Scene/Pixel logic.
    *   It is architected to support future `pyproj` integration without breaking the UI.
    *   **Note**: Full Y-Axis Inversion is prepared for but not yet active to match current static map behavior.
* **Database Schema**: The `moving_features` table has been added to the SQLite schema.
    *   It supports storing `trajectory` as a JSON blob.
    *   Temporal indices (`t_start`, `t_end`) are in place for efficient queries.
* **Interaction**: The map now uses an "Infinite Canvas" interaction model (Scrollbars disabled, Drag-to-Pan enforced).

### Existing Capabilities
* **Map Visualization**: Supports loading static map images (`QGraphicsPixmapItem`).
* **Marker Implementation**:
    *   `MarkerItem` supports SVG icons and coloring.
    *   Optimization flags (`ItemIsMovable`, `ItemSendsGeometryChanges`, `ItemCoordinateCache` equivalent) are enabled.
* **Map Hardening / GIS Features**:
    *   **Scale Bar**: Implemented GIS-style scale bar overlay (`ScaleBarPainter`) leveraging `drawForeground`.
    *   **Configuration**: Added "Settings" dialog to define map pixel-to-meter ratio.
    *   **Live Coordinates**: Real-time display of Normalized and Kilometer coordinates.
    *   **UI Polish**: Standardized Map Widget toolbar with `QPushButton` styling to match application theme.
* **Layers**: The scene is now structured with defined Z-Values (`LAYER_MAP_BG`, `LAYER_MARKERS`, etc.) to prevent future rendering conflicts.
* **Code Quality & Stability**:
    *   **Marker Logic**: Refactored `MarkerItem` for better maintainability (helper methods for painting/drag).
    *   **Critical Fixes**: Resolved interaction bugs where markers at `(0,0)` were unclickable.
    *   **Testing**: Expanded unit tests to cover coordinate display and marker signals.

### Temporal Synchronization & Animation
* **Timeline ↔ Map Signal Wiring**: The map subscribes to time changes from the Timeline widget (`playhead_time_changed`).
* **Interpolation Logic**: Implemented `interpolate_position` (Linear) using `bisect` for efficient keyframe lookup.
* **Marker Movement**: `MapWidget` now automatically updates marker positions during timeline scrubbing/playback based on interpolated trajectory data.
* **Trajectory Persistence**: Dedicated `TrajectoryRepository` handles ACID-compliant storage of keyframes, resolving the mapping between transient UI "Object IDs" and persistent Database Primary Keys.

### Interaction & Visualization
* **Manual Keyframing (Snapshots)**: Added "Add Keyframe" button to the Map toolbar. This allows users to set precise snapshots of marker state at specific timeline moments.
* **Trajectory Visualizer**:
    *   **Visual Cues**: When a marker is selected, its entire trajectory is rendered as a dashed path.
    *   **Keyframe Indicators**: Individual keyframes are visualized as dots on the map, providing immediate visual feedback of the "history" of the entity.
    *   **Zoom-Aware Rendering**: Keyframe dots scale with zoom level to maintain visual consistency.
* **Dual-Mode Keyframe Editing** (Implemented):
    *   **Transform Mode (Spatial)**: Default state. Users can click and drag keyframe dots to reposition their $(x, y)$ coordinates. The trajectory path updates in real-time (Rubber-Banding).
    *   **Clock Mode (Temporal)**:
        *   **Gizmo Activation**: Hovering a keyframe reveals a persistent "Clock" icon.
        *   **Pinning**: Clicking the icon "Pins" the keyframe, locking its spatial position but unlocking its timestamp.
        *   **Visual Feedback**: Pinned keyframes glow **Cyan** (#00FFFF) to clearly distinguish Temporal Mode from Spatial selection.
        *   **Scrub-to-Edit**: While pinned, scrubbing the timeline moves the keyframe itself through time (updating $t$) rather than moving the playhead.
        *   **Commit**: Clicking the icon again commits the new timestamp, automatically re-sorting the keyframe list to maintain chronological integrity.

### Gaps & Next Steps
1.  **Recording Mode**: The "Live Puppeteering" logic (Phase 8.1) for recording real-time mouse movements is not yet implemented.
2.  **Bezier Interpolation**: Current interpolation is strictly linear; Bezier support (Phase 5.2) remains a roadmap item.

---

## 14. The Chronological Paradox: Architectural and Interaction Patterns for State Persistence in Temporal Cartesian Interfaces

### 14.1 Introduction: The Gulf of Execution in Non-Linear Time
The interaction design of temporal interfaces—specifically those governing the animation of spatial markers on Cartesian planes—represents one of the most sophisticated challenges in Human-Computer Interaction (HCI). The user query highlights a fundamental friction point inherent to Non-Linear Editing (NLE) systems: the conflict between the Recorded State, defined by the deterministic interpolation of the evaluation graph, and the Transient State, generated by the user's immediate manipulation of the viewport.

This report analyzes a specific solution proposed by the user: a Hybrid Static/Buffer Model. In this model, manipulating a marker "outside" a keyframe range affects its global static position, while manipulating it "inside" a range creates a temporary, scrubbable "transient" keyframe set that persists until explicitly committed.

This document validates this workflow against industry standards, specifically drawing parallels to Buffer Curves in Autodesk Maya, Animation Layers in MotionBuilder, and Additive Animation logic in game engines.

#### 14.1.1 The Phenomenology of the "Snap Back"
The "snap back" occurs because standard NLE architectures prioritize the timeline's authority over the user's input buffer. When the playhead moves, the system recalculates the scene based on the graph, discarding any "unsaved" values. The user's proposed model resolves this by creating a Temporary Edit Session—a state where the "Transient Value" temporarily overrides the "Recorded Value" during scrubbing, bridging the gap between exploration and commitment.

### 14.2 The Hybrid Static/Buffer Architecture
The user's proposed workflow divides the timeline into two distinct interaction zones. This section deconstructs that logic using established animation theory.

#### 14.2.1 Zone 1: Outside Keyframe Range (The Static Base)
*   **User Input**: "Outside the range the position is undefined by key frames, it is just an arbitrary position."
    *   In professional animation terms, this is the Base Layer or Setup Mode.
*   **Concept**: When the playhead is outside the influence of an active F-Curve (or before/after the animation clip), the object falls back to its static transform properties.
*   **Behavior**: Moving the marker here does not create a keyframe. Instead, it updates the Global Offset or Root Transform of the object.
*   **Technical Precedent**: This mirrors the behavior in MotionBuilder where editing on the "BaseAnimation" layer shifts the entire character's position without altering the relative animation data on layers above it.
*   **UX Benefit**: This solves the "layout" problem. Users can reposition a marker (e.g., "Move the entire path 50 pixels East") without having to select and move every individual keyframe.

#### 14.2.2 Zone 2: Inside Keyframe Range (The Transient Buffer)
*   **User Input**: "Moving a marker sets a new transient keyframe. Scrubbing keeps that but dirties the keyframe set."
    *   This is the core innovation of the proposed model. It creates a Non-Destructive Edit Buffer.
*   **Concept**: When the user manipulates a value inside a keyed range, the system does not immediately overwrite the curve. Instead, it creates a Transient Keyframe in a temporary memory buffer.
*   **Scrubbing Behavior**: The animation engine calculates position as:
    $$P(t) = Interpolation(Keyframes_{original}) + \Delta(Transient)$$
    Or, in a replacement logic:
    $$P(t) = Interpolation(Keyframes_{transient})$$
*   **Persistence**: Crucially, this transient state survives the "Scrub" event. The user can scrub back and forth to see how their new (unsaved) keyframe interacts with the rest of the animation.
*   **Industry Validation**: This is functionally identical to the Buffer Curve workflow in Autodesk Maya. In Maya, users can take a "Snapshot" of a curve, edit it, and scrub the timeline to compare the "Edited" (Transient) curve against the "Buffer" (Original) curve before swapping/committing.

### 14.3 Comparative Analysis of "Proven and Tested" Interaction Models
To implement the user's model effectively, we must look at how similar "Buffer" and "Commit" patterns are handled in existing software.

#### 14.3.1 The "Buffer Curve" Pattern (Maya)
Maya allows users to edit animation curves non-destructively using buffers.
*   **Mechanism**: The user selects a curve and creates a "Buffer Snapshot." The original curve turns gray (Ghost), and the active curve can be edited freely.
*   **Scrubbing**: The viewport updates to show the new (transient) animation.
*   **Commit**: The user clicks "Swap Buffer" to make the changes permanent, or reverts to the snapshot to discard them.
*   **Relevance**: This proves that separating "Transient Edit Data" from "Committed Data" is a stable, professional workflow.

#### 14.3.2 The "Audition Mode" (Audio & Sequencing)
In audio software (DAWs) and some NLEs, "Auditioning" allows users to hear/see changes without writing them.
*   **Logic**: Parameters changed during playback are "overridden" but revert once playback stops unless "Write Automation" is enabled.
*   **User's Variation**: The user wants the change to persist after the scrub stops (until committed). This is effectively a "Latch" mode in automation terms, but applied to a draft state.

#### 14.3.3 The "Animation Layer" Pattern (Unity/Blender)
This pattern uses additive logic to handle the "Transient Keyframe."
*   **Mechanism**: When the user moves the marker inside the range, the system effectively spawns a hidden Additive Animation Layer.
*   **Math**: The specific move is stored as a $+ \Delta(x,y)$ on this layer.
*   **Scrubbing**: The system sums the Base Track + The Additive Layer.
*   **Commit**: Clicking "Commit" flattens (bakes) the additive layer down into the Base Track.

### 14.4 Proposed UX Framework: The "Draft & Commit" Workflow
Based on the research and the user's guiding input, here is the recommended specification for the UI/UX.

#### 14.4.1 The "Dirty" State Visualization
When a user moves a marker inside a keyframe range, the interface must explicitly signal that the timeline has entered a Draft/Dirty State.

| State | Visual Indicator | Data Status | Scrub Behavior |
| :--- | :--- | :--- | :--- |
| **Clean** | White/Grey Keyframes | Read from Graph | Standard Interpolation |
| **Draft (Transient)** | Amber/Yellow Path & Keyframes | Read from Buffer | Persists (User's Requirement) |
| **Committed** | Blue/Red Keyframes | Written to Graph | Standard Interpolation |

*   **Ghosting**: To prevent disorientation, the system should display a Ghost of the original path (the "Snap Back" destination) as a faint dotted line. This gives the user confidence that their original data is safe.

#### 14.4.2 The Interaction Logic

**Outside the Range (Setup Mode)**
*   **Action**: User drags marker at $t < Start$ or $t > End$.
*   **System**: Updates Object.BasePosition.
*   **Visual**: The entire animation path shifts rigidly. No keyframes are added.
*   **Feedback**: "Global Offset Applied."

**Inside the Range (Draft Mode)**
*   **Action**: User drags marker at $t_{current}$.
*   **System**:
    1.  Checks if DraftBuffer exists. If not, creates one as a copy of ActiveCurve.
    2.  Inserts Key_{transient} at $t_{current}$ into DraftBuffer.
    3.  Sets Renderer.Source = DraftBuffer.
*   **Visual**:
    *   The marker path turns Amber.
    *   A "Commit" button (Checkmark) and "Discard" button (X) appear near the marker or timeline.
    *   **Ghost**: The original path remains visible (Grey/Transparent).
*   **Scrubbing**: The user scrubs. The marker follows the Amber path (the Draft). The Grey path (Original) stays put.

#### 14.4.3 The "Commit" Action
*   **Action**: User clicks "Commit."
*   **System**:
    1.  ActiveCurve = DraftBuffer.
    2.  DraftBuffer = null.
    3.  Renderer.Source = ActiveCurve.
*   **Visual**: Amber path turns standard color. Ghost disappears. "Commit" button vanishes.

### 14.5 Technical Considerations

#### 14.5.1 Handling "Transient" Data
To support scrubbing without "snapping back," the application must maintain a Secondary State Object for the active selection.
*   **Reference**: This is similar to the EditorCurveBinding in Unity or the F-Curve Modifier stack in Blender.
*   **Implementation**: The "Scrub" event listener usually queries AnimationEngine.evaluate(time). It must be patched to query DraftEngine.evaluate(time) if isDirty == true.

#### 14.5.2 Auto-Keying vs. Explicit Commit
The user requested a Button to Commit. This is an "Explicit Save" pattern.
*   **Pros**: Prevents accidental destruction of carefully tuned animation curves.
*   **Cons**: Requires an extra click.
*   **Recommendation**: Offer a "Auto-Commit" toggle in settings for power users, but default to the Explicit Button to solve the "Snap Back" anxiety.

### 14.6 Summary of Recommendations
To build the solution geared to your specific input:
1.  **Adopt "Buffer Curve" Architecture**: Treat the "Inside Range" edits as a temporary layer (Draft) that overlays the original data. This allows the scrubbing persistence you require.
2.  **Implement Visual Ghosting**: Always show the "Original" position (Ghost) when a "Transient" keyframe is active. This explains the relationship between the Draft and the Saved state.
3.  **Differentiate "Static" vs. "Keyed" Moves**: Explicitly handle "Outside Range" moves as global offsets (changing the root transform) rather than adding keys. This aligns with the "Setup vs. Animate" mode distinction.
4.  **Floating Commit UI**: Place the "Commit/Discard" controls directly in the viewport near the modified marker to reduce mouse travel and reinforce the "Draft" metaphor.

This approach transforms the "Snap Back" bug into a powerful Non-Destructive Versioning Feature, giving users the freedom to experiment ("audition") without fear of data loss.

### Works cited
*   Animation Layers - Maya - Autodesk product documentation, accessed on January 7, 2026, https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-5C202CB8-EB3C-4ADE-B203-5F93A9FD9104
*   NLA Additive Animation Layers: (Add/Subtract/Multiply) - Blender Artists Community, accessed on January 7, 2026, https://blenderartists.org/t/nla-additive-animation-layers-add-subtract-multiply/1100149
*   Saving - Primer Design System, accessed on January 7, 2026, https://primer.style/product/ui-patterns/saving/


