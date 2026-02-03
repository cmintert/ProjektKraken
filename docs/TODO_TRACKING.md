# TODO Tracking Document

**Date:** 2024-02-03  
**Phase:** 4 (Polish)  
**Status:** Active

---

## Overview

This document tracks TODO comments that have been reviewed during Phase 4 and their resolution status.

---

## Completed (3 items)

### 1. MainWindow Title Bar Theme Integration ✅
**File:** `src/app/main_window.py:153`  
**Original:** `TODO: Hook into ThemeManager changes`  
**Status:** IMPLEMENTED  
**Date:** 2024-02-03

**Solution:**
- Connected to `ThemeManager().theme_changed` signal
- Added `_on_theme_changed_for_titlebar()` handler
- Title bar now updates dynamically when theme changes

---

### 2. UnifiedList Theme Updates ✅
**File:** `src/gui/widgets/unified_list.py:249`  
**Original:** `TODO: Migrate to fully dynamic theme updates with ThemeManager.theme_changed signal`  
**Status:** ALREADY DONE (TODO removed)  
**Date:** 2024-02-03

**Solution:**
- Code already connected to `theme_changed` signal (line 257)
- Signal handler already implemented (`_on_theme_changed` at line 262)
- TODO was obsolete, removed comment

---

### 3. Entity Editor Auto-Generate Comment ✅
**File:** `src/gui/widgets/entity_editor.py:514`  
**Original:** `# Auto-generate if configured (TODO check config)`  
**Status:** REMOVED (incomplete/abandoned)  
**Date:** 2024-02-03

**Solution:**
- Removed incomplete comment
- No config system exists for auto-generation
- Feature may be implemented in future if needed

---

## To Convert to GitHub Issues (5 items)

These TODOs represent legitimate feature requests or enhancements that should be tracked as GitHub issues.

### 4. Configurable Max Tokens for Summary Generation
**File:** `src/services/summary_service.py:160`  
**Original:** `TODO: Make max_tokens configurable per request if needed`  
**Priority:** Low  
**Category:** Enhancement

**Description:**
Currently, summary generation uses a hardcoded `max_tokens=300`. This should be configurable per request or via settings.

**Suggested Issue Title:**  
"Make max_tokens configurable for summary generation"

**Suggested Labels:**  
enhancement, llm-integration, low-priority

---

### 5. Implement ANN Index for Semantic Search
**File:** `src/services/embedding_service.py:289`  
**Original:** `TODO: Implement actual ANN index building (e.g., FAISS, Annoy)`  
**Priority:** Medium  
**Category:** Enhancement

**Description:**
Current implementation saves embedding metadata but doesn't build an ANN (Approximate Nearest Neighbor) index for fast semantic search. Should integrate FAISS or Annoy for production-quality semantic search.

**Suggested Issue Title:**  
"Implement ANN index (FAISS/Annoy) for semantic search"

**Suggested Labels:**  
enhancement, semantic-search, performance

---

### 6. Calendar Year Variants Support
**File:** `src/core/date_parser.py:323`  
**Original:** `TODO: Handle year variants properly by asking CalendarConfig?`  
**Priority:** Low  
**Category:** Enhancement

**Description:**
Date validation currently doesn't handle calendar year variants (e.g., leap years, variable months per year). Should query `CalendarConfig` for year-specific month configurations.

**Suggested Issue Title:**  
"Add support for calendar year variants in date parsing"

**Suggested Labels:**  
enhancement, calendar, low-priority

---

### 7. Outline Context Menu
**File:** `src/gui/widgets/longform/outline.py:301`  
**Original:** `TODO: Implement context menu with promote/demote/remove options`  
**Priority:** Medium  
**Category:** UX Enhancement

**Description:**
Outline widget has keyboard shortcuts for promote/demote but lacks a context menu. Should add right-click menu with:
- Promote
- Demote
- Remove
- Other outline operations

**Suggested Issue Title:**  
"Add context menu to outline widget with promote/demote/remove options"

**Suggested Labels:**  
enhancement, ux, longform-editor

---

### 8. Timeline Tag Operations (Multiple)
**Files:**  
- `src/gui/widgets/timeline/timeline_view.py:1475` - Color picker
- `src/gui/widgets/timeline/timeline_view.py:1488` - Rename dialog
- `src/gui/widgets/timeline/timeline_view.py:1500` - Remove from grouping

**Priority:** Low  
**Category:** UX Enhancement  
**Status:** Properly documented (keep as-is)

**Description:**
These TODOs correctly note that tag operations (color change, rename, remove from grouping) should be handled by the main window/controller. The current comments are appropriate architectural notes.

**Action:** KEEP AS-IS  
These are not bugs but proper documentation of architectural decisions. No issue needed.

---

## Statistics

**Total TODOs Found:** 10  
**Implemented:** 1  
**Already Done (removed):** 1  
**Removed (incomplete):** 1  
**To Track as Issues:** 5  
**Keep as Architecture Notes:** 2

**Resolution Rate:** 30% (3/10 immediately resolved)

---

## Recommendations

### For Future Development

1. **Issue Creation:** Create 5 GitHub issues from items 4-7 above
2. **Labels:** Use consistent labels (enhancement, low-priority, medium-priority)
3. **Milestones:** Assign to appropriate future milestones
4. **TODO Policy:** New TODOs should:
   - Include issue number if tracked: `TODO(#123): Description`
   - Be temporary (max 1 sprint before converting to issue)
   - Have clear owner/context

### Code Quality

**BEFORE Phase 4:**
- 10 TODO comments
- No tracking system
- Mixed urgency/importance

**AFTER Phase 4:**
- 2 proper architecture notes
- 3 resolved immediately
- 5 documented for issue creation
- Clear tracking document

---

## Next Steps

1. ✅ Implement quick fixes (main_window, unified_list)
2. ✅ Remove obsolete TODO (entity_editor)
3. ✅ Create tracking document
4. ⏳ Create GitHub issues for remaining items (optional)
5. ⏳ Establish TODO policy for future development

---

**Document maintained by:** Production Readiness Review  
**Last updated:** 2024-02-03
