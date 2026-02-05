# Per-Document History Undo System - Research Package Index

## Overview

This package contains comprehensive research on implementing a sophisticated undo/redo system for ProjektKraken, evaluating the proposed JSON Patch + Event Sourcing architecture.

**Research Date:** 2026-02-04  
**Status:** ✅ Complete - Awaiting Stakeholder Decision  
**Recommendation:** ✅ PROCEED with Phased Hybrid Approach (Phases 1-3)

---

## Document Structure

### 📋 For Decision Makers

**Start Here:** [`UNDO_SYSTEM_DECISION.md`](UNDO_SYSTEM_DECISION.md)
- Quick decision matrix with scoring
- Cost-benefit analysis
- Risk assessment
- Go/No-Go checklist
- Recommended options with budget
- Sign-off section

**Then Read:** [`UNDO_SYSTEM_SUMMARY.md`](UNDO_SYSTEM_SUMMARY.md)
- Executive summary (12KB)
- Quick verdict and reasoning
- Current architecture strengths
- Phased implementation overview
- Reality checks addressed
- Success metrics

### 🔧 For Engineers

**Start Here:** [`UNDO_SYSTEM_ARCHITECTURE.txt`](UNDO_SYSTEM_ARCHITECTURE.txt)
- Visual ASCII diagrams (18KB)
- Data flow illustrations
- Phase-by-phase architecture evolution
- Memory management strategy
- Complete integration flow

**Then Read:** [`UNDO_SYSTEM_RESEARCH.md`](UNDO_SYSTEM_RESEARCH.md)
- Comprehensive technical analysis (46KB)
- Current architecture deep-dive
- JSON Patch evaluation
- Event Sourcing feasibility
- Alternative approaches
- Detailed implementation specs
- Code examples and file modifications

### 📊 Quick Reference

| Document | Size | Audience | Purpose |
|----------|------|----------|---------|
| **DECISION.md** | 10KB | Leadership, PM | Approve/reject with justification |
| **SUMMARY.md** | 12KB | Everyone | Quick understanding of proposal |
| **ARCHITECTURE.txt** | 18KB | Engineers | Visual design and flows |
| **RESEARCH.md** | 46KB | Tech Lead, Architect | Deep technical analysis |

**Total Package Size:** ~86KB of documentation

---

## Key Findings at a Glance

### The Recommendation

**✅ PROCEED** with **Phased Hybrid Approach**

**NOT** the full event sourcing system (too complex), but a pragmatic evolution of existing command pattern.

### Why This Makes Sense

| Aspect | Score | Reasoning |
|--------|-------|-----------|
| **Feasibility** | 8/10 | Foundation exists, proven approach |
| **Value** | 9/10 | Users expect undo/redo |
| **Effort** | 7/10 | Reasonable 7-10 weeks for full |
| **Risk** | 8/10 | Low risk, reversible changes |
| **ROI** | 8/10 | High value, low maintenance |
| **OVERALL** | 7.8/10 | **Strong recommendation** |

### The Plan

```
Phase 1: In-Memory Undo/Redo     →  2-3 weeks  →  ⭐⭐⭐ Good MVP
Phase 2: Persistent History       →  3-4 weeks  →  ⭐⭐⭐⭐ Strong
Phase 3: History Panel UI         →  2-3 weeks  →  ⭐⭐⭐⭐⭐ Complete
Phase 4: Advanced Features        →  OPTIONAL   →  ⭐⭐ Polish
Phase 5: Full Event Sourcing      →  DEFER      →  ❌ Not needed
```

**Total Timeline:** 7-10 weeks for Phases 1-3

### What We're NOT Doing (and Why)

❌ **Full Event Sourcing:**
- 10x more complex than needed
- Poor fit for desktop application
- Maintenance nightmare
- Overkill for single-user scenario

❌ **JSON Patch (RFC 6902):**
- Unnecessary abstraction layer
- Schema mismatch (SQL vs JSON)
- Current commands already handle undo
- Can add later if web API needed

---

## Current Architecture Strengths

ProjektKraken already has **80% of what's needed**:

✅ **Command Pattern:** All actions are commands with undo logic  
✅ **State Capture:** Commands store previous state  
✅ **Thread Safety:** Worker thread architecture  
✅ **Per-World Isolation:** Separate database per world  
✅ **Transaction Support:** SQLite with ACID guarantees

