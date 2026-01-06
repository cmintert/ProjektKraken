# **ProjektKraken: Temporal Map Markers \- Architectural Specification and Implementation Strategy**

## **1\. Executive Summary: The Fourth Dimension in Digital Cartography**

The visualization of geospatial data has traditionally been bound by the constraints of static representation—a snapshot of a world frozen in a single moment. However, the narrative requirements of ProjektKraken, specifically in the domains of storytelling, world-building, and historical simulation, demand a fundamental paradigm shift. The "Temporal Map Markers" initiative, previously classified as an abandoned proposal, represents the critical evolution from static 2D maps to dynamic 4D visualizations. This report provides an exhaustive technical analysis and implementation roadmap for resurrecting this feature, aiming to transform the map from a passive reference image into a living, breathing non-linear editor (NLE) for spatial history.

The core objective is to visualize the state and movement of entities—characters, armies, political borders—as a function of a global time variable, $t$. This requires the system to handle not just the spatial coordinates $(x, y)$, but the temporal existence and trajectory of thousands of entities simultaneously. The architectural challenge is threefold: designing a data model that efficiently queries state at any given $t$; building a rendering pipeline capable of updating thousands of graphical items at 60 frames per second (FPS) within the Python/Qt ecosystem; and constructing a user interface that bridges the gap between spatial manipulation and temporal scrubbing.

Analysis of the technical requirements and available frameworks, particularly PySide6 (Qt for Python), confirms that this vision is achievable. The Qt Graphics View Framework provides the necessary scene graph capabilities 1, while specific optimization strategies—such as OpenGL viewport integration, spatial indexing bypasses, and coordinate caching—can overcome the inherent performance bottlenecks of high-frequency updates in Python.2 This document outlines the mathematical foundations for trajectory interpolation, the synchronization logic for a master clock architecture, and the specific user interaction patterns required to enable "Live Puppeteering" and timeline scrubbing, ultimately delivering a toolset where users can visualize the journey of the "One Ring" or the shifting borders of empires with cinematic fluidity.

## ---

**2\. Theoretical Framework and Core Vision**

### **2.1 The Limitations of Static Cartography**

In traditional Geographic Information Systems (GIS) and fantasy map tools, an entity’s location is defined by a static coordinate tuple $P \= (x, y)$. To represent movement, users are often forced to create multiple static markers (e.g., "Army at Start," "Army at Battle," "Army at End") or rely on separate map layers that must be manually toggled. This approach fractures the narrative continuity. It fails to convey velocity, simultaneous action, or the causal relationships between moving bodies. For a storytelling platform like ProjektKraken, the map must be a canvas for *events*, not just *locations*.

### **2.2 The Temporal Coordinate System**

The "Temporal Map" architecture redefines the fundamental nature of a map marker. An entity $E$ is no longer a static point but a function of time:

$$P(t) \= (x(t), y(t))$$

This function is defined over an existence interval $\[t\_{start}, t\_{end}\]$.

* **Global Time ($t$):** A monotonic floating-point value controlled by a central clock.  
* **Keyframes:** Discrete snapshots of the entity's state (position, rotation, opacity, metadata) at specific times.  
* **Continuity:** The system must derive the state of the entity at any arbitrary time $t$ by interpolating between the nearest defined keyframes.

This shift necessitates a "Non-Linear Editor (NLE) on Map" philosophy. Much like video editing software (e.g., Adobe Premiere, DaVinci Resolve) allows editors to scrub through video frames, ProjektKraken must allow users to scrub through the "history" of their world. The map becomes the viewport, and the underlying data model becomes a collection of temporal tracks.

### **2.3 Core Use Case Analysis**

The architecture is driven by three distinct use cases, each imposing unique technical constraints:

1. **Tracking Journeys (The Trajectory Problem):**  
   * *Scenario:* Visualizing a character's travel across a continent.  
   * *Constraint:* Movement is rarely linear. Characters follow winding roads or rivers. The system must support complex interpolation (Bezier curves) and visual Motion Paths to show the "past" and "future" trajectory.  
