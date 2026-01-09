# Temporal Map Interaction Flow Diagrams

## Current Implementation: Mode Confusion

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER EXPERIENCE                          │
└─────────────────────────────────────────────────────────────────┘

SCENARIO: User wants to adjust when a keyframe occurs

Step 1: Select Marker
   ┌──────────┐
   │ [Marker] │ ← Click marker with trajectory
   └──────────┘
        ↓
   Trajectory path appears (blue dashed line)
   Keyframes show as yellow dots

Step 2: Find Gizmo (❌ DISCOVERY PROBLEM)
   User must:
   - Hover over 6px yellow dot (precise targeting required)
   - Wait for gizmo to appear (no hint it exists)
   - Interpret emoji icons (no tooltips)
   
   Many users stop here → Never discover Clock Mode

Step 3: Enter Clock Mode (❌ MODE CONFUSION)
   ┌──────┐
   │ 🕐 ✕ │ ← Hover gizmo appears
   └──────┘
        ↓
   Click clock icon
        ↓
   ┌──────────┐
   │ 🔴 (red) │ ← Keyframe turns red
   └──────────┘
   
   ❌ NO OTHER INDICATOR
   ❌ User doesn't know mode changed
   ❌ No instructions shown

Step 4: Scrub Timeline (❌ UNEXPECTED BEHAVIOR)
   User drags playhead
        ↓
   Expected: All markers move (normal behavior)
   Actual: Only red keyframe moves
        ↓
   User thinks: "Timeline is broken" or "I did something wrong"

Step 5: Exit Mode (❌ NO CLEAR PATH)
   User options:
   - Click clock icon again (same 6px target)
   - Click away (implicit commit—confusing)
   - ??? (no Cancel button, no Esc handler)
   
   User struggles to regain control
```

---

## Recommended Implementation: Clear Mode Awareness

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMPROVED USER EXPERIENCE                      │
└─────────────────────────────────────────────────────────────────┘

SCENARIO: User wants to adjust when a keyframe occurs

Step 1: Select Marker
   ┌──────────┐
   │ [Marker] │ ← Click marker with trajectory
   └──────────┘
        ↓
   Trajectory path appears
   ✅ First-time tooltip: "Hover keyframes to edit"

Step 2: Discover Gizmo (✅ PROGRESSIVE DISCLOSURE)
   ┌──────────┐
   │ 🔴●   ●  │ ← Keyframes pulse 3× on first display
   └──────────┘
        ↓
   Hover 24×24px target (easier to hit)
        ↓
   ┌─────────────────────┐
   │ [Edit Time] [Delete] │ ← Tooltips show immediately
   └─────────────────────┘

Step 3: Enter Clock Mode (✅ CLEAR FEEDBACK)
   Click "Edit Time" button
        ↓
   ┌────────────────────────────────────────────────────┐
   │ TOOLBAR: [🔴 CLOCK MODE: Editing Marker "Entity"] │
   │          [Cancel] [Commit Change]                  │
   └────────────────────────────────────────────────────┘
        ↓
   ┌────────────────────────────────────────────────────┐
   │ OVERLAY: ⏱ CLOCK MODE ACTIVE                      │
   │ Scrub timeline to adjust keyframe timestamp        │
   │ [Esc] Cancel  [Enter] Commit                       │
   └────────────────────────────────────────────────────┘
        ↓
   Keyframe turns red + Label updates
   Cursor changes to clock icon

Step 4: Scrub Timeline (✅ EXPECTED BEHAVIOR)
   User drags playhead
        ↓
   ✅ Only red keyframe moves (as indicated by mode)
   ✅ Date label updates in real-time
   ✅ Other markers stay frozen (expected in Clock Mode)
        ↓
   User thinks: "Perfect, I'm adjusting the time"

Step 5: Exit Mode (✅ MULTIPLE CLEAR PATHS)
   User options:
   A) Click [Commit Change] button → Saves new time
   B) Click [Cancel] button → Reverts to original
   C) Press Enter → Commits
   D) Press Esc → Cancels
   E) Right-click → Context menu with options
        ↓
   ✅ Toast confirmation: "Keyframe time updated to T=150.5"
   ✅ Mode indicator returns: [Normal Mode]
```

---

## Visual State Comparison

### Current: Hidden Mode State
```
┌─────────────────────────────────────────────────────┐
│ MAP WIDGET                                          │
│ [Dropdown] [New Map] [Delete] [Fit] [Settings] [...] │ ← No mode shown
└─────────────────────────────────────────────────────┘

MAP VIEW:
┌─────────────────────────────────────────────────────┐
│                                                     │
│     [Blue Marker]                                   │
│          ↓                                           │
│     🔵───🔴───🔵  (trajectory)                       │ ← Only local cue
│          ↑                                           │
│      (Red = pinned, but ambiguous)                  │
│                                                     │
└─────────────────────────────────────────────────────┘

❌ User must REMEMBER they're in Clock Mode
❌ Mode state not visible if zoomed/panned away from keyframe
```

### Recommended: Persistent Mode Indicator
```
┌─────────────────────────────────────────────────────────────────┐
│ MAP WIDGET                                                      │
│ [New Map] [Delete] [...] [🔴 CLOCK MODE] [Cancel] [Commit]    │ ← Always visible
└─────────────────────────────────────────────────────────────────┘

MAP VIEW:
┌─────────────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────┐             │
│ │ ⏱ CLOCK MODE ACTIVE                             │             │ ← Overlay
│ │ Scrub timeline to adjust keyframe timestamp      │             │
│ │ [Esc] Cancel  [Enter] Commit                    │             │
│ └─────────────────────────────────────────────────┘             │
│                                                                 │
│     [Blue Marker] ← Normal markers frozen                       │
│          ↓                                                       │
│     🔵───🔴───🔵  (trajectory)                                   │
│          ↑                                                       │
│   [T=150.5] ← Live date label                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

✅ Mode visible at all times (toolbar + overlay)
✅ Clear instructions and exit paths
✅ Cursor changes to clock icon
```

