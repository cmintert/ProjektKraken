# Concept: Temporal Map Markers

**Status**: Proposal / Abandoned Implementation (Jan 2026)
**Goal**: Visualize the movement and state of entities on a map over time.

## 1. The Vision

In storytelling and world-building, entities (characters, armies, items) rarely stay in one place. "Temporal Maps" allows ProjektKraken to represent **Journeys** and **Timelines** visually on the map.

Instead of a marker being fixed at `(x, y)`, a marker has a position `(x, y)` relative to a global **Time** `t`.

### Core Use Cases
-   **Tracking Journeys**: Show the path of the "One Ring" across Middle-earth.
-   **Historical Borders**: Show how kingdom borders shift over centuries.
-   **Battle Maneuvers**: Animate troop movements during a specific battle event.

---

## 2. Key Features

### Global Timeline
-   A master "Playhead" controls the current time `t` for the entire application.
-   As `t` changes, the map updates to show the state of the world at that moment.

### Temporal Markers
-   Markers have "Keyframes": discrete points in time with specific attributes.
-   **Position Keyframes**: `At t=0, pos=(10,10)`. `At t=100, pos=(50,50)`.
-   **Interpolation**: System calculates the position between keyframes (e.g., Linear interpolation for straight movement).

### Motion Paths
-   When a marker is selected, its entire trajectory is visible as a **Motion Path** (dotted line).
-   Nodes on the path represent keyframes.
-   Users can see where an entity *was* and where it *will go*.

### Visibility & Existence
-   Entities can "appear" and "disappear".
-   Example: A character is born at `t=1980` and dies at `t=2050`. The marker is only visible on the map between these times.

---

## 3. User Interface Concepts

### The Timeline Widget
-   A dockable panel at the bottom of the map.
-   **Scrubber**: Drag to change time.
-   **Tracks**: Rows showing keyframes for selected entities.
-   **Controls**: Play/Pause, Next/Prev Keyframe.

### Map Interaction (The "NLE on Map")
-   **Record Mode**: A "Rec" button toggles recording.
    -   When ON, dragging a marker creates a new keyframe at the current `t`.
    -   Allows "Live Puppeteering": Drag a marker while time plays to record complex movements.
-   **Path Editing**:
    -   Clicking a path node (keyframe) allows dragging it spatially.
    -   Right-click context menu to change interpolation type (Linear, Bezier, Instant).

---

## 4. Technical Requirements

-   **Data Storage**:
    -   Markers need a `temporal` JSON structure.
    -   Keyframes stored as a sorted list: `[{t: 0, x: 0.5, y: 0.5}, ...]`
-   **Performance**:
    -   Rendering needs to be efficient; thousands of markers updating every frame (60fps) requires optimized scene graph updates.
-   **Interaction Layer**:
    -   Separation of "Playback" interactions (panning map) vs "Editing" interactions (moving keyframes).
    -   Robust selection model (see `post_mortem_temporal_maps.md` for challenges here).

## 5. Future Roadmap Ideas (If Resurrected)

-   **Ghost Trails**: Show fading trails behind moving markers during playback.
-   **Region Animation**: Support animating polygon vertices for shifting borders.
-   **Calendar Integration**: Map abstract `t` values to actual fantasy calendar dates.
