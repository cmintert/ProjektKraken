---
**Project:** ProjektKraken  
**Document:** Undo System Research - Executive Summary  
**Date:** 2026-02-04  
---

# Undo System Research - Executive Summary

## The Ask

Research the feasibility of implementing:
1. **Per-document history** (context-aware undo per world)
2. **JSON Patch (RFC 6902)** for delta storage
3. **Event sourcing** backend architecture

## The Answer

**✅ PROCEED** with a **Phased Hybrid Approach**

**NOT** the proposed full event sourcing system (too complex), but a pragmatic evolution of the existing command pattern.

---

## Quick Verdict

| Aspect | Assessment |
|--------|------------|
| **Feasibility** | ✅ Viable |
| **Complexity** | ⚠️ Medium-High |
| **Existing Foundation** | ✅ 80% already built (command pattern exists) |
| **Recommended Approach** | Hybrid: Command stack + optional persistence |
| **Event Sourcing** | ❌ Overkill for desktop app |
| **JSON Patch** | ⚠️ Not needed initially |
| **Time to MVP** | 2-3 weeks |
| **Total Effort** | 7-10 weeks (full implementation) |

---

## What ProjektKraken Already Has

### ✅ Strengths (The Good News)

1. **Command Pattern**: All actions are already commands with undo logic
   - 12 command modules (~3,135 LOC)
   - `CreateEventCommand`, `UpdateEventCommand`, etc.
   - Each stores state for undo already

2. **Thread-Safe Architecture**: Worker thread handles all DB operations

3. **Per-World Isolation**: Each world is a separate database file

4. **Hybrid Data Model**: SQL + JSON attributes (already flexible)

5. **Transaction Safety**: SQLite with ACID guarantees

### ❌ What's Missing

1. **Command Stack Management**: No undo/redo stack maintained
2. **History Persistence**: Commands not saved across sessions
3. **UI Components**: No undo/redo buttons or history panel
4. **Event Sourcing**: Database uses UPDATE, not append-only

---

## Recommended Architecture

### The Hybrid Approach

**Core Idea:** Start simple, add complexity incrementally

```
Phase 1: In-Memory Stack    →  2-3 weeks  →  Basic undo/redo
Phase 2: Persistence         →  3-4 weeks  →  Cross-session history
Phase 3: History Panel       →  2-3 weeks  →  Visual history UI
Phase 4: Advanced (optional) →  4-6 weeks  →  Scrubber, squashing
Phase 5: Event Sourcing      →  DEFER      →  Maybe never
```

### Phase 1: In-Memory Undo/Redo (MVP)

**What:** Add undo/redo stacks to CommandCoordinator

```python
class CommandCoordinator:
    def __init__(self):
        self.undo_stack = []  # List[BaseCommand]
        self.redo_stack = []  # List[BaseCommand]
    
    def execute_command(self, command):
        result = command.execute(db_service)
        if result.success:
            self.undo_stack.append(command)
            self.redo_stack.clear()
    
    def undo(self):
        command = self.undo_stack.pop()
        command.undo(db_service)
        self.redo_stack.append(command)
    
    def redo(self):
        command = self.redo_stack.pop()
        command.execute(db_service)
        self.undo_stack.append(command)
```

**UI Changes:**
- Add Edit → Undo (Ctrl+Z)
- Add Edit → Redo (Ctrl+Y)
- Enable/disable based on stack state

**Effort:** 2-3 weeks  
**Value:** HIGH - basic undo/redo expected by users

---

### Phase 2: Persistent History

**What:** Save commands to database, load on startup

```sql
CREATE TABLE command_history (
    id INTEGER PRIMARY KEY,
    world_id TEXT,
    command_type TEXT,
    command_data TEXT,  -- JSON serialized command
    description TEXT,
    timestamp REAL
);
```

**Changes:**
- Add `to_dict()` / `from_dict()` to all commands
- Save commands to history table on execution
- Load last 100 commands on world open
- Per-world history isolation

**Effort:** 3-4 weeks  
**Value:** HIGH - persistent undo across sessions

---

### Phase 3: History Panel UI

