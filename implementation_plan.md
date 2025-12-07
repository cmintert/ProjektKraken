*   **`EventItem`**: A `QGraphicsItem` (or `QGraphicsRectItem`) representing an Event.
    *   Displays name and date.
    *   Clickable (selects event in main window).
    *   Movable (maybe later, triggers `UpdateEventCommand`).
*   **`RelationItem`**: A `QGraphicsPathItem` drawing a bezier curve or line between two `EventItem`s.

## Logic
*   **Scaling**: Need a `pixels_per_unit` scale factor. `x = date * scale`.
*   **Layout**: Events might overlap if they have close dates. Need a simple layout algorithm to stack them vertically (Y-axis) to avoid collisions, or just manual positioning for now (Y=0).
*   **Navigation**: Pan/Zoom support in `QGraphicsView`.

## Integration (`src/app/main.py`)
*   Add `TimelineWidget` to `MainWindow` (Center Widget or Dock).
*   Connect signals:
    *   `timeline.event_selected` -> `load_event_details`.
    *   `db_service` updates -> `timeline.refresh()`.

## Step-by-Step
1.  **Draft `timeline.py`**: Basic scaffolding with `QGraphicsView`.
2.  **Implement `EventItem`**: Draw a simple box.
3.  **Implement `set_events`**: method to populate scene from Event objects.
4.  **Add to `MainWindow`**: Replace central widget placeholder or add dock.
5.  **Refine**: Add auto-scaling or scrollbars.
