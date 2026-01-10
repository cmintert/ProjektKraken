# **Temporal Geospatial Architectures: Engineering High-Performance Animation Systems in PySide6 with Hybrid SQLite Storage**

## **1\. Architectural Convergence in Temporal GIS**

The contemporary landscape of Geographic Information Systems (GIS) is undergoing a fundamental shift from static cartography to dynamic, temporal visualization. This transition necessitates a re-evaluation of traditional database architectures and rendering pipelines, particularly when targeting desktop environments using Python and Qt. Your objective—to construct a map application capable of keyframe-based animation using a hybrid SQLite database—places the project at the bleeding edge of "Post-Relational" geospatial engineering. This report serves as a comprehensive architectural blueprint, deconstructing the complexities of storing, interpolating, and rendering moving features (trajectories) within a PySide6 environment.  
The challenge is multi-dimensional. It requires reconciling the distinct requirements of storage efficiency, query latency, and rendering frame rates. A hybrid SQLite approach, where relational rigour meets the schema flexibility of JSON, offers a potent solution but introduces specific pitfalls regarding indexing and serialization overhead. Furthermore, the user experience (UX) of *editing* time—translating abstract temporal qualities into tangible, manipulable interface elements—requires a sophisticated understanding of animation principles derived from computer graphics rather than traditional GIS forms.  
We define "Moving Features" not merely as points with timestamps, but as continuous geometries—prisms in a 4D space-time cube—that require mathematical interpolation to render at arbitrary time t. The analysis that follows integrates rigorous database optimization strategies, computational geometry algorithms, and advanced Qt widget engineering to deliver a system that is both performant and intuitive.

## **2\. The Persistence Layer: Hybrid SQLite Optimization**

The decision to utilize a hybrid approach in SQLite—storing core entity metadata in relational columns and complex trajectory data in JSON documents—aligns with modern "Multi-Model" database paradigms. This architecture allows for the high-speed retrieval of entity lists while preserving the structural integrity of variable-length time-series data. However, the implementation details determine whether this system scales to thousands of features or falters under the weight of parsing overhead.

### **2.1 The Mechanics of SQLite JSONB and Hybrid Storage**

Traditionally, geospatial trajectories were modeled in Third Normal Form (3NF), where a parent Track table linked to a child Waypoints table containing millions of rows of (track\_id, timestamp, lat, lon). While theoretically sound, this model is disastrous for animation performance. To render a single frame at time t, the database engine must perform massive JOIN operations and scan indexes across millions of rows to find the two points bracketing t for every active entity.  
The hybrid approach encapsulates the entire trajectory—the sequence of spatiotemporal coordinates—into a single row within the features table. This dramatically reduces the "Seek" penalty of the disk I/O. As of SQLite version 3.45, the introduction of **JSONB**—a binary encoding of JSON—transforms this pattern from a convenient hack into a high-performance standard. JSONB eliminates the parse-on-read penalty associated with text-based JSON, allowing the application to load complex trajectories directly into memory buffers with minimal serialization overhead.  
Research indicates that storing trajectory data as a JSON array of arrays—\[\[t1, x1, y1\], \[t2, x2, y2\]\]—is superior to arrays of objects for storage density and parsing speed, although it sacrifices some self-describing clarity. In a Python 3.13 environment, leveraging orjson or standard json libraries to deserialize these binary blobs is significantly faster than iterating cursor results from a normalized table.

### **2.2 Generated Columns: The Indexing Strategy**

The primary critique of storing JSON in databases is the inability to index values buried within the document. In a temporal map, the system must efficiently answer the query: *"Which features are active between 12:00 and 12:05?"* If the start and end times are locked inside the JSON blob, the database must perform a full table scan, parsing every row to extract the timestamps. This is O(N) complexity, which is unacceptable for real-time applications.  
The solution lies in **Virtual Generated Columns**. SQLite allows the definition of columns that are mathematically derived from other columns. By creating virtual columns for start\_time, end\_time, and the spatial Bounding Box (min/max lat/lon), we project the internal JSON data into the relational realm where it can be indexed using standard B-Trees or R-Trees.