**What:** Dockable widget showing command list

```
┌─────────────────────────┐
│ History                 │
├─────────────────────────┤
│ [Undo] [Redo]          │
├─────────────────────────┤
│ Recent Changes:         │
│ • Updated "Battle"      │
│ • Created "King Arthur" │
│ • Deleted event #123    │
└─────────────────────────┘
```

**Effort:** 2-3 weeks  
**Value:** MEDIUM - nice UX enhancement

---

### Phase 4-5: Advanced Features (Optional)

**Deferred:**
- Timeline scrubber for visual navigation
- Command squashing (merge similar edits)
- Full event sourcing with JSON Patch
- Export/import history

**Why Defer:**
- Complexity increases exponentially
- Diminishing returns for desktop app
- Current phases provide 80% of value
- Can revisit based on user feedback

---

## Reality Checks (From Original Proposal)

### A. Browser Back Button Conflict
**Status:** ✅ Not applicable (desktop app, no browser)

### B. Multi-User Concurrency
**Status:** ✅ Not applicable (single-user desktop app)
- Each world is local SQLite file
- No networking or collaboration
- SQLite handles file locking

### C. Frontend Memory Bloat
**Status:** ⚠️ Valid concern, mitigated

**Problem:** 5,000 commands × 1KB each = 5MB in memory

**Solutions:**
- **Stack Limit:** Keep last 100 commands in memory
- **Archiving:** Move old commands to database
- **Weak References:** Store IDs instead of full objects
- **Squashing:** Combine similar consecutive edits

**Monitoring:** Track memory usage, alert if >50MB for history

---

## Event Sourcing: Why Not?

### Proposed System
```python
# Instead of:
UPDATE events SET name = 'New' WHERE id = '123'

# Do:
INSERT INTO event_log (event_id, patch)
VALUES ('123', '{"op": "replace", "path": "/name", ...}')

# Current state = replay all patches
```

### Why It's Overkill

❌ **Complexity:**
- Major architectural overhaul
- Need replay mechanism, snapshots, compaction
- Query complexity explodes

❌ **Performance:**
- Must replay patches to get current state
- Slow for frequently accessed data
- Need materialized views or caching