**What's Missing:**
- ❌ Command stack management (undo/redo lists)
- ❌ UI components (menu items, history panel)
- ❌ History persistence (optional)

---

## Implementation Highlights

### Phase 1: In-Memory Undo/Redo (MVP)

**What:** Add undo/redo stacks to CommandCoordinator

```python
class CommandCoordinator:
    def __init__(self):
        self.undo_stack = []  # Last 100 commands
        self.redo_stack = []  # Clear on new action
    
    def undo(self):
        cmd = self.undo_stack.pop()
        cmd.undo(db_service)
        self.redo_stack.append(cmd)
```

**UI:** Edit → Undo (Ctrl+Z), Edit → Redo (Ctrl+Y)

**Files Modified:**
- `src/app/command_coordinator.py` (+150 lines)
- `src/app/main_window.py` (+50 lines)
- All command files (+20 lines each)

**Timeline:** 2-3 weeks  
**Value:** HIGH

### Phase 2: Persistent History

**What:** Save commands to database, load on startup

```sql
CREATE TABLE command_history (
    id INTEGER PRIMARY KEY,
    world_id TEXT,
    command_type TEXT,
    command_data TEXT,  -- JSON
    timestamp REAL
);
```

**Files Modified:**
- All command files (+50 lines serialization)
- `src/services/history_service.py` (NEW +300 lines)
- `src/services/db_service.py` (+50 lines migration)

**Timeline:** 3-4 weeks  
**Value:** HIGH

### Phase 3: History Panel UI

**What:** Dockable widget showing command list

```
┌─────────────────┐
│ History         │
├─────────────────┤
│ [Undo] [Redo]  │
├─────────────────┤
│ Recent:         │
│ • Updated       │
│   "Battle"      │
│ • Created       │
│   "Arthur"      │
└─────────────────┘
```

**Files Modified:**
- `src/gui/widgets/history_panel.py` (NEW +200 lines)
- `src/app/main_window.py` (+50 lines dock)

**Timeline:** 2-3 weeks  
**Value:** MEDIUM

---

## Reality Checks from Original Proposal

### A. Browser Back Button Conflict
**Original Concern:** Users might confuse browser back with undo  
**Reality:** ✅ Not applicable - ProjektKraken is a desktop app

### B. Multi-User Concurrency
**Original Concern:** Multiple users editing same document  
**Reality:** ✅ Not applicable - Single-user desktop design

### C. Frontend Memory Bloat
**Original Concern:** Thousands of commands in memory  
**Reality:** ⚠️ Valid - Mitigated with stack limits (100 commands)

**Solution:**
- Keep last 100 commands in memory (~120KB)
- Archive older commands to database
- Squash similar consecutive operations

---

## Success Metrics

### Technical Metrics
- [ ] Undo/redo latency <50ms
- [ ] Memory usage <100MB for history
- [ ] Startup time <+100ms with loading
- [ ] Zero data loss from undo operations
- [ ] Test coverage >90% for new code

### User Metrics
- [ ] >80% user satisfaction
- [ ] >50% adoption within first week
- [ ] Average 5-10 undo operations per session
- [ ] <5% confusion/support requests

### Development Metrics
- [ ] Phase 1 complete in 2-3 weeks
- [ ] <5 regressions in existing functionality
- [ ] Complete documentation
- [ ] Code review approval

---

## File Modifications Summary

### Phase 1 (In-Memory)
```
src/app/command_coordinator.py        +150 lines
src/app/main_window.py                +50 lines
src/commands/base_command.py          +20 lines
tests/unit/test_command_coordinator.py +200 lines
```

### Phase 2 (Persistence)
```
src/commands/base_command.py          +30 lines (interface)
src/commands/*.py                      +50 lines each (12 files)
src/services/history_service.py       NEW +300 lines
src/services/db_service.py            +50 lines (migration)
tests/unit/test_serialization.py      NEW +300 lines
tests/integration/test_history.py     NEW +200 lines
```

### Phase 3 (UI Panel)
```
src/gui/widgets/history_panel.py      NEW +200 lines
src/app/main_window.py                +50 lines
src/app/ui_manager.py                 +30 lines
tests/unit/test_history_panel.py      NEW +150 lines
```

