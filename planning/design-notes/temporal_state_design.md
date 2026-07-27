# Relation-driven Temporal State Design

## 1. Summary
Implement a relation-first temporal state system where Events create typed relations to entities/locations. Relations carry time scopes and payloads (overrides) in `relation.attributes` and become the canonical source of time‑scoped changes.

### Goals
- **Causality**: Keep provenance explicit (Events = causes, Relations = effects).
- **Reliability**: Make simulation and playhead-driven UI reliable and queryable.
- **Source of Truth**: 
    - **Base State**: Users can edit the entity's "static" state text/attributes directly (acts as the default).
    - **Temporal State**: Events provide time-scoped overrides/additions to this base state.
- **Flexibility**: Support multiple relation types per Event-Entity pair (e.g., one for "Role", one for "Condition").

### Scope (MVP)
- **Multi-Edge Relations**: events start with typed relations; mapped to keys in `relation.attributes`.
- **Structured & Textual**: The system will support both structured payloads (valid_from/to) and eventually auto-generated textual timelines.
- `temporal_resolver` service that computes entity state at time $t$ by reading relations.
- **Event Editor**: Participants & Locations pickers that create typed relations on save.
- **Playhead integration**: Timeline playhead → resolver → entity inspector refresh.
- **Change monitoring**: Emit signals on relation/event changes and invalidate caches.
- **Tests**: Comprehensive unit and integration tests for end-to-end flow.

---

## 2. Data Model

### Relation Row
No DB schema change required. We utilize the existing `relations` table with the Flexible JSON Attributes pattern.

- **source_id**: `event_id`
- **target_id**: `entity_or_location_id`
- **rel_type**: Role string (e.g., `participated_in`, `located_at`)
- **attributes** (JSON):
  ```json
  {
    "payload": {
      "status": "Injured",
      "location": "Castle Black"
    },
    // ...
  }
  ```
> **Note**: Multiple relations can exist between the same Event and Entity (e.g., `rel_type="commander"` and `rel_type="injured_in"`). The specific "meaning" is carried by the `rel_type` and the payload.

### Event-Relative Timing (Dynamic Resolution)
To ensure relations move with Events, we support dynamic dating flags in `attributes`:
```json
{
  "valid_from_event": true, // Resolver uses source_event.lore_date instead of static valid_from
  "valid_to_event": true,   // Resolver uses source_event.lore_date instead of static valid_to
  "payload": { ... }
}
```
*   **Repository Layer**: `RelationRepository` joins with `events` table to fetch `lore_date` as `source_event_date`.
*   **Resolver Layer**: If `valid_from_event` is true, replaces `valid_from` with `source_event_date`.

### Resolver Semantics
To compute state for Entity $E$ at time $T$:
1. **Query**: Find all relations where:
   - `target_id` == $E$
   - `source` is an Event (conceptually, or check `valid_from` existence)
   - Relation is "active" at $T$ (`valid_from <= T` AND (`valid_to` is null OR `valid_to > T`)).
2. **Sort/Merge**:
   - Sort by `valid_from` (ascending).
   - Tie-breaker: Relation creation time or Version.
   - Initial State = Entity's static/base attributes.
   - Apply Relation Payloads sequentially (Overwrite merge for simple keys).

---

## 3. Implementation Status
---

### Stage 0: Core Scaffold (Completed)
- **Framework**: `TemporalResolver` (Logic) and `TemporalManager` (Orchestration).
- **Caching**: Naive `(entity_id, time)` cache in Manager.

### Stage 1: Structured Relationship Backend (Completed)
- **UI**: Added `RelationEditDialog` support for valid_from/to and JSON payloads.
- **Backend**: Verified `relations` table JSON support.

### Stage 2: Resolver Integration & Playhead (Completed)
- **Flow**: `Timeline.playhead_changed` -> `Worker.resolve_state` -> `EntityEditor.display_state`.
- **UX**: Entity Inspector enters Read-Only mode (Yellow button) when viewing past states.
- **Verification**: Integration tests (`test_temporal_integration.py`) confirm DB -> Resolver flow.

### Stage 3: Event Editor UI Expansion (Completed)
- **Categorized Pickers**: `EventEditor` now differentiates between Participants (`involved`), Locations (`located_at`), and Other Relations.
- **Smart Relations**: `RelationEditDialog` is aware of the source Event context and supports dynamic binding.
- **Features**: Quick-add `+` buttons for structural relationships (Who/Where).

### Stage 4: Change Propagation & Caching (Next)
- **Signals**: Connect `event_updated` and `relation_updated` signals to `TemporalManager`.
- **Cache**: Implement event-aware invalidation (Event moves -> clear cache for related entities).

### Stage 5: Future Foundations (Textual Timeline)
- **UX**: Dedicated "Timeline" tab in Entity Inspector showing chronological changes.
- **Summarization**: Logic to generate text summaries from Relation Payloads.

### Stage 6: CLI Parity & Export (2–4 days)
- **CLI**: `event.py` flags for participants/payloads.
- **New Tool**: `src/cli/animation.py` for sampling state over time.

### Stage 7: Docs & Examples (1–2 days)
- **Docs**: `docs/TEMPORAL_RELATIONS.md`.
- **Validation**: Example world dataset in CI.

---

## 4. Design Analysis & Brainstorming

### Performance & Indexing
- **Challenge**: JSON queries for `valid_from` might be slow.
- **Mitigation (MVP)**: Python-side filtering. (Fetch all relations for Entity $E$, then filter in memory).
- **Future**: Add SQLite index on `json_extract(attributes, '$.valid_from')` if event count > 10k.

### Conflict Resolution
- **Issue**: Simultaneous events (same `valid_from`).
- **Strategy**: Rigid tie-breaking order:
  1. Priority (`event` > `manual`)
  2. `valid_from` (Time)
  3. `created_at` (Insert Order / Server Time)
  4. Relation ID (lexicographical) to ensure determinism.

### The "Hole in History"
- **Issue**: Deleting an event instantly reverts state for all future times.
- **Mitigation**: This is "Working as Intended" for a non-destructive source-of-truth system. "Burn-in" features can be added in Stage 4/5 if users need to decouple history.

### UI Complexity
- **Event Editor**: Avoid overcrowding.
- **Plan**: Keep "Relations" tab flexible but add a "Quick Participants" section in the main Details tab for common usage (Who/Where).