❌ **YAGNI (You Aren't Gonna Need It):**
- Event sourcing shines in distributed systems
- ProjektKraken is single-user desktop app
- No microservices, no event replay across nodes
- The benefits don't justify the complexity

❌ **Maintenance:**
- More code to test and debug
- Schema migrations become harder
- Team needs ES expertise

### When Event Sourcing Makes Sense

✅ **Good for:**
- Distributed systems with multiple services
- Audit requirements (regulatory compliance)
- Time-travel debugging at scale
- Real-time collaboration (Google Docs style)

❌ **Not needed for:**
- Single-user desktop applications
- Local file-based databases
- Simple undo/redo functionality
- ProjektKraken's use case

---

## JSON Patch: Why Not (Initially)?

### Proposed
```json
{ "op": "replace", "path": "/events/123/name", "value": "New Title" }
```

### Reality

❌ **Schema Mismatch:**
- Database is SQL tables, not JSON documents
- Path notation doesn't map to SQL
- `/events/123/name` needs translation to `UPDATE events SET name = ?`

❌ **Unnecessary Abstraction:**
- Commands already capture state changes
- Adding JSON Patch is extra layer with no benefit
- Would need: `Command → JSON Patch → SQL`

✅ **When It's Useful:**
- If building a REST API
- If storing document as JSON
- If need standard interchange format

✅ **Our Approach:**
- Commands already know how to undo themselves
- Just serialize command objects directly
- Can add JSON Patch later if needed

---

## Files to Modify (Phase 1-3)

### Phase 1: In-Memory Undo/Redo
```
src/app/command_coordinator.py        +150 lines
src/app/main_window.py                +50 lines
src/commands/base_command.py          +20 lines (add get_description)
tests/unit/test_command_coordinator.py +200 lines
```

### Phase 2: Persistence
```
src/commands/base_command.py          +30 lines (serialization interface)
src/commands/*.py                      +50 lines each (implement serialization)
src/services/history_service.py       NEW FILE +300 lines
src/services/db_service.py            +50 lines (migration)
tests/unit/test_command_serialization.py NEW FILE +300 lines
tests/integration/test_history_persist.py NEW FILE +200 lines
```

### Phase 3: History Panel
```
src/gui/widgets/history_panel.py      NEW FILE +200 lines
src/app/main_window.py                +50 lines (dock widget)
src/app/ui_manager.py                 +30 lines
```

**Total New/Modified LOC:** ~2,000 lines (estimated)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Memory bloat | HIGH | Stack limits (100 commands), archiving |
| Serialization breaks | MEDIUM | Versioning, graceful fallback |
| Thread safety | HIGH | Keep coordinator in main thread |
| Performance | MEDIUM | Profiling, async operations |
| Scope creep | HIGH | Strict phase boundaries, stop after Phase 3 |

---

## Success Metrics

### Technical
- [ ] Undo/redo latency <50ms
- [ ] Memory usage <100MB for history
- [ ] Startup time <+100ms with history loading
- [ ] Zero data loss from undo operations
- [ ] <1 bug per 1000 undo/redo operations

### User Experience
- [ ] >80% user satisfaction with undo feature
- [ ] >50% users utilize undo within first week
- [ ] Average 5-10 undo operations per editing session
- [ ] <5% confusion/support requests about undo behavior

### Development
- [ ] Phase 1 complete in 2-3 weeks
- [ ] <5 regressions in existing functionality
- [ ] Test coverage >90% for new code
- [ ] Documentation complete

---

## Go / No-Go Decision

### ✅ GO (Recommended)

**Proceed with Phase 1-3:**

1. **Strong Foundation:** 80% of infrastructure already exists
2. **High Value:** Undo/redo expected in modern apps
3. **Low Risk:** Phase 1 is simple, reversible
4. **Incremental:** Can stop after any phase
5. **Competitive:** Differentiator vs other worldbuilding tools

### ❌ DO NOT DO

**Full Event Sourcing (Phase 5):**

1. **Complexity:** 10x more complex than needed
2. **Performance:** Slower for desktop use case
3. **YAGNI:** Desktop app doesn't need ES
4. **Maintenance:** Ongoing burden for team

---

## Next Steps

### Immediate (This Sprint)
1. Review this research with stakeholders
2. Get approval for Phase 1 implementation
3. Create detailed task breakdown
4. Set up feature branch: `feature/undo-redo-mvp`
5. Assign developer(s)

### Phase 1 Tasks (Sprint 1-2)
1. Enhance CommandCoordinator with stacks
2. Add undo/redo menu items + shortcuts
3. Update BaseCommand with description method
4. Add unit tests for undo/redo flow
5. Manual testing with all command types
6. User documentation

### Decision Points
- **After Phase 1:** Does MVP meet user needs? Proceed to Phase 2?
- **After Phase 2:** Is persistent history valuable? Proceed to Phase 3?
- **After Phase 3:** Do users want scrubber/advanced? Consider Phase 4?

---

## References

- **Full Research:** See `docs/UNDO_SYSTEM_RESEARCH.md` (46KB detailed analysis)
- **Command Pattern:** Already implemented in `src/commands/`
- **Architecture:** See `ARCHITECTURE.md` for threading model
- **RFC 6902:** [JSON Patch Specification](https://tools.ietf.org/html/rfc6902)
- **Event Sourcing:** [Martin Fowler](https://martinfowler.com/eaaDev/EventSourcing.html)

---

## Glossary

- **Command Pattern:** Design pattern where actions are objects
- **Undo Stack:** LIFO stack of executed commands
- **Redo Stack:** LIFO stack of undone commands
- **Event Sourcing:** Store state changes, not current state
- **JSON Patch:** Standard for describing JSON changes
- **Snapshot:** Full state capture for fast reconstruction
- **Squashing:** Merging multiple commands into one

---

**Status:** ✅ Research Complete  
**Recommendation:** ✅ Proceed with Phase 1-3  
**Effort Estimate:** 7-10 weeks total  
**Approval Required:** Product Owner + Engineering Lead  

---