2. **Historical Borders (The Vertex Animation Problem):**  
   * *Scenario:* A kingdom expands its territory over 500 years.  
   * *Constraint:* This involves animating QPolygonF items. Unlike point markers, regions may change topology. The system must interpolate vertex positions while maintaining the integrity of the shape.  
3. **Battle Maneuvers (The Swarm Problem):**  
   * *Scenario:* A tactical view of a battle with 1,000 individual troop units.  
   * *Constraint:* Performance is paramount. Updating the position of 1,000 independent items every 16ms (to achieve 60fps) is a stress test for the Python Global Interpreter Lock (GIL) and the Qt event loop.3

## ---

**3\. Data Architecture and Storage Models**

The foundation of the temporal map is the data structure used to store and retrieve time-based attributes.

### **3.1 The Temporal JSON Schema**

To support the "Time" dimension, the data model for a marker must extend standard GeoJSON-like structures. A "Temporal Entity" is defined by a timeline property containing a sorted list of keyframes. This structure must be robust enough to handle position, but also extensible for other animated properties (e.g., opacity, color, scale).

**Proposed Data Schema:**

| Attribute | Type | Description |
| :---- | :---- | :---- |
| id | UUID | Unique identifier for the entity. |
| name | String | Display name (e.g., "The One Ring"). |
| existence | Object | Defines the lifespan: { "start": 0, "end": 3019 }. |
| timeline | List | A time-sorted list of keyframe objects. |

**Keyframe Structure:**

JSON

{  
  "t": 150.5,  
  "pos": ,  
  "interpolation": "cubic-bezier",  
  "control\_points": \[, \],  
  "attributes": {  
    "opacity": 1.0,  
    "label": "Camp at Amon Sul"  
  }  
}

This schema implies that the state of an entity between two keyframes is derived. If interpolation is "linear," the system computes a weighted average. If "cubic-bezier," it evaluates the curve equation.

### **3.2 Keyframe Storage and Retrieval Efficiency**

During playback, the system requests the position of every entity at the current frame. If an entity has 10,000 keyframes (e.g., a highly detailed recorded path), iterating through the list to find the correct interval is computationally expensive ($O(N)$).

Optimization: Binary Search (Bisect)  
To maximize performance, keyframes must be maintained as a strictly sorted list by time $t$. This allows the use of the binary search algorithm to locate the insertion point for the current time $t$. Python’s standard library bisect module provides a highly efficient C-implemented bisection algorithm.4

* **Mechanism:** bisect.bisect\_right(keyframes, t) returns the index $i$ where $t$ would be inserted.  
* **Interval:** The current state is derived from keyframes\[i-1\] (start of interval) and keyframes\[i\] (end of interval).  
* **Complexity:** This reduces the lookup cost from $O(N)$ to $O(\\log N)$, which is critical when scrubbing through long histories with thousands of data points.5

### **3.3 Calendar Integration: Mapping $t$ to Dates**

A request from the "Future Roadmap" is to map the abstract float $t$ to actual calendar dates (e.g., "Year 3018, March 25").

The Epoch System:  
The system should operate internally on a float $t$ (representing atomic units, e.g., hours or days since a global epoch). A translation layer handles the conversion to human-readable dates.

* *Calendar Model:* A CalendarSystem class defines the rules (months per year, days per month, leap year logic).  
* Mapping:

  $$Date \= Epoch \+ t \\times UnitScale$$

  This separation of concerns allows the underlying animation engine to work with fast float arithmetic while the UI layer handles the complex string formatting of fantasy dates.

## ---

**4\. The Rendering Pipeline: Qt Graphics View Framework**

The visual implementation relies on the Qt Graphics View Framework (accessible via PySide6), which utilizes a Model-View-Controller (MVC) architecture specifically designed for managing large numbers of 2D items.1

### **4.1 The Scene Graph (QGraphicsScene)**

The QGraphicsScene acts as the spatial data model. It manages the geometry of all items (markers, paths, terrain) and handles collision detection.

* **Coordinate System:** The scene operates in logical coordinates (Map Units), independent of the screen resolution or zoom level.6  
* **Spatial Indexing:** The scene uses a Binary Space Partitioning (BSP) tree by default to rapidly locate items. While efficient for static scenes, this index can become a bottleneck for moving items, as the tree must be rebuilt whenever an item changes position.7

