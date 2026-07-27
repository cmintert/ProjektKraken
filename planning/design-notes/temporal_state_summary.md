# Summary of Work: Relation-driven Temporal State

This project aims to implement a system where an entity's state over time is dynamically resolved from its relationships with events.

## 🛠️ Work Accomplished So Far

### Stage 0 & 1: The Engine and the Backend
- **Temporal Engine**: Created the `TemporalResolver` to merge entity attributes with high-priority "event payloads". 
- **Persistence**: Updated the `RelationRepository` to support JSON-based attributes, enabling storage of `valid_from`, `valid_to`, and custom state overrides.

### Stage 2: Timeline Integration
- **State Resolution**: Connected the logic to the `DatabaseWorker`. Moving the playhead now triggers a background resolution for the active entity.
- **Inspector Feedback**: Implemented a "Read-Only" mode in the Entity Inspector. The UI glows yellow and disables editing when viewing historical states to prevent data corruption.

### Stage 3: Authoring & UI (Finalized)
- **Dynamic Binding**: Implemented logic to bind relation validity directly to event dates (`valid_from_event` / `valid_to_event`).
- **Event Editor Refactor**:
    - Split relations into "Participants", "Locations", and "Other Relations".
    - Added quick-add `+` buttons for structural relationships (Who/Where).
- **Smart Dialog**: The `RelationEditDialog` now features "Timeline Logic" radio buttons to automatically sync dates with the source event.

---

## ⚠️ Problems & Challenges Overcome

| Category | Problem | Solution |
| :--- | :--- | :--- |
| **Lifecycle** | SQLite connections were closing prematurely in asynchronous workers during testing. | Refined `initialize_db` and `cleanup` routines to ensure thread affinity. |
| **UI Bugs** | `AttributeError` caused by referencing `self.event` instead of raw name/date widgets. | Fixed `EventEditor` to pull data directly from UI fields at the moment of request. |
| **Types** | `TypeError` occurred when a signal passed a `bool` (checked state) to a slot expecting a `str` (rel_type). | Handled boolean signal arguments in `_on_add_relation` with default type fallbacks. |
| **UX Logic** | Manual temporal settings were clashing with automatic "Event Logic" radio buttons. | Implemented conditional visibility; manual settings are now hidden until "Absolute Dates" is chosen. |
| **Logic Gaps** | Initial logic lacked a way to say a relation is *only* valid for the duration of a point event. | Added "Only valid at Event" option to bind both Start and End dates simultaneously. |

---

## 🤝 Design Agreements & Decisions

We have established several key patterns to ensure the temporal system remains intuitive and robust:

1.  **Non-Destructive History**: Historical states are derived, not "baked in." Deleting an event or a relation instantly reverts the world state, preserving the database as a single source of truth.
2.  **Visual Safety (The "Yellow Glow")**: To prevent users from accidentally overwriting historical data, the Entity Inspector enters a **Read-Only** state (indicated by a yellow UI shift) whenever the playhead is not at "Present Time."
3.  **Event-Relation Seniority**: We agreed that relations sourced from Events should take priority over base entity attributes to reflect "Story Overrides" accurately.
4.  **UI Hierarchies**: 
    - **Categorization**: Relations are now grouped into "Participants" (Who), "Locations" (Where), and "Others" (Misc) to reduce cognitive load in the Event Editor.
    - **Logic First**: In the `RelationEditDialog`, choosing the *Logic* (e.g., "Starts at Event") is the primary action. Manual date entry is treated as an "Advanced" fallback and is hidden by default.
5.  **Dynamic Tracking**: Agreements were made to store `valid_from_event` and `valid_to_event` flags instead of static dates. This ensures that if you move an event on the timeline, all participants' memberships move with it automatically.

---

## 🚀 Next Steps
- **Stage 4: Change Propagation**: Automatically invalidating the entity cache when a linked event is moved or a relationship is deleted.
- **Stage 5: Summarization**: Generating a chronological text timeline of an entity's history.
