# Implementation Plan: In-Place Entity/Event Creation from Map

The goal is to allow users to create a new Entity or Event directly when adding a marker, path, or region to the map, instead of being limited to existing items.

## User Review Required

> [!IMPORTANT]
> The default type for new entities created from the map will be "Location", as this is most common for map markers. Events will have a default lore_date of 0.0 unless configured otherwise by the user.

## Proposed Changes

### GUI Layer

#### [MODIFY] [map_handler.py](file:///c:/Users/chris/Antigravity_Projects/ProjektKraken/ProjektKraken/src/app/map_handler.py)

-   Update `create_marker` and `on_feature_drawn` to:
    -   Add `"<New Entity...>"` and `"<New Event...>"` to the selection list.
    -   Handle these selections by prompting for a name via `QInputDialog.getText`.
    -   If a new item is created:
        -   Generate a UUID locally.
        -   Emit `CreateEntityCommand` or `CreateEventCommand` using that UUID.
        -   Emit `CreateMarkerCommand` linked to that UUID.

---

## Verification Plan

### Automated Tests
-   I will add a unit test in `tests/unit/app/test_map_handler.py` (if it exists) or create a new test to verify that selecting "New Entity" emits the correct sequence of commands.
-   Run existing tests: `pytest tests/unit/app/test_map_handler.py`

### Manual Verification
1.  Open the application and navigate to the Map tab.
2.  Right-click on the map or draw a feature (Path/Region).
3.  Select `"<New Entity..."` from the list.
4.  Enter a name (e.g., "Mount Doom").
5.  Verify that:
    -   A new marker appears on the map.
    -   A new entity "Mount Doom" appears in the Entity list.
    -   The marker is correctly linked to the new entity (clicking it opens "Mount Doom" in the editor).
6.  Repeat for `"<New Event..."`.
