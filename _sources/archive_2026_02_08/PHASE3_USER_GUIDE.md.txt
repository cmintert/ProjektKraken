# Phase 3: History Panel UI - User Guide

## What's New in Phase 3?

Phase 3 adds a **visual history panel** - a dockable widget that displays your command history in a clear, interactive list!

### Before Phase 3
- Undo/Redo via keyboard shortcuts only (Ctrl+Z/Ctrl+Y)
- Edit menu shows Undo/Redo but no visual history
- No way to see what commands are in the history

### After Phase 3
- **Visual history panel** showing all commands
- See exactly what will be undone or redone
- Click buttons in the panel for undo/redo
- Real-time updates as you work
- Theme-aware styling

---

## Features

### 1. Visual Command History

The history panel displays all commands in your undo/redo stacks:

```
┌─────────────────────────────┐
│ [⟲ Undo] [⟳ Redo] [✕ Clear] │
├─────────────────────────────┤
│  5 commands (3 undo / 2 redo)│
├─────────────────────────────┤
│ ▼ Update Event 'Battle'     │ ← Next to redo (dimmed, orange)
│   Create Entity 'Arthur'    │
│ ▲ Create Event 'Siege'      │ ← Next to undo (bold, blue)
│   Update Event 'War'        │
│   Delete Entity 'Old One'   │
├─────────────────────────────┤
│  ▲ Can undo  |  ▼ Can redo  │
└─────────────────────────────┘
```

**Visual Indicators:**
- **▲ Symbol** - Commands that can be undone (above current position)
- **▼ Symbol** - Commands that can be redone (below current position)
- **Bold Text** - Next command to undo or redo
- **Blue Highlight** - Next undo action
- **Orange Highlight** - Next redo action
- **Dimmed Text** - Commands that have been undone

### 2. Interactive Buttons

Three buttons at the top provide quick access:

**⟲ Undo Button**
- Click to undo the last action
- Shortcut: Ctrl+Z (same as Edit menu)
- Disabled when undo stack is empty
- Tooltip shows keyboard shortcut

**⟳ Redo Button**
- Click to redo an undone action
- Shortcut: Ctrl+Y (same as Edit menu)
- Disabled when redo stack is empty
- Tooltip shows keyboard shortcut

**✕ Clear Button**
- Click to clear all history
- Permanently removes undo/redo history
- Disabled when history is empty
- Use with caution!

### 3. Status Information

**Top Status Label:**
- Shows total command count
- Shows undo/redo split (e.g., "5 commands (3 undo / 2 redo)")
- Updates in real-time

**Bottom Info Label:**
- Explains the symbols: "▲ Can undo | ▼ Can redo"

### 4. Theme Support

The history panel automatically adapts to your selected theme:

**Dark Mode:**
- Dark background, light text
- Blue highlights for undo
- Orange highlights for redo
- Subtle borders

**Light Mode:**
- Light background, dark text
- Same color scheme adapted for light theme
- Maintains visual consistency

**Theme Switching:**
- Changes apply immediately
- No need to restart the application

---

## How to Use

### Opening the History Panel

The history panel is a dockable widget that appears on the right side of the window:

1. **Default Position:** Tabbed with Entity Inspector on the right
2. **To Show/Hide:** Click the tab labeled "History"
3. **To Undock:** Drag the title bar to float it
4. **To Redock:** Drag the title bar back to a dock area

### Basic Workflow

1. **Work normally** - Create/edit/delete events and entities
2. **Watch the history** - Panel updates automatically
3. **Review commands** - See what you've done recently
4. **Undo/Redo** - Use panel buttons or keyboard shortcuts
5. **Clear history** - When you want to free up memory

### Example Session

```
1. Create Event "Battle of Vale"
   → History shows: ▲ Create Event 'Battle of Vale'

2. Update Event to "Battle of Vale (Morning)"
   → History shows:
      ▲ Update Event 'Battle of Vale'
        Create Event 'Battle of Vale'

3. Press Ctrl+Z (or click Undo button)
   → History shows:
      ▼ Update Event 'Battle of Vale'
      ▲ Create Event 'Battle of Vale'
   → Event name reverts to "Battle of Vale"

4. Press Ctrl+Y (or click Redo button)
   → History shows:
      ▲ Update Event 'Battle of Vale'
        Create Event 'Battle of Vale'
   → Event name returns to "Battle of Vale (Morning)"
```

---

## Understanding the Display

### Command Descriptions

Each command shows a human-readable description:

**Event Commands:**
- "Create Event 'Event Name'"
- "Update Event 'Event Name'"
- "Delete Event 'Event Name'"

**Entity Commands:**
- "Create Entity 'Entity Name'"
- "Update Entity 'Entity Name'"
- "Delete Entity 'Entity Name'"