### **4.2 The Viewport (QGraphicsView)**

The QGraphicsView is the widget that renders the scene. It handles the transformation matrix (zoom/pan) and user input events.

* **Render Engine:** By default, QGraphicsView uses a raster paint engine (CPU-based). For high-performance animation of thousands of items, this is often insufficient.  
* **OpenGL Acceleration:** The viewport can be backed by a QOpenGLWidget, forcing Qt to use the GPU for composition and rendering. This is a critical optimization for the "Battle Maneuvers" use case.2  
  Python  
  view \= QGraphicsView(scene)  
  view.setViewport(QOpenGLWidget())

### **4.3 The Temporal Marker Item (QGraphicsItem)**

Each map marker is a subclass of QGraphicsItem (or QGraphicsObject if signals are needed).

* **Paint Method:** The paint() method draws the visual representation (e.g., an SVG icon or a circle).  
* **Bounding Rect:** The boundingRect() method defines the area requiring updates. Accurately defining this is crucial for the view to optimize repaints.8  
* **State Updates:** Unlike standard items, a temporal marker does not store a fixed position. Instead, it subscribes to the global clock and updates its position via setPos() whenever the time changes.

## ---

**5\. Algorithmic Core: Interpolation and Trajectory**

To create smooth motion from discrete keyframes, the system must employ robust interpolation algorithms.

### **5.1 Linear Interpolation (Lerp)**

For strategic movements (e.g., "Army moves from City A to City B"), linear interpolation is sufficient and computationally cheap.  
Given:

* Start Keyframe: $K\_1$ at $t\_1$, pos $P\_1$  
* End Keyframe: $K\_2$ at $t\_2$, pos $P\_2$  
* Current Time: $t$ where $t\_1 \\le t \\le t\_2$

The normalized progress factor $\\alpha$ is:

$$\\alpha \= \\frac{t \- t\_1}{t\_2 \- t\_1}$$  
The position $P(t)$ is:

$$P(t) \= P\_1 \+ (P\_2 \- P\_1) \\times \\alpha$$

### **5.2 Bezier Interpolation (Organic Movement)**

For tracking journeys along rivers or roads, linear movement looks robotic. Cubic Bezier curves provide the necessary smoothness. A cubic Bezier segment is defined by four points: $P\_0$ (start), $P\_1$ (control 1), $P\_2$ (control 2), and $P\_3$ (end).9

The equation for a point on the curve is:

$$B(\\tau) \= (1-\\tau)^3P\_0 \+ 3(1-\\tau)^2\\tau P\_1 \+ 3(1-\\tau)\\tau^2 P\_2 \+ \\tau^3P\_3$$  
The Parameterization Challenge:  
In the standard Bezier equation, $\\tau$ varies from 0 to 1\. However, simply mapping the time progress $\\alpha$ to $\\tau$ results in non-uniform speed along the curve (the marker speeds up and slows down depending on the curvature).

* *Solution:* For strict constant-speed travel, the system must perform arc-length parameterization (remapping $\\alpha$ to distance).  
* *Approximation:* For the scale of ProjektKraken, a direct mapping ($\\tau \\approx \\alpha$) is often visually acceptable and significantly faster to compute than numerical integration of arc length. If "perfect" speed is required, a lookup table (LUT) of arc lengths can be pre-calculated for each segment.

### **5.3 Region Animation (Polygon Morphing)**

Animating the borders of a kingdom requires interpolating QPolygonF objects.

* **Topology Consistency:** Morphing between two polygons works best if they have the same number of vertices.  
* **Algorithm:**  
  1. Ensure $K\_1$ (Polygon A) and $K\_2$ (Polygon B) have $N$ vertices. (If not, vertex insertion is required).  
  2. For each vertex index $i$, linearly interpolate between $V\_{A,i}$ and $V\_{B,i}$.  
  3. Reconstruct the QPolygonF at time $t$ with the new vertex positions.10

This allows regions to expand, contract, or shift smoothly over time.

## ---

**6\. Time Management Architecture**

The synchronization of the entire application relies on a robust "Master Clock" architecture.

### **6.1 The Master Clock Controller**