**Total New/Modified:** ~2,000 lines of code

---

## Risk Assessment

### Overall Risk: LOW-MEDIUM

| Category | Level | Mitigation |
|----------|-------|------------|
| Technical | LOW | Uses existing patterns |
| Performance | LOW | Async operations, limits |
| Memory | LOW-MEDIUM | Stack limits, archiving |
| UX | LOW | Clear feedback, testing |
| Scope Creep | MEDIUM-HIGH | Strict phase boundaries |

---

## Decision Options

### Option A: Full Implementation (Phases 1-3) ✅ RECOMMENDED
- **Timeline:** 7-10 weeks
- **Budget:** 9-12 weeks (with testing/docs)
- **Value:** ⭐⭐⭐⭐⭐ Complete feature
- **Risk:** Low

### Option B: MVP Only (Phase 1) ✅ ACCEPTABLE
- **Timeline:** 2-3 weeks
- **Budget:** 3 weeks total
- **Value:** ⭐⭐⭐ Basic functionality
- **Risk:** Very Low
- **Upgrade Path:** Can expand later

### Option C: Do Nothing ❌ NOT RECOMMENDED
- **Timeline:** 0 weeks
- **Value:** ❌ Missing expected feature
- **Impact:** Competitive disadvantage

### Option D: Full Event Sourcing ❌ NOT RECOMMENDED
- **Timeline:** 12-16 weeks
- **Value:** ⭐⭐ Over-engineered
- **Risk:** High complexity

---

## Stakeholder Actions Required

### 1. Decision Makers
- [ ] Review `UNDO_SYSTEM_DECISION.md`
- [ ] Select implementation option (A or B)
- [ ] Approve budget and timeline
- [ ] Sign off on document

### 2. Engineering Lead
- [ ] Review `UNDO_SYSTEM_RESEARCH.md`
- [ ] Validate technical approach
- [ ] Assign developer(s)
- [ ] Set up feature branch

### 3. Product Owner
- [ ] Review `UNDO_SYSTEM_SUMMARY.md`
- [ ] Prioritize vs other features
- [ ] Define success metrics
- [ ] Plan release (v0.11 or v0.12)

### 4. Designer (if Phase 3)
- [ ] Review history panel mockups
- [ ] Design UI components
- [ ] Ensure theme consistency

---

## Next Steps (If Approved)

### Week 1
1. Create feature branch: `feature/undo-redo-mvp`
2. Kickoff meeting with team
3. Set up tracking (issues/tickets)
4. Begin Phase 1 implementation

### Weeks 2-3
1. Complete CommandCoordinator enhancements
2. Add menu items and shortcuts
3. Write unit tests
4. Code review and merge

### Weeks 4-7 (if Phase 2 approved)
1. Implement command serialization
2. Create database schema
3. Integration testing
4. Performance benchmarking

### Weeks 8-10 (if Phase 3 approved)
1. Design and implement history panel
2. User acceptance testing
3. Documentation
4. Release preparation

---

## Questions & Answers

### Q1: Why not use Qt's QUndoStack?
**A:** Considered, but would require refactoring all existing commands. Current BaseCommand pattern already works well. Could revisit in Phase 4.

### Q2: What about real-time collaboration?
**A:** Not planned. ProjektKraken is single-user by design. Event sourcing would be needed for collaboration, but that's a much larger feature.

### Q3: Can users undo changes from days ago?
**A:** With Phase 2 (persistence), yes - history is stored in database. Limited only by disk space and snapshot strategy.

### Q4: What happens if command serialization fails?
**A:** Graceful degradation - skip the command, log error, continue with rest of history. User loses that specific undo point but app continues working.

### Q5: Performance impact on large worlds?
**A:** Minimal. Undo/redo happens in worker thread. Database operations are async. Target <50ms latency maintained even with 10,000+ events.

---

## Contact & Feedback

**Research Team:** Development Team  
**Date:** 2026-02-04  
**Version:** 1.0

For questions or feedback on this research:
1. Review the detailed documents
2. Contact engineering lead
3. Discuss in team meeting

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-02-04 | Initial research complete | Research Team |

---

**Status:** ✅ RESEARCH COMPLETE  
**Recommendation:** ✅ PROCEED (Option A or B)  
**Next Action:** Stakeholder review and decision  

---
