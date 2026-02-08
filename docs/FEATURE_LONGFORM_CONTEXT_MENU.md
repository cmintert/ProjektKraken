# Longform Outline Context Menu Feature

## Overview

The Longform Outline widget now includes a comprehensive right-click context menu for managing document structure. This enhancement provides an intuitive interface for users who prefer mouse-based interactions over keyboard shortcuts.

## Features

### Context Menu Actions

Right-clicking on any item in the Longform Outline reveals a context menu with the following options:

#### 1. **Move Up**
- Moves the selected item up one position among its siblings
- Maintains the same parent and depth level
- Disabled when item is already at the top of its sibling group
- **Keyboard Alternative**: None (new feature)

#### 2. **Move Down**
- Moves the selected item down one position among its siblings
- Maintains the same parent and depth level
- Disabled when item is already at the bottom of its sibling group
- **Keyboard Alternative**: None (new feature)

#### 3. **Promote**
- Reduces the item's depth by one level
- Changes parent to parent's parent
- Equivalent to moving left in the outline hierarchy
- Disabled when item is already at top level (depth 0)
- **Keyboard Shortcut**: Ctrl+[ (Cmd+[ on Mac)

#### 4. **Demote**
- Increases the item's depth by one level
- Makes the item a child of its previous sibling
- Equivalent to moving right in the outline hierarchy
- Disabled when there's no previous sibling to become parent of
- **Keyboard Shortcut**: Ctrl+] (Cmd+] on Mac)

#### 5. **Delete Item**
- Completely deletes the selected Event or Entity
- This is a permanent deletion (can be undone with Ctrl+Z)
- Use when you want to remove an item entirely from your project
- **Warning**: This deletes the actual item, not just its placement in the outline
- **Keyboard Alternative**: None

## User Experience Improvements

### For Non-Power Users
- **Visual Discovery**: Context menu makes operations discoverable without memorizing shortcuts
- **Clear Labeling**: Action names clearly describe what will happen
- **Smart Disabling**: Invalid operations are grayed out, preventing errors
- **Familiar Pattern**: Right-click menu follows standard GUI conventions

### For All Users
- **Efficiency**: Quick access to common operations
- **Flexibility**: Choice between keyboard shortcuts and mouse actions
- **Visual Feedback**: Menu items show current state (enabled/disabled)
- **Undo Support**: All operations are fully reversible

## Technical Implementation

### Signal Flow
```
User Right-Click → Context Menu Display
User Selects Action → Signal Emission
Outline Widget → Editor Widget → Longform Manager
Manager → Command Creation → Command Execution
Command → Database Update → UI Refresh
```

### Architecture Components

1. **LongformOutlineWidget** (`src/gui/widgets/longform/outline.py`)
   - Implements context menu display
   - Emits signals for each operation
   - Manages action enable/disable logic

2. **LongformEditorWidget** (`src/gui/widgets/longform/editor.py`)
   - Relays signals from outline to manager
   - Maintains clean separation of concerns

3. **LongformManager** (`src/app/longform_manager.py`)
   - Translates user actions into commands
   - Handles position calculations for move up/down
   - Emits command requests to command system

4. **Commands** (`src/commands/longform_commands.py`)
   - MoveLongformEntryCommand (for move up/down)
   - PromoteLongformEntryCommand
   - DemoteLongformEntryCommand
   - RemoveLongformEntryCommand

### Position Calculation Logic

For Move Up/Down operations, the system calculates new positions using fractional positioning:

- **Move Up**: Position = (previous_sibling.position + before_previous.position) / 2
- **Move Down**: Position = (next_sibling.position + after_next.position) / 2
- If no adjacent item exists, uses ±100 offset from current position

This approach ensures consistent ordering without requiring reindexing of all items.

## Usage Examples

### Reorganizing a Chapter Structure

**Initial Structure:**
```
Chapter 1
  Section 1.1
  Section 1.2
  Section 1.3
Chapter 2
```

**To move Section 1.3 above Section 1.1:**
1. Right-click on "Section 1.3"
2. Select "Move Up" twice
3. Section 1.3 is now the first child of Chapter 1

**To promote Section 1.2 to a chapter:**
1. Right-click on "Section 1.2"
2. Select "Promote"
3. Section 1.2 becomes a top-level item

### Cleaning Up the Outline

**To remove an item from longform without deleting it:**
1. Right-click on the item
2. Select "Delete from Longform"
3. Item is removed from outline but remains in database
4. Can be re-added later or undone with Ctrl+Z

## Testing

Comprehensive test coverage includes:

- Context menu creation and display
- Signal emission for all operations
- Enable/disable state logic
- Boundary conditions (top/bottom items)
- Signal flow through widget chain

See: `tests/unit/test_longform_outline_context_menu.py`

## Future Enhancements

Potential additions to consider:

1. **Duplicate Item**: Clone the selected item in the outline
2. **Insert New**: Create a new placeholder event/entity at this position
3. **Change Type**: Convert between Event and Entity
4. **Set Title Override**: Quick edit of display title
5. **Copy/Paste**: Cut/copy/paste items within the outline

## Related Documentation

- **User Guide**: `docs/USER_GUIDE.md` (Longform Builder section)
- **Keyboard Shortcuts**: `docs/WORKFLOWS.md` (Outline editing)
- **Architecture**: `docs/ARCHITECTURE.md` (Command Pattern)
- **API Reference**: `docs/API_REFERENCE.md` (Longform components)

## Accessibility

The context menu follows standard accessibility patterns:

- Keyboard navigation with arrow keys
- Action activation with Enter/Space
- Visual state indicators for disabled items
- Tooltip support (if configured)

## Conclusion

This feature significantly improves the usability of the Longform Outline for users of all experience levels, making document structure manipulation more intuitive and discoverable while maintaining full backward compatibility with existing keyboard shortcuts.
