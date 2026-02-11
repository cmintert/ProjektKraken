# Research: Network Analysis & QGIS Comparison

## Executive Summary
Network analysis (routing, flow, centrality) requires a **Graph Topology** (Nodes & Edges), which is fundamentally different from the **Vector Graphics** (Points & Lines) currently used in ProjektKraken.

To perform analysis with **NetworkX**, ProjektKraken's map data would need to be converted into a mathematical graph. QGIS handles this by enforcing **Topological Rules** on its vector data, ensuring that lines connect exactly at vertices.

## 1. QGIS Data Model
QGIS uses a **Spatial RDBMS** approach (often via PostGIS or SpatiaLite):
- **Features**: Stored as Geometry (Point, LineString, Polygon).
- **Topology**: Not strictly enforced by default, but managed via **Topology Rules**:
    - "Must not have dangles" (lines must connect).
    - "Must not intersect" (lines must split at intersections).
- **Analysis**: When running a route, QGIS converts valid vector geometry into a graph on-the-fly or uses a persistent topology layer.

## 2. NetworkX Integration
**NetworkX** is a pure Python graph library. It does not natively understand "geometry" or "maps", only "Nodes" (any hashable object) and "Edges" (tuples of nodes).

**To analyze ProjektKraken geometry in NetworkX:**
1.  **Extract Coordinates**: Convert `PathItem` vertices into tuples `(x, y)`.
2.  **Define Nodes**: The start and end points of every line segment become Nodes.
3.  **Define Edges**: The line segments themselves become Edges, with `weight = length`.
4.  **Handle Intersections ("Noding")**:
    - *Crucial Step*: If two roads cross but don't share a vertex (a "bridge" visually), NetworkX won't know they connect.
    - We would need an algorithm to detect line-line intersections and inject new Nodes at those points (effectively splitting the lines).

## 3. Feasibility for ProjektKraken
YES, using NetworkX is feasible and powerful, but it requires a **"Graph Builder" Service**:
- **Input**: List of `PathItem` entities (Roads, Rivers).
- **Process**:
    1.  Snap nearby vertices together (tolerance threshold).
    2.  Split lines at intersections (noding).
    3.  Build `nx.Graph`.
- **Output**: Shortest paths, centrality, etc., which can be rendered back onto the map.

## Comparison
| Feature | QGIS / PostGIS | NetworkX (Python) | ProjektKraken (Current) |
| :--- | :--- | :--- | :--- |
| **Data Structure** | Spatial Vectors + Topology | Adjacency Matrix / Edge List | Visual Lists of Points |
| **Connectivity** | Enforced by rules/tools | Explicitly defined by edges | Visual overlap only |
| **Routing** | Native (pgRouting, QNEAT3) | Dijkstra / A* (Fast) | None |
| **Complexity** | High (Full GIS stack) | Medium (Code-based) | Low (Drawing only) |

## Recommendation
If advanced analysis is a goal:
1.  **Don't** change the storage model (keep it simple JSON/SQL).
2.  **Do** build an on-demand `GraphService` that converts the active map's paths into a NetworkX graph for calculation.
3.  Use **snapping** during drawing to ensure valid topology (users must click *exactly* on the intersection for the graph to connect).

## 4. Prerequisite: Robust Snapping
Your intuition is correct: **Snapping is the foundation.**
Without exact coordinate matches, the graph will be disconnected.

### Current Limitations
The current `_snap_to_nearby_vertex` only snaps to **vertices of the feature being edited**. It cannot connect a new road to an *existing* road.

### Required Snapping Features
1.  **Global Vertex Snapping**: Snap to endpoints of *other* PathItems.
2.  **Edge Snapping**: Snap to the nearest point *along* a line segment (essential for T-junctions).
3.  **Visual Feedback**: Show a "magnet" or "node" indicator when snapping is active.

**Implementation Strategy**:
- Maintain a **KD-Tree** or **Grid Index** of all map vertices for fast O(log n) lookups during mouse moves.
- During drawing, query this index to find the nearest snap target within `MAP_SNAP_RADIUS_PX`.