**Other Commands:**
- Commands use their class name if no custom description
- Example: "Add Relation Command"

### History Order

Commands are displayed in execution order:

```
Most Recent Undo Command  ← Top
    ↓
Older Undo Commands
    ↓
Most Recent Redo Command
    ↓
Older Redo Commands       ← Bottom
```

The "current position" is between undo and redo stacks:
- Everything above can be undone (▲)
- Everything below can be redone (▼)

### Command Limits

- **In-Memory Limit:** Last 100 commands kept in memory
- **Display Limit:** Shows all commands in memory
- **Performance:** Handles 100 commands smoothly
- **Clearing:** Use Clear button to free memory

---

## Tips and Tricks

### 1. Quick Undo/Redo
- Use keyboard shortcuts for speed: Ctrl+Z and Ctrl+Y
- Panel updates automatically to show new state

### 2. Review Recent Work
- Scroll through the history panel to see what you've done
- Useful for remembering your workflow

### 3. Understanding Position
- Next undo command is **bold with blue highlight**
- Next redo command is **bold with orange highlight**
- Makes it clear what will happen when you undo/redo

### 4. Clear History Strategically
- Clear history after completing a major editing session
- Keeps memory usage low
- Cannot undo after clearing!

### 5. Panel Positioning
- Tab with Entity Inspector for convenient access
- Float the panel if you need constant visibility
- Dock on bottom if you prefer horizontal layout

---

## Keyboard Shortcuts

| Action | Shortcut | Panel Button |
|--------|----------|--------------|
| Undo   | Ctrl+Z   | ⟲ Undo       |
| Redo   | Ctrl+Y   | ⟳ Redo       |
| Clear  | (none)   | ✕ Clear      |

---

## Troubleshooting

### History Panel Not Visible

**Problem:** Can't find the History panel

**Solutions:**
1. Check if it's tabbed with Entity Inspector (click the "History" tab)
2. Check View menu for panel visibility options
3. Try resetting window layout (View → Reset Layout)

### Commands Not Showing

**Problem:** History panel is empty despite making changes

**Solutions:**
1. Ensure you're making changes to events/entities (Phase 2 commands)
2. Check that commands are executing successfully (no errors)
3. Try creating a new event to verify it appears

### Panel Not Updating

**Problem:** History panel doesn't update after commands

**Solutions:**
1. Check that history_changed signal is connected
2. Look for errors in the log file
3. Try restarting the application

### Theme Issues

**Problem:** Colors don't match current theme

**Solutions:**
1. Switch to a different theme and back
2. Restart the application
3. Check themes.json for valid theme data

---

## Technical Details

### Signal Connections

The history panel connects to CommandCoordinator:

- **history_changed** → Updates display
- **undo_clicked** → Calls coordinator.undo()
- **redo_clicked** → Calls coordinator.redo()
- **clear_history_clicked** → Calls coordinator.clear_history()

### Update Frequency

- Updates immediately after each command execution
- Updates after undo/redo operations
- Updates when history is cleared
- No polling - event-driven

### Memory Usage

- ~1KB per command in memory
- 100 command limit = ~100KB max
- Negligible impact on application performance

---

## FAQ

**Q: Can I click on a command to jump to that state?**  
A: Not yet. This is a future enhancement planned for Phase 4. Currently, you must undo/redo sequentially.

**Q: Why are some commands dimmed?**  
A: Dimmed commands have been undone. They're in the redo stack waiting to be redone.

**Q: What happens when I hit the 100 command limit?**  
A: Oldest commands are automatically removed to make room for new ones. They're still in the database (Phase 2).

**Q: Can I resize the history panel?**  
A: Yes! It's a dockable widget. You can resize, undock, and position it anywhere.

**Q: Does the panel work with all commands?**  
A: It shows all commands in the undo/redo stacks. Commands that don't support serialization (Phase 2) won't persist across sessions but still appear in the panel during the current session.

**Q: What's the difference between panel buttons and Edit menu?**  
A: They do the same thing. Use whichever is more convenient. The panel gives you visual feedback.

---

## What's Next?

### Future Enhancements (Phase 4+)

**Planned Features:**
- Click on any command to jump to that state
- Timeline scrubber for visual history navigation
- Search/filter commands
- Command grouping (collapse similar commands)
- Export/import history
- History statistics

**Nice-to-Have:**
- Command icons for visual distinction
- Command details on hover
- Keyboard navigation (arrow keys)
- Command categories/tags

---

## Feedback

If you encounter issues or have suggestions for the history panel:
1. Check the troubleshooting section above
2. Review log files for errors
3. Report issues with screenshots and log excerpts

---

**Phase 3 Status:** ✅ Complete and Production Ready

Enjoy the visual history panel!