| Column Type | Description | Storage Impact | Performance Impact |
| :---- | :---- | :---- | :---- |
| **Standard** | Static data (ID, Name, Type) | Normal | Fast Indexing |
| **JSON/JSONB** | The Trajectory Blob | High (stores full path) | Slow if queried directly |
| **Stored Generated** | Computes value on INSERT/UPDATE | High (duplicates data) | Ultra-fast Read, Slower Write |
| **Virtual Generated** | Computes value on READ | Zero (CPU only) | Fast Read (if indexed), Fast Write |

**Recommended Schema Implementation:**  
The following SQL Data Definition Language (DDL) demonstrates the optimal structure. It extracts the temporal bounds from the JSON array (assuming the first element is start and the last is end) and creates a compound index.  
`CREATE TABLE moving_features (`  
    `id INTEGER PRIMARY KEY,`  
    `name TEXT NOT NULL,`  
    `-- Core Trajectory Data: Stored as JSONB for performance`  
    `-- Structure: {"coordinates": [[t, x, y],...], "properties": {...}}`  
    `trajectory_data BLOB,`   
      
    `-- VIRTUAL COLUMNS for Indexing`  
    `-- We extract the first timestamp from the coordinates array`  
    `start_time INTEGER GENERATED ALWAYS AS (`  
        `json_extract(trajectory_data, '$.coordinates')`  
    `) VIRTUAL,`  
      
    `-- We extract the last timestamp using the array length`  
    `end_time INTEGER GENERATED ALWAYS AS (`  
        `json_extract(trajectory_data, '$.coordinates[#-1]')`  
    `) VIRTUAL,`

    `-- Spatial Bounds for Viewport Queries`  
    `min_lon REAL GENERATED ALWAYS AS (json_extract(trajectory_data, '$.bbox')) VIRTUAL,`  
    `min_lat REAL GENERATED ALWAYS AS (json_extract(trajectory_data, '$.bbox')) VIRTUAL,`  
    `max_lon REAL GENERATED ALWAYS AS (json_extract(trajectory_data, '$.bbox')) VIRTUAL,`  
    `max_lat REAL GENERATED ALWAYS AS (json_extract(trajectory_data, '$.bbox')) VIRTUAL`  
`);`

`-- Compound Index for Temporal Indexing`  
`CREATE INDEX idx_time_bounds ON moving_features(start_time, end_time);`

`-- Spatial Index (approximated with standard index, or use R-Tree extension)`  
`CREATE INDEX idx_spatial_bounds ON moving_features(min_lon, max_lon, min_lat, max_lat);`

This architecture allows the PySide6 application to execute "Time Slice" queries instantly. When the playhead moves, the application queries the DB for WHERE end\_time \>= current\_time AND start\_time \<= current\_time. Because these values are exposed as indexed virtual columns, SQLite performs a rapid index seek rather than scanning the blobs.

### **2.3 OGC Moving Features Compliance and GeoPackage**

While flexibility is a virtue, adhering to established standards ensures interoperability and long-term maintainability. The **Open Geospatial Consortium (OGC) Moving Features** standard provides the rigorous conceptual framework required for this application. It defines the "Moving Feature" not just as a path, but as a feature with *temporal geometry* and *temporal properties*.  
The application should adopt the **MF-JSON** (Moving Features JSON) encoding specification for the content of the JSON columns. MF-JSON explicitly handles the complexities of time-varying attributes—for instance, a vehicle that changes color or speed classification over time.  
**MF-JSON Structure Recommendation:**  
`{`  
  `"type": "MovingFeature",`  
  `"temporalGeometry": {`  
    `"type": "MovingPoint",`  
    `"datetimes":,`  
    `"coordinates": [[10.0, 20.0], [10.1, 20.2]],`  
    `"interpolation": "Linear"`  
  `},`  
  `"temporalProperties":,`  
      `"speed": {"values": , "interpolation": "Stepwise"}`  
    `}`  
  `]`  
