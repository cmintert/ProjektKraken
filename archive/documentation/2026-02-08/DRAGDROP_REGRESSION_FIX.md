# Drag-and-Drop Regression Fix

**Date:** 2026-02-07  
**Commit:** ea2f7a5  
**Issue:** Box selection interfering with drag operations  

---

## Problem

After Sprint 0 and Sprint 1 implementation, a drag-and-drop regression was introduced where:
- Clicking and dragging on items triggered **box selection** (rubber-band) instead of **drag operation**
- Multi-select mode was accidentally enabled
- Users could not drag items from Project Explorer to editors

## Root Cause

Line 295 in `src/gui/widgets/unified_list.py` had the wrong selection mode:

```python
# WRONG - Causes regression
self.list_widget.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
```

**ExtendedSelection mode** enables:
- Multi-select with Ctrl/Shift keys
- **Rubber-band box selection on click-and-drag** ❌
- Conflicts with drag-and-drop operations

## Solution

Changed to **SingleSelection mode**:

```python
# CORRECT - Fixes drag-and-drop
self.list_widget.setSelectionMode(QListView.SelectionMode.SingleSelection)
```

**SingleSelection mode** ensures:
- Only one item can be selected at a time ✅
- Click-and-drag initiates drag operation (not box selection) ✅
- No interference with drag-and-drop functionality ✅

## Files Changed

1. **`src/gui/widgets/unified_list.py`** (line 295-296)
   - Changed `ExtendedSelection` → `SingleSelection`
   - Added explanatory comment

2. **`tests/unit/test_unified_list_features.py`**
   - Renamed test class: `TestUnifiedListMultiSelection` → `TestUnifiedListSelection`
   - Updated test expectations to match SingleSelection behavior
   - Changed from expecting 2 selected items to expecting 1 selected item

## Behavior Comparison

### Before Fix (Broken)

1. User clicks on item in Project Explorer
2. User drags mouse → **Box selection rubber-band appears** ❌
3. Multiple items get selected instead of dragging
4. Drag-and-drop to editors doesn't work properly

### After Fix (Working)

1. User clicks on item in Project Explorer
2. User drags mouse → **Drag operation starts** ✅
3. Drag pill appears (Sprint 1 feature)
4. Drop hint shows on editor hover (Sprint 1 feature)
5. Drop creates relation correctly (Sprint 0 feature)

## Testing

**Manual Test:**
1. Launch ProjektKraken
2. Open Project Explorer with events/entities
3. Click and hold on an item
4. Move mouse (drag motion)
5. **Verify:** No box selection rubber-band appears
6. **Verify:** Item can be dragged to editor
7. **Verify:** Drop creates relation correctly

**Unit Test:**
```bash
pytest tests/unit/test_unified_list_features.py::TestUnifiedListSelection -v
```

All tests pass ✅

## Important Notes

**DO NOT re-enable ExtendedSelection** in unified_list.py - it will break drag-and-drop!

If multi-select functionality is needed in the future, it must be implemented in a way that doesn't conflict with drag operations, such as:
- Using checkboxes for multi-select instead of selection mode
- Detecting drag intent (distance threshold) before starting box selection
- Using a modifier key (Ctrl) to toggle between drag and multi-select modes

## Related Issues

- **Sprint 0:** Implemented basic drag-drop (commit c48a68e)
- **Sprint 1:** Added toast notifications and drop hints (commit 789c082)
- **This fix:** Restored drag-drop functionality (commit ea2f7a5)

---

**Status:** ✅ Fixed  
**Ready for:** Manual testing and verification
