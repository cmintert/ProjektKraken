# Walkthrough: In-Place Entity/Event Creation from Map

## What Changed

The map's item-selection dialog (used when adding markers, paths, or regions) now includes **`<New Entity...>`** and **`<New Event...>`** options at the top of the list.

### Modified File
- [map_handler.py](file:///c:/Users/chris/Antigravity_Projects/ProjektKraken/ProjektKraken/src/app/map_handler.py)

render_diffs(file:///c:/Users/chris/Antigravity_Projects/ProjektKraken/ProjektKraken/src/app/map_handler.py)

### New File
- [test_map_handler_create.py](file:///c:/Users/chris/Antigravity_Projects/ProjektKraken/ProjektKraken/tests/unit/test_map_handler_create.py) — 7 unit tests

## How It Works

1. User right-clicks the map (or finishes drawing a path/region).
2. The selection dialog appears with two new entries pinned to the top:
   - **`<New Entity...>`** — creates a "Location"-type entity
   - **`<New Event...>`** — creates an event with `lore_date=0.0`
3. Selecting either prompts for a name via a second dialog.
4. Two commands are emitted in sequence:
   - `CreateEntityCommand` or `CreateEventCommand` (with a pre-generated UUID)
   - `CreateMarkerCommand` (linked to that UUID)
5. Cancelling the name dialog aborts the entire operation cleanly.

## Validation Results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_map_handler_scale.py` (existing) | 2 | ✅ Pass |
| `test_map_handler_create.py` (new) | 7 | ✅ Pass |
| Ruff lint | — | ✅ Clean |
