---
**Project:** ProjektKraken  
**Document:** Temporal Relations & Dynamic State Guide  
**Last Updated:** 2026-01-04  
**Commit:** `25a67c2`  
---

# Temporal Relations & Dynamic State

## Overview

ProjektKraken implements a **Temporal Resolver** system that allows Entity state (attributes, relationships, status) to change dynamically over time based on Events. Instead of manually updating an entity's description as the story progresses, you define **Temporal Relations** that project state changes onto the entity at specific points in time.

This ensures that:
- You can view the state of the world at *any* point in time (Past, Present, or Future).
- Changing an earlier event automatically propagates effects to the future.
- The "Current State" is simply the state at the concept of "Now".

## Core Concepts

### 1. Base State vs. Projected State

*   **Base State**: The fundamental attributes of an entity (e.g., Name, Type, Description) stored directly on the Entity record. This is the "timeless" truth or the default starting state.
*   **Projected State**: The resolved state of an entity at time `t`, calculated by applying all relevant Temporal Relations active at or before `t`.

### 2. The Playhead

The **Playhead** represents the current viewing time in the application. Moving the Playhead (via the Timeline Widget) instructs the System to re-calculate the Projected State for all visible entities.

- **NOW**: The "Current Story Time" (the furthest point of canonical events).
- **Playhead**: The "Viewing Time" (can be in the past to review history).

## Authoring Guide

### Creating Temporal Relations

1.  **Open an Event** in the Event Editor.
2.  **Add a Relation** to an Entity (e.g., "Involved", "Affects").
3.  **Configure Temporal Logic**:
    -   In the "Add Relation" dialog, use the **Timeline Logic** section.
    -   **Starts Effect**: The relation applies a change starting from this event's date (e.g., "King dies" -> "Kingdom is in chaos").
    -   **Ends Effect**: The relation ends a previous state.
    -   **Payload**: Define the specific attribute changes (e.g., `{"status": "Wounded", "faction": "Rebels"}`).

### Visualizing History

-   **Timeline Widget**: Shows events chronologically. The Playhead indicates the active time context.
-   **Entity Inspector**:
    -   **Timeline Tab**: Displays a filtered list of events affecting this specific entity.
    -   **Status Indicator**: When viewing the past, the "Save" button changes to a yellow "Read-Only" indicator to prevent accidental modification of historical states (which are derived, not stored).

## Technical Architecture

### Temporal Components

#### `TemporalManager` (`src/core/temporal_manager.py`)
The central coordinator that manages caching and invalidation. It listens for database changes and clears the cached state of affected entities.

```python
# Caching Strategy
_cache = {
    ("entity_id", 100.0): {...state...},
    ("entity_id", 200.0): {...state...}
}

# Invalidation
def on_event_changed(event_id):
    # Finds all entities linked to this event and invalidates them
    temporal_manager.invalidate_entity(entity_id)
```

#### `TemporalResolver` (`src/core/temporal_resolver.py`)
Responsible for the pure logic of merging states.

1.  Fetches Base Entity.
2.  Fetches all Relations targeting the Entity where `date <= t`.
3.  Sorts Relations by:
    -   **Date** (Ascending)
    -   **Creation Order** (Tie-breaker)
4.  Applies `payload` dictionaries sequentially using `dict.update()`.

### Code Example: Resolving State

```python
from src.core.temporal_manager import TemporalManager

manager = TemporalManager(db_service)

# Get Frodo's state at the Council of Elrond
state_1 = manager.get_entity_state_at(
    entity_id="frodo_uuid",
    time=3018.8  # Oct 25, 3018
)
print(state_1["location"])  # "Rivendell"

# Get Frodo's state at Mount Doom
state_2 = manager.get_entity_state_at(
    entity_id="frodo_uuid",
    time=3019.25 # Mar 25, 3019
)
print(state_2["location"])  # "Mount Doom"
```

## Best Practices

1.  **Latest Wins**: If two events happen at the exact same time, the one created/edited most recently takes precedence.
2.  **Sparse Payloads**: Only include changed fields in the payload (e.g., `{"status": "Dead"}`). Fields not mentioned retain their previous value (from Base State or previous events).
3.  **Performance**: The system caches heavily. If bulk updating thousands of events, consider suppressing signals or using `clear_all_cache()` once at the end.

## Troubleshooting

### State Not Updating
-   Ensure the relation has `valid_from` set (or "Starts at Event" checked).
-   Verify the Event has a valid `lore_date`.
-   Check if a later event is overriding your change.

### Circular Dependencies
-   The resolver currently assumes a DAG (Directed Acyclic Graph) of time flow. Circular time loops (Event A causes B, B causes A in the past) are not supported and strictly strictly linear based on `lore_date`.