Unlike simple animations that might use QPropertyAnimation on individual items, a global timeline requires a centralized controller. This MasterClock is a QObject that maintains the authoritative current time $t$.

* **Signal Propagation:** The clock emits a timeChanged(float t) signal.  
* **Subscription:** The QGraphicsScene or individual TemporalMarker items connect to this signal.  
* **Scrubbing Logic:** When the user drags the timeline scrubber, the clock updates $t$ directly without advancing the internal timer.  
* **Playback Logic:** When "Play" is active, a QTimer fires (e.g., every 16ms), incrementing $t$ by a delta ($\\Delta t$) determined by the playback speed.11

### **6.2 Handling "Time Skips" and Non-Linear Access**

When the user scrubs the timeline (jumps from $t=100$ to $t=5000$), the system must handle the state change gracefully.

* **Instant Updates:** The interpolation logic is stateless; it depends only on the current $t$. Therefore, a jump is handled identically to a sequential update: binary search for the new interval, calculate position, update view.  
* **Event Triggers:** If the system supports "Events" (e.g., "Battle starts at $t=300$"), the clock logic must detect if an event timestamp was crossed during the jump, although for pure visualization, calculating the static state is usually sufficient.

## ---

**7\. User Interface: The Timeline Widget**

The "Timeline Widget" is the primary interface for temporal manipulation, docking at the bottom of the map view.

### **7.1 Architecture of the Timeline**

The timeline is effectively a custom QWidget that draws a representation of time.

* **The Ruler:** A horizontal bar rendering time ticks. It requires a coordinate transform to map "Pixels" to "Time Units" (Zooming the timeline).12  
* **The Playhead:** A vertical indicator representing the current $t$ of the Master Clock.  
* **Tracks:** Rows corresponding to selected entities. Each track displays the keyframes (diamonds) and existence duration (bars) of that entity.

### **7.2 Synchronization Logic**

The Timeline and the Map must be tightly coupled:

1. **Timeline $\\rightarrow$ Map:** Dragging the playhead emits set\_time(t) to the Master Clock, which updates the Map markers.  
2. **Map $\\rightarrow$ Timeline:** Selecting a marker on the map adds its "Track" to the timeline widget. Dragging a keyframe node on the map (spatial edit) updates the keyframe's time/position in the data model, which triggers a repaint of the timeline track.13

### **7.3 Zoom and Pan on the Time Axis**

Users need to switch between "Tactical Time" (seconds/minutes) and "Historical Time" (years/centuries).

* **Implementation:** The Timeline Widget handles wheelEvent. Scrolling modifies a scale\_factor (pixels per time unit).  
* **Rendering:** The drawing logic uses this scale factor to determine the interval of tick marks (e.g., labeling every 10 years vs every 10 minutes).

## ---

**8\. Interaction Design: The "NLE on Map"**

The user interface must facilitate not just viewing, but *creating* these complex journeys.

### **8.1 Live Puppeteering (Recording Mode)**

A unique feature of ProjektKraken is the ability to "act out" a journey.

* **Mechanism:**  
  1. User toggles "Record" mode.  
  2. User drags a marker on the map.  
  3. A QTimer samples the mouse position at a fixed interval (e.g., 100ms) or on every mouseMoveEvent.14  
  4. Each sample is saved as a keyframe: { t: current\_time, x: mouse\_x, y: mouse\_y }.  
* **Smoothing:** Raw mouse input is jittery and dense. Post-processing is required. The **Douglas-Peucker algorithm** or simple distance-based filtering can reduce the number of keyframes while preserving the shape of the motion.15

### **8.2 Motion Path Visualization and Editing**

When a marker is selected, its path becomes visible.

* **Visual Component:** A QGraphicsPathItem draws the trajectory.  
* **Node Editing:** The keyframes appear as small, draggable handles along the path.  
* **Interaction:**  
  * *Click & Drag Node:* Updates the $(x, y)$ of that keyframe.  
  * *Right Click Node:* Opens a context menu to change interpolation (e.g., "Switch to Bezier").  
  * *Tangent Handles:* If Bezier is selected, two additional handles (control points) appear, allowing the user to shape the curve.16