---

## Gizmo Design Evolution

### Current: 6px Hidden Buttons
```
Hover keyframe dot:
   ┌──┐
   │🕐│✕  ← 6×6 pixel targets (emoji)
   └──┘
   
Problems:
❌ Too small (below WCAG 24px minimum)
❌ Emoji rendering varies by OS
❌ No tooltips (meaning unclear)
❌ Only visible on hover (hidden affordance)
```

### Recommended: 24px Accessible Buttons
```
Hover keyframe dot:
   ┌────────────────────────┐
   │ [🕐 Edit Time] [✕ Delete] │ ← 24×24px targets
   └────────────────────────┘
      ↑ Tooltip appears       ↑ Tooltip appears
   
Or with text labels at high zoom:
   ┌─────────────────────────────────┐
   │ [⏱ Time] [🗑️ Delete]           │
   └─────────────────────────────────┘

Improvements:
✅ 4× larger hit zones (accessible)
✅ Tooltips explain function
✅ SVG icons (consistent rendering)
✅ Optional text labels at high zoom
✅ Scale 1.2× on hover (feedback)
```

---

## Timeline Scrubbing: Mode-Dependent Behavior

### Normal Mode (Default)
```
PLAYHEAD: ━━━━━━━●━━━━━━━━
                 ↑ T=100

MAP VIEW:
   🔵 Marker A at (0.3, 0.4) ← Interpolated from keyframes
   🔵 Marker B at (0.7, 0.2) ← Interpolated from keyframes
   🔵 Marker C at (0.5, 0.8) ← Interpolated from keyframes

All markers animate as playhead moves
```

### Clock Mode (Keyframe Editing)
```
PLAYHEAD: ━━━━━━━●━━━━━━━━
                 ↑ T=150 (changed from 100)

MAP VIEW:
   🔵 Marker A at (0.3, 0.4) ← FROZEN
   🔴 Marker B at (0.7, 0.2) ← PINNED (moves with playhead time)
   🔵 Marker C at (0.5, 0.8) ← FROZEN

Only pinned keyframe "travels through time"
```

---

## Error Prevention: Delete Confirmation Flow

### Current: Instant Deletion (❌ DANGEROUS)
```
User clicks ✕ icon
     ↓
Keyframe deleted immediately
     ↓
If last keyframe → Trajectory auto-deleted
     ↓
User panics → Searches for undo (not visible)
```

### Recommended: Smart Confirmation (✅ SAFE)
```
User clicks [Delete] button
     ↓
System checks: How many keyframes remain?
     ↓
┌─ If >2 keyframes: ────────────────────┐
│ Delete immediately                     │
│ Show toast: "Deleted. [Undo]"         │
└────────────────────────────────────────┘
     
┌─ If ≤2 keyframes (would delete trajectory): ─────┐
│ ⚠️ Delete Entire Trajectory?                     │
│                                                   │
│ This is the last keyframe for "Entity Name".     │
│ Deleting it will remove all movement history.    │
│                                                   │
│ This action can be undone.                       │
│                                                   │
│ [Cancel]  [Delete Trajectory]                    │
└───────────────────────────────────────────────────┘
```

---

## Performance: Drag Optimization

### Current: Unthrottled Updates (❌ LAGGY)
```
User drags keyframe
     ↓
EVERY mouse move event:
   1. Update keyframe position
   2. Sort keyframes by time
   3. Rebuild entire QPainterPath
   4. Redraw all path segments
   5. Update scene
     ↓
At 10 keyframes: 60fps ✅
At 100 keyframes: 15fps ❌ (visible stutter)
```

### Recommended: Throttled Updates (✅ SMOOTH)
```
User drags keyframe
     ↓
EVERY mouse move event:
   1. Update keyframe position
   2. Set dirty flag
     ↓
16ms timer (60fps):
   If dirty:
      1. Sort keyframes
      2. Rebuild path (optimized)
      3. Single scene update
     ↓
Smooth 60fps even with 200+ keyframes
```

---

## Accessibility: Keyboard Navigation

### Current: Mouse-Only (❌ EXCLUDES USERS)
```
All operations require precise mouse:
❌ No Tab navigation between keyframes
❌ No Delete key for removal
❌ No arrow keys for position adjustment
❌ No Esc to exit modes
❌ No Enter to commit
```

### Recommended: Full Keyboard Support (✅ INCLUSIVE)
```
Keyboard Shortcuts:
┌──────────────────────────────────────┐
│ Tab          - Cycle keyframe focus  │
│ Shift+Tab    - Reverse cycle         │
│ ←↑→↓        - Nudge position (1px)  │
│ Delete       - Delete focused keyframe│
│ C            - Enter Clock Mode       │
│ Enter        - Commit Clock Mode      │
│ Esc          - Cancel Clock Mode      │
│ Space        - Toggle playhead play   │
│ Ctrl+Z       - Undo                   │
│ Ctrl+Shift+Z - Redo                   │
└──────────────────────────────────────┘

Visual Focus:
   🔵───🟦───🔵  (Blue ring = focused)
        ↑
   Arrow keys move this keyframe
```

---

**Last Updated**: January 9, 2026  
**Purpose**: Visual supplement to UX Audit Report  
**See Also**: [UX_AUDIT_TEMPORAL_MAPS.md](./UX_AUDIT_TEMPORAL_MAPS.md)