`}`

Adopting this standard allows the application to utilize libraries like **MovingPandas** for heavy lifting (import/export) while maintaining a custom, lightweight rendering loop. Furthermore, because SQLite is the underlying container for the **OGC GeoPackage** standard, this hybrid table can technically coexist within a valid.gpkg file , allowing the data to be opened (as static tables) in GIS software like QGIS, provided the gpkg\_geometry\_columns are managed correctly.  
For the purpose of an editing application, the strict OGC separation of datetimes and coordinates into parallel arrays is efficient for storage but risky for manual editing (index misalignment). However, it is the standard. If the user interface provides a robust abstraction layer, this risk is mitigated.

### **2.4 Transaction Management and Batching**

A critical performance pitfall in SQLite interactions from Python is the handling of write operations during editing. If the user drags a keyframe on the timeline, generating hundreds of "move" events, and the application attempts to commit each change individually, performance will collapse. SQLite's default behavior waits for the filesystem flush (fsync) on every transaction, limiting throughput to approximately 50 transactions per second on rotational media, or slightly higher on SSDs.  
**Best Practice: The "Dirty" Buffer Strategy**

1. **In-Memory Manipulation:** All interactive editing happens on Python objects (e.g., a Trajectory class instance).  
2. **Debounced Saves:** The application should implement a "dirty" flag. Writes to the database are triggered either by an explicit "Save" action, an auto-save timer (e.g., every 30 seconds), or when the user deselects the active feature.  
3. **Explicit Transactions:** When saving, wrap all updates in a single transaction block (BEGIN TRANSACTION;... COMMIT;). This allows SQLite to commit thousands of updates in milliseconds.  
4. **WAL Mode:** Enable Write-Ahead Logging (PRAGMA journal\_mode=WAL;). This allows readers (the rendering thread) to access the database concurrently with the writer (the auto-save thread) without blocking, ensuring that the animation playback doesn't stutter during a background save operation.

## **3\. Computational Geometry: Interpolation and Trajectory Logic**

The core value proposition of the application is the ability to determine the state of a feature at any arbitrary time t. Since the database stores discrete samples (t\_0, p\_0), (t\_1, p\_1) \\dots, the application must implement a robust interpolation engine.

### **3.1 The Mathematics of Interpolation**

The choice of interpolation algorithm dictates the visual quality and geospatial accuracy of the animation.

#### **3.1.1 Linear vs. Spherical Interpolation**

For standard projected coordinate systems (like Web Mercator, EPSG:3857), Linear Interpolation (LERP) is often sufficient for visual smoothness over short distances. The formula for a point P at time t between t\_0 and t\_1 is:  
However, for trajectories covering significant global distances (e.g., flight paths), LERP on a projected plane results in visual artifacts where the speed appears to vary, and the path deviates from the Great Circle route. In these cases, **Spherical Linear Interpolation (SLERP)** is required. SLERP interpolates the angle between two vectors on a sphere, ensuring constant angular velocity and a true geodesic path.  
While SLERP is computationally more expensive, Python's scipy.spatial.transform.Rotation or dedicated geospatial libraries handle this efficiently via quaternions. For a generic map editor, providing a toggle between "Linear" (screen space) and "Geodesic" (spherical space) interpolation is a best practice.

#### **3.1.2 Vectorized Calculation with NumPy**

A common performance pitfall is implementing the interpolation logic using native Python loops. Python's interpreter overhead is significant when calculating positions for thousands of markers 60 times per second.  
The architectural solution is **Vectorization**. Instead of storing keyframes as lists of objects, store them as **NumPy arrays**. This allows the use of np.interp, which delegates the calculation to optimized C code.  
`# Vectorized Interpolation Concept`  
`import numpy as np`

`class VectorizedTrajectory:`  
    `def __init__(self, times, lats, lons):`  
        `self.times = np.array(times) # Sorted timestamps`  
        `self.lats = np.array(lats)`  
        `self.lons = np.array(lons)`

    `def get_position_at(self, t):`  
        `# np.interp performs linear interpolation efficiently in C`  
        `lat = np.interp(t, self.times, self.lats)`  
        `lon = np.interp(t, self.times, self.lons)`  
        `return lat, lon`