### **8.3 Selection Challenges in a Dynamic Scene**

Selecting a moving object is difficult.

* **Hit Testing:** Qt's QGraphicsView handles hit testing via itemAt(). However, if the item is moving 60 times a second, the user might miss.  
* **Pause-on-Click:** A common UX pattern is to pause the Master Clock momentarily when the user presses the mouse button down, allowing for easier selection and manipulation.

## ---

**9\. Performance Engineering: Rendering at Scale**

The requirement to support "thousands of markers" at 60fps is the most significant technical risk. The Python Global Interpreter Lock (GIL) and the overhead of crossing the Python/C++ boundary in PySide6 can lead to performance degradation.

### **9.1 Optimizing the Scene Graph**

* Disable Spatial Indexing (NoIndex):  
  The QGraphicsScene uses a BSP tree to index items. When an item moves, the tree must be updated. For 1,000 moving items, this re-indexing is expensive.  
  * *Strategy:* For the layer containing moving units, call scene.setItemIndexMethod(QGraphicsScene.NoIndex). This disables the index. Collision detection becomes $O(N)$, but the frame update cost drops significantly.17  
* Item Coordinate Cache:  
  Complex markers (e.g., detailed SVG sigils) are expensive to paint.  
  * *Strategy:* Enable QGraphicsItem.ItemCoordinateCache. Qt renders the item to an offscreen pixmap and reuses it as long as the item's appearance doesn't change (even if it moves). This shifts the load from the CPU (painting) to the GPU (texture blitting).18

### **9.2 The OpenGL Viewport Solution**

Standard QWidget viewports perform rasterization on the CPU.

* *Strategy:* Set the QGraphicsView viewport to QOpenGLWidget.  
* *Benefit:* This unlocks hardware acceleration. Modern GPUs can handle the composition of thousands of textured quads (the cached markers) with ease, bypassing the CPU bottleneck of software rasterization.2

### **9.3 Level of Detail (LOD)**

Rendering full details for 1,000 units when zoomed out is wasteful.

* *Strategy:* Implement LOD in the paint() method.  
  * *High Zoom:* Draw full SVG marker.  
  * *Medium Zoom:* Draw simplified geometric shape.  
  * *Low Zoom:* Draw a single pixel or dot.  
* *Implementation:* Use QStyleOptionGraphicsItem.levelOfDetailFromTransform to determine the current zoom factor and branch the painting logic accordingly.19

### **9.4 Batching Updates**

To avoid 1,000 separate Python-to-C++ calls per frame:

* *Strategy:* Vectorize the math. Use numpy to calculate the positions of all 1,000 units for time $t$ in a single batch operation. While updating the QGraphicsItem positions still requires a loop, the heavy lifting of interpolation is done in optimized C code via numpy.

## ---

**10\. Advanced Features and Future Roadmap**

### **10.1 Ghost Trails (Motion History)**

Visualizing where an entity *was* is crucial for understanding battle maneuvers.

* **Implementation Options:**  
  1. *Particle System:* Spawn fading "ghost" items behind the marker. *Drawback:* Explodes the item count (1,000 units $\\times$ 10 ghosts \= 10,000 items).  
  2. *Path Stroking (Recommended):* Each marker maintains a QPolygonF of its last $N$ positions. The paint() method draws this polyline.  
* **Fading Effect:** Using a QLinearGradient brush along the path allows the trail to fade out smoothly without managing transparency for separate items. This is far more performant than particle systems in a QGraphicsView context.20

### **10.2 Visibility and Existence Intervals**

Entities that "die" or haven't been "born" must be hidden.

* **Optimization:** Simply calling hide() is not enough if the system still iterates over them.  
* **Active List:** Maintain a separate list of "Active Entities" for the current time window. Only update and render items in this list. When $t$ crosses an existence boundary ($t\_{start}$ or $t\_{end}$), move the entity between the "Active" and "Inactive" lists.21

## ---

**11\. Implementation Roadmap**

### **Phase 1: The Core Engine**

1. Implement TemporalEntity class and JSON schema.  
2. Build MasterClock and basic QTimer playback loop.  
3. Implement bisect based keyframe lookup.

### **Phase 2: The Viewer**