This approach is orders of magnitude faster than iterating through a list of dictionaries in Python, leaving more CPU time for the Qt rendering loop.

### **3.2 Integration with MovingPandas**

Rather than reinventing the wheel, the application logic should leverage **MovingPandas**. MovingPandas is a Python library specifically designed for trajectory analysis. It sits on top of GeoPandas and Pandas, providing robust data structures for trajectory collections.  
MovingPandas implements the get\_position\_at(datetime) method, handling the underlying interpolation complexities. It also supports trajectory generalization and cleaning (removing outliers). However, a caveat exists: MovingPandas is heavy. For the real-time *rendering loop* (60 FPS), calling a complex MovingPandas method might be too slow due to Pandas' indexing overhead.  
**Recommendation:** Use MovingPandas for the "Edit Mode" (loading data, cleaning, splitting tracks, analysis) and for exporting/importing MF-JSON. For the "Playback Mode," compile the validated MovingPandas trajectory into the lightweight NumPy structure described in 3.1.2 for raw speed.

### **3.3 Trajectory Simplification and Topology**

User-generated data (e.g., recorded mouse movements or raw GPS logs) often contains excessive density—thousands of points for a straight line. This bloats the database and slows down the np.interp search.  
The **Ramer-Douglas-Peucker (RDP)** algorithm is essential for optimizing this data. RDP decimates the curve, removing points that do not contribute significantly to the shape (based on a user-defined epsilon \\epsilon threshold).  
**The Topology Pitfall:** Aggressive simplification can alter the topological relationship between features (e.g., a path that went around a building might now cut through it). When applying RDP, one must be careful with the epsilon value. Libraries like shapely offer simplify(preserve\_topology=True), which is slower but safer.  
For an editor, the "User Friendliest Way" to handle this is to run RDP automatically on *import* or *recording* completion, reducing the input noise to a manageable set of "Keyframes" that the user can then manually tweak.

## **4\. The Visualization Layer: PySide6 Architecture**

The choice of widget for rendering the map determines the ceiling of the application's performance.

### **4.1 Comparison of Rendering Engines**

| Feature | QWebEngineView (Leaflet/MapLibre) | QGraphicsView (Native Qt) | QOpenGLWidget (Direct GL) |
| :---- | :---- | :---- | :---- |
| **Map Fidelity** | **High** (Standard Web Tiles, Styles) | Moderate (Requires custom tile loader) | Low (Requires custom engine) |
| **Animation Perf.** | Low (IPC Latency) | **High** (Native C++ Scene Graph) | **Extreme** (GPU Accelerated) |
| **Python Control** | Difficult (Async JS Bridge) | **Direct** (Python Objects) | Difficult (Raw Matrices) |
| **Editing UX** | Poor (HTML/DOM limitations) | **Excellent** (Native Drag/Drop events) | Moderate (Custom Hit testing) |

#### **4.1.1 The Latency of QWebEngineView**

Many developers default to QWebEngineView to load Leaflet or MapLibre GL because it is easy to get a map on screen. However, this creates a "Split Brain" architecture. The map lives in a Chromium process, while the data lives in the Python process. To animate a marker, Python must send a signal over a WebSocket or runJavaScript channel. This introduces asynchronous latency. Scrubbing a timeline in PySide6 and waiting for the WebEngine to update results in a "muddy," disconnected feel. High-performance animation in WebEngine requires moving the *entire* logic loop into JavaScript, relegating Python to a simple data server.

#### **4.1.2 The Superiority of QGraphicsView for Editors**

For a keyframe editor where interaction (clicking, dragging, selecting) is paramount, **QGraphicsView** is the superior architectural choice. The Graphics View Framework uses a BSP (Binary Space Partitioning) tree to manage millions of items efficiently.

* **Architecture:** The Map is a QGraphicsScene. The Map Tiles are QGraphicsPixmapItems loaded in background threads. The Moving Features are QGraphicsPathItems (for the track) and QGraphicsItems (for the marker).  
* **Coordinate System:** The application must implement a transformation class to map Longitude/Latitude to the Scene's Cartesian coordinate system (usually Web Mercator).  
* **Performance:** QGraphicsView can easily handle thousands of moving items at 60 FPS if the viewport is set to use OpenGL acceleration (view.setViewport(QOpenGLWidget())).

### **4.2 The Animation Loop**

Do not use time.sleep(). The animation must be driven by the Qt Event Loop to keep the GUI responsive.  
**The "Pulse" Mechanism:**

1. **AnimationController:** A class owning a QElapsedTimer and a QTimer.  
2. **The Tick:** Every 16ms (target 60 FPS), the QTimer fires. The Controller calculates the new current\_time based on the elapsed real time multiplied by the playback\_speed.  
3. **Signal Emission:** A signal timeChanged(float timestamp) is emitted.  
4. **Observer Update:** All MapMarker objects connected to this signal receive the timestamp, call their internal trajectory.get\_position\_at(t) method (using the NumPy logic), and update their setPos(x, y) on the scene.

This "Push" architecture ensures that the visual state is always synchronized with the internal clock.

## **5\. User Experience (UX): Designing for Temporal Entry**

Entering temporal data is cognitively demanding. Users understand space intuitively, but "time" requires abstraction. The "user friendliest way" to enter these qualities is to hide the raw timestamps behind visual metaphors and direct manipulation.

### **5.1 The Timeline Widget ("Dope Sheet")**

A custom widget, docked at the bottom of the screen, is essential. It should borrow the "Dope Sheet" paradigm from animation software (Blender, After Effects).  
**Components of the Timeline:**

1. **The Ruler:** A horizontal axis representing time. It must support zooming (scroll wheel) to change the scale from "Years" down to "Milliseconds".  
2. **Tracks:** Each Moving Feature has a horizontal track.  
3. **Keyframes (Diamonds):** Discrete points in time where the user has explicitly defined a position.  
4. **Interpolation Curves (Lines):** Visual lines connecting keyframes. Clicking the line could open a dialog to change the interpolation type (Linear vs. Ease-In/Ease-Out).

**Interaction Logic:**

* **Scrubbing:** The user drags a vertical "Playhead" line. This updates the map in real-time (ghosting).  
* **Retiming:** The user can drag a Keyframe diamond left or right to change *when* an event happens without changing *where* it happens. This is the distinct advantage of the separated Timeline view over strictly map-based editing.

### **5.2 Input Methods: "Auto-Keying" vs. Path Drawing**