1. Set up QGraphicsScene with QOpenGLWidget viewport.  
2. Implement TemporalMarker item with setPos updates.  
3. Create the Timeline Widget with basic scrubbing.

### **Phase 3: Interaction & Recording**

1. Implement "Record" mode with mouse sampling.  
2. Add Motion Path visualization (QGraphicsPathItem).  
3. Implement node dragging and Bezier control points.

### **Phase 4: Optimization & Scale**

1. Profile with 1,000 items.  
2. Implement ItemCoordinateCache and NoIndex.  
3. Add Level of Detail (LOD) logic.

## ---

**12\. Conclusion**

The "Temporal Map Markers" feature is not only feasible but represents a transformative capability for ProjektKraken. While the "Abandoned" status suggests prior difficulties—likely related to performance scaling with naive implementations—the architectural approach outlined here addresses those specific bottlenecks. By leveraging the advanced features of the Qt Graphics View Framework (OpenGL integration, caching, indexing control) and adopting a robust data model based on binary search and stateless interpolation, the system can achieve the vision of a fluid, 4D narrative map. The shift from static coordinates to temporal functions allows ProjektKraken to tell stories of journeys, history, and conflict with a fidelity previously impossible in standard mapping tools.

## **13\. Comparison of Optimization Techniques**

| Technique | Implementation Effort | Performance Gain | Use Case |
| :---- | :---- | :---- | :---- |
| **Binary Search (Bisect)** | Low | High ($O(\\log N)$ lookup) | Playback/Scrubbing of long histories. |
| **OpenGL Viewport** | Medium | Very High (GPU Render) | Rendering 1000+ items; Battle Maneuvers. |
| **Item Coordinate Cache** | Low | High (Texture Blitting) | Complex SVG markers moving without scaling. |
| **NoIndex (BSP Bypass)** | Low | High (Update Speed) | Constant movement of many items. |
| **LOD (Level of Detail)** | Medium | Medium (Paint reduction) | Viewing the whole world map (Zoomed out). |

This table summarizes the critical technical decisions required to ensure the "Battle Maneuvers" use case runs at the target 60fps. By systematically applying these optimizations, the Python/Qt architecture serves as a robust foundation for the next generation of digital storytelling tools.

#### **Works cited**