How does a user create a trajectory from scratch?  
**Method A: Auto-Keying (The Animator's Approach)** This is the most intuitive for precise control.

1. User scrubs Playhead to Time T\_0. Moves Marker to Location A. System records Keyframe (T\_0, A).  
2. User scrubs Playhead to Time T\_1. Moves Marker to Location B. System records Keyframe (T\_1, B). *Insight:* This separates the dimensions. The user focuses on "When" first, then "Where."

**Method B: Path Drawing (The GIS Approach)** Better for defining routes.

1. User draws a polyline on the map.  
2. System prompts: "Start Time?" and "Duration/Speed?".  
3. System calculates the timestamps for each vertex assuming constant speed. *Refinement:* To make this "user friendly," allow the user to draw the path *gesturally* with the mouse while the clock runs (Live Recording). The system records the mouse position and the timestamp of the mouse event simultaneously. This captures natural acceleration and deceleration. Post-processing with RDP simplification is required here to reduce the jittery mouse input into clean keyframes.

### **5.3 Visual Feedback: Onion Skinning**

To assist in editing, the application should implement **Onion Skinning** (Ghosting). When a marker is selected, render its position at t-1s, t-2s, etc., with decreasing opacity. This allows the user to visualize the velocity and direction of the movement even when the animation is paused. In QGraphicsView, this is achieved by creating temporary QGraphicsItem clones with reduced alpha channels.

## **6\. Best Practices and Pitfalls Summary**

### **6.1 Best Practices**

* **Use JSONB:** Leverage SQLite's binary JSON format for storage efficiency.  
* **Virtual Columns:** Always expose temporal bounds (start, end) and spatial bounds (bbox) as Virtual Generated Columns for indexing.  
* **Vectorization:** Use NumPy for interpolation calculations to avoid the Python loop overhead.  
* **Native Rendering:** Prefer QGraphicsView with OpenGL acceleration for the editor interface to ensure low-latency interaction.  
* **Batch Writes:** Use transactions and WAL mode to prevent UI freezing during saves.

### **6.2 Pitfalls to Avoid**

* **Deep Inheritance in JSON:** Avoid deeply nested JSON structures for the core trajectory arrays. Keep the coordinate arrays flat or shallow to minimize extraction cost.  
* **QWebEngineView for Editing:** Avoid using web widgets for the core editing loop; the IPC latency will degrade the "feel" of the application.  
* **Blocking the Main Thread:** Do not perform database fetches or complex path simplifications on the GUI thread. Use QThread or QRunnable for all I/O operations.  
* **Timezone Confusion:** Store all timestamps in the database as UTC (Unix Epoch or ISO 8601). Only convert to local time for the Timeline Widget display labels.

## **7\. Implementation Roadmap**

1. **Phase 1: Database & Model:** Define the SQLite schema with JSONB and Virtual Columns. Implement the Python Trajectory class with NumPy-based get\_position\_at(t).  
2. **Phase 2: Visualization Engine:** Build the QGraphicsView map with a background Tile Loader. Implement the coordinate transform logic.  
3. **Phase 3: Animation Loop:** Implement the AnimationController (Timer) and connect it to the Map Markers.  
4. **Phase 4: Timeline UI:** Create the custom QWidget for the Dope Sheet. Implement the "Scrubbing" logic.  
5. **Phase 5: Editing Tools:** Implement "Auto-Key" and "Path Draw" modes with RDP simplification.

This architecture provides a robust, scalable foundation for a temporal map editor, balancing the flexibility of hybrid data structures with the performance requirements of real-time animation.

#### **Works cited**

1\. Using JSON instead of normalized data, is this approach correct? \- Stack Overflow, https://stackoverflow.com/questions/12970831/using-json-instead-of-normalized-data-is-this-approach-correct 2\. JSON and Virtual Columns in SQLite \- Hacker News, https://news.ycombinator.com/item?id=31396578 3\. Is it good to use SQL function like JSON\_EXTRACT for large number of data, https://stackoverflow.com/questions/53497108/is-it-good-to-use-sql-function-like-json-extract-for-large-number-of-data 4\. SQLite Boosts JSON Query Speed with Virtual Generated Columns \- WebProNews, https://www.webpronews.com/sqlite-boosts-json-query-speed-with-virtual-generated-columns/ 5\. OGC Moving Features Encoding Extension \- JSON, https://docs.ogc.org/is/19-045r3/19-045r3.html 6\. opengeospatial/movingfeatures: public repo for Moving Features \- GitHub, https://github.com/opengeospatial/movingfeatures 7\. OGC Moving Features Encoding Extension \- JSON \- GitHub Pages, https://ksookim.github.io/mf-json/ 8\. OGC API \- Moving Features \- Part 1: Core, https://docs.ogc.org/is/22-003r3/22-003r3.html 9\. OGC GeoPackage Related Tables Extension, https://docs.ogc.org/is/18-000/18-000.html 10\. OGC® GeoPackage Encoding Standard \- with Corrigendum, https://www.geopackage.org/spec121/ 11\. Best practices for SQLite performance | App quality \- Android Developers, https://developer.android.com/topic/performance/sqlite-performance-best-practices 12\. Best Practices for Managing Schema, Indexes, and Storage in SQLite for Data Engineering | by firman brilian | Medium, https://medium.com/@firmanbrilian/best-practices-for-managing-schema-indexes-and-storage-in-sqlite-for-data-engineering-c74f71056518 13\. How to use linear interpolation estimate current position between two Geo Coordinates?, https://stackoverflow.com/questions/1739019/how-to-use-linear-interpolation-estimate-current-position-between-two-geo-coordi 14\. Lerp vs Slerp \- Tibor Stanko, https://tiborstanko.sk/lerp-vs-slerp.html 15\. Interpolation (scipy.interpolate) — SciPy v1.16.2 Manual, https://docs.scipy.org/doc/scipy/reference/interpolate.html 16\. Trajectory interpolation at multiple time stamps · Issue \#213 \- GitHub, https://github.com/anitagraser/movingpandas/issues/213 17\. movingpandas/movingpandas: Movement trajectory classes and functions built on top of GeoPandas \- GitHub, https://github.com/movingpandas/movingpandas 18\. movingpandas/movingpandas/trajectory.py at main \- GitHub, https://github.com/anitagraser/movingpandas/blob/master/movingpandas/trajectory.py 19\. movingpandas.TrajectoryCollection.to\_mf\_json, https://movingpandas.readthedocs.io/en/main/api/api/movingpandas.TrajectoryCollection.to\_mf\_json.html 20\. New MovingPandas tutorial: taking OGC Moving Features full circle with MF-JSON, https://anitagraser.com/2024/07/08/new-movingpandas-tutorial-taking-ogc-moving-features-full-circle-with-mf-json/ 21\. Ramer–Douglas–Peucker algorithm \- Wikipedia, https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker\_algorithm 22\. Shapely's simplify won't simplify any more \- GIS StackExchange, https://gis.stackexchange.com/questions/120004/shapelys-simplify-wont-simplify-any-more 23\. simplify() can return invalid geometries (even with preserve\_topology=True) \#2165 \- GitHub, https://github.com/shapely/shapely/issues/2165 24\. Why does PyQt6 make Leaflet so slow with 1000 markers? \- Stack Overflow, https://stackoverflow.com/questions/75976663/why-does-pyqt6-make-leaflet-so-slow-with-1000-markers 25\. QtWebEngine performance is very poor \- Qt Forum, https://forum.qt.io/topic/154895/qtwebengine-performance-is-very-poor 26\. 0n3byt3/Leaflet.MarkerPlayer: A plug-in for animating marker along polyline with ability to get/set progress. \- GitHub, https://github.com/0n3byt3/Leaflet.MarkerPlayer 27\. QWebEngineView and leaflet.js slow performance \- Stack Overflow, https://stackoverflow.com/questions/74914600/qwebengineview-and-leaflet-js-slow-performance 28\. QGraphics vector graphics interfaces with Python and PyQt6, https://www.pythonguis.com/tutorials/pyqt6-qgraphics-vector-graphics/ 29\. QGeoView \- Qt/C \++ widget for visualizing geographic data, https://forum.qt.io/topic/94771/qgeoview-qt-c-widget-for-visualizing-geographic-data 30\. PySide6.QtOpenGLWidgets.QOpenGLWidget \- Qt for Python, https://doc.qt.io/qtforpython-6/PySide6/QtOpenGLWidgets/QOpenGLWidget.html 31\. hasielhassan/QtEditorialTimelineWidget: Non linear editor timeline widget for python Qt bindings \- GitHub, https://github.com/hasielhassan/QtEditorialTimelineWidget 32\. Use the Animation Timeline pane—ArcGIS Pro | Documentation, https://pro.arcgis.com/en/pro-app/latest/help/mapping/animation/animation-timeline-pane.htm 33\. How do I achieve smooth mouse movement on turns in Pyautogui? \- Stack Overflow, https://stackoverflow.com/questions/76861629/how-do-i-achieve-smooth-mouse-movement-on-turns-in-pyautogui 34\. Realistic Mouse Movement from A to B : r/learnpython \- Reddit, https://www.reddit.com/r/learnpython/comments/c49cos/realistic\_mouse\_movement\_from\_a\_to\_b/