1. QGraphics vector graphics interfaces with Python and PySide6, accessed on January 5, 2026, [https://www.pythonguis.com/tutorials/pyside6-qgraphics-vector-graphics/](https://www.pythonguis.com/tutorials/pyside6-qgraphics-vector-graphics/)  
2. Thread: QGraphicsView, OpenGL and repainting/updating \- Qt Centre, accessed on January 5, 2026, [https://qtcentre.org/threads/18025-QGraphicsView-OpenGL-and-repainting-updating](https://qtcentre.org/threads/18025-QGraphicsView-OpenGL-and-repainting-updating)  
3. How to move around 1000 items in a QGraphicsScene without blocking the UI, accessed on January 5, 2026, [https://stackoverflow.com/questions/18397603/how-to-move-around-1000-items-in-a-qgraphicsscene-without-blocking-the-ui](https://stackoverflow.com/questions/18397603/how-to-move-around-1000-items-in-a-qgraphicsscene-without-blocking-the-ui)  
4. bisect — Array bisection algorithm — Python 3.14.2 documentation, accessed on January 5, 2026, [https://docs.python.org/3/library/bisect.html](https://docs.python.org/3/library/bisect.html)  
5. Efficient Python Bisect for Sorted List Operations (2025 Guide) | by Devin Rosario, accessed on January 5, 2026, [https://python.plainenglish.io/efficient-python-bisect-for-sorted-list-operations-2025-guide-dc61bb8ad23c](https://python.plainenglish.io/efficient-python-bisect-for-sorted-list-operations-2025-guide-dc61bb8ad23c)  
6. QGraphicsItem — PySide v1.0.7 documentation, accessed on January 5, 2026, [https://srinikom.github.io/pyside-docs/PySide/QtGui/QGraphicsItem.html](https://srinikom.github.io/pyside-docs/PySide/QtGui/QGraphicsItem.html)  
7. Graphics View Framework \- Qt for Python, accessed on January 5, 2026, [https://doc.qt.io/qtforpython-6.5/overviews/graphicsview.html](https://doc.qt.io/qtforpython-6.5/overviews/graphicsview.html)  
8. Understanding paintEvent() \- Qt Forum, accessed on January 5, 2026, [https://forum.qt.io/topic/86500/understanding-paintevent](https://forum.qt.io/topic/86500/understanding-paintevent)  
9. isinsuatay/Cubic-Bezier-With-Python \- GitHub, accessed on January 5, 2026, [https://github.com/isinsuatay/Cubic-Bezier-With-Python](https://github.com/isinsuatay/Cubic-Bezier-With-Python)  
10. PySide6.QtGui.QPolygonF \- Qt for Python, accessed on January 5, 2026, [https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPolygonF.html](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPolygonF.html)  
11. custom widget with progressbar (timeline animation on it) Qt c++ \- Stack Overflow, accessed on January 5, 2026, [https://stackoverflow.com/questions/74510720/custom-widget-with-progressbar-timeline-animation-on-it-qt-c](https://stackoverflow.com/questions/74510720/custom-widget-with-progressbar-timeline-animation-on-it-qt-c)  
12. Zooming function on a QWidget \- qt \- Stack Overflow, accessed on January 5, 2026, [https://stackoverflow.com/questions/6650219/zooming-function-on-a-qwidget](https://stackoverflow.com/questions/6650219/zooming-function-on-a-qwidget)  
13. Qt-Widgets/task-timeline-date-time-graph-status \- GitHub, accessed on January 5, 2026, [https://github.com/Qt-Widgets/task-timeline-date-time-graph-status](https://github.com/Qt-Widgets/task-timeline-date-time-graph-status)  
14. PySide6.QtWidgets.QGraphicsSceneMouseEvent \- Qt for Python, accessed on January 5, 2026, [https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsSceneMouseEvent.html](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsSceneMouseEvent.html)  
15. How to properly smooth a QPainterPath? \- Stack Overflow, accessed on January 5, 2026, [https://stackoverflow.com/questions/78375558/how-to-properly-smooth-a-qpainterpath](https://stackoverflow.com/questions/78375558/how-to-properly-smooth-a-qpainterpath)  
16. PyQt QPainter Animate Path Strokes \- YouTube, accessed on January 5, 2026, [https://www.youtube.com/watch?v=637wO83IXMk](https://www.youtube.com/watch?v=637wO83IXMk)  
17. QGraphicsScene performance (200000 static items and 1 moving) \- Qt Centre, accessed on January 5, 2026, [https://qtcentre.org/threads/38209-QGraphicsScene-performance-(200000-static-items-and-1-moving)](https://qtcentre.org/threads/38209-QGraphicsScene-performance-\(200000-static-items-and-1-moving\))  
18. How to optimize QGraphicsView's performance? \- Stack Overflow, accessed on January 5, 2026, [https://stackoverflow.com/questions/43826317/how-to-optimize-qgraphicsviews-performance](https://stackoverflow.com/questions/43826317/how-to-optimize-qgraphicsviews-performance)  
19. How to improve QGraphicsView performance in a 2D static scene with many items? (no way to solve it?) | Qt Forum, accessed on January 5, 2026, [https://forum.qt.io/topic/3325/how-to-improve-qgraphicsview-performance-in-a-2d-static-scene-with-many-items-no-way-to-solve-it](https://forum.qt.io/topic/3325/how-to-improve-qgraphicsview-performance-in-a-2d-static-scene-with-many-items-no-way-to-solve-it)  
20. QPolygonF — PySide v1.0.7 documentation, accessed on January 5, 2026, [https://srinikom.github.io/pyside-docs/PySide/QtGui/QPolygonF.html](https://srinikom.github.io/pyside-docs/PySide/QtGui/QPolygonF.html)  
21. python \- PyQt6 \- handle events on QGraphicsItem \- Stack Overflow, accessed on January 5, 2026, [https://stackoverflow.com/questions/78610243/pyqt6-handle-events-on-qgraphicsitem](https://stackoverflow.com/questions/78610243/pyqt6-handle-events-on-qgraphicsitem)