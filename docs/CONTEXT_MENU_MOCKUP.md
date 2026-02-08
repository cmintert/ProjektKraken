# Context Menu Visual Mockup

```
┌─ Document Outline ─────────────┐
│                                 │
│  📄 Chapter 1                   │
│    └─ 📝 Section 1.1 ◄──────────┼─ Right-click here
│    └─ 📝 Section 1.2            │
│  📄 Chapter 2                   │
│    └─ 📝 Section 2.1            │
│                                 │
└─────────────────────────────────┘

When right-clicking on "Section 1.2":

┌─────────────────────┐
│ Move Up             │  ◄── Enabled (has sibling above)
│ Move Down           │  ◄── Disabled (last child)
├─────────────────────┤
│ Promote             │  ◄── Enabled (depth > 0)
│ Demote              │  ◄── Enabled (has previous sibling)
├─────────────────────┤
│ Delete from Longform│  ◄── Always enabled
└─────────────────────┘

Context Menu States:
=====================

1. Top-level item (Chapter 1):
   ┌─────────────────────┐
   │ Move Up             │  ◄── Disabled (first item)
   │ Move Down           │  ◄── Enabled
   ├─────────────────────┤
   │ Promote             │  ◄── Disabled (already top level)
   │ Demote              │  ◄── Disabled (no previous sibling)
   ├─────────────────────┤
   │ Delete from Longform│  ◄── Enabled
   └─────────────────────┘

2. First child item (Section 1.1):
   ┌─────────────────────┐
   │ Move Up             │  ◄── Disabled (first child)
   │ Move Down           │  ◄── Enabled
   ├─────────────────────┤
   │ Promote             │  ◄── Enabled (can become sibling of parent)
   │ Demote              │  ◄── Disabled (no previous sibling)
   ├─────────────────────┤
   │ Delete from Longform│  ◄── Enabled
   └─────────────────────┘

3. Middle child item (Section 1.2 when multiple siblings exist):
   ┌─────────────────────┐
   │ Move Up             │  ◄── Enabled
   │ Move Down           │  ◄── Enabled
   ├─────────────────────┤
   │ Promote             │  ◄── Enabled
   │ Demote              │  ◄── Enabled (has previous sibling)
   ├─────────────────────┤
   │ Delete from Longform│  ◄── Enabled
   └─────────────────────┘

Action Examples:
================

Move Up:
--------
Before:                  After:
Chapter 1               Chapter 1
  Section 1.1             Section 1.2  ◄── Moved up
  Section 1.2  ◄──       Section 1.1
  Section 1.3             Section 1.3

Move Down:
----------
Before:                  After:
Chapter 1               Chapter 1
  Section 1.1  ◄──       Section 1.2
  Section 1.2             Section 1.1  ◄── Moved down
  Section 1.3             Section 1.3

Promote:
--------
Before:                  After:
Chapter 1               Chapter 1
  Section 1.1             Section 1.1
  Section 1.2  ◄──     Section 1.2  ◄── Promoted to same level as Chapter 1
  Section 1.3             Section 1.3

Demote:
-------
Before:                  After:
Chapter 1               Chapter 1
  Section 1.1             Section 1.1
  Section 1.2  ◄──          Section 1.2  ◄── Demoted (child of Section 1.1)
  Section 1.3             Section 1.3

Delete:
-------
Before:                  After:
Chapter 1               Chapter 1
  Section 1.1             Section 1.1
  Section 1.2  ◄──       [removed from outline]
  Section 1.3             Section 1.3

Note: Deleted items remain in the database and can be:
- Re-added to longform later
- Undone with Ctrl+Z
- Still accessed through Project Explorer
```

## Color Coding (in actual UI)

- **Events**: Blue text
- **Entities**: Orange text  
- **Disabled menu items**: Gray text
- **Enabled menu items**: White/Black text (depends on theme)
- **Separators**: Subtle gray lines

## Keyboard Navigation

Once context menu is open:
- **↑/↓**: Navigate between menu items
- **Enter/Space**: Activate selected action
- **Esc**: Close menu without action
- **Left-click**: Activate action
- **Click outside**: Close menu

## Mouse Behavior

- **Right-click on item**: Show context menu at cursor position
- **Right-click on empty space**: No menu displayed
- **Left-click during menu**: Activate action or close menu
- **Click outside menu**: Close menu without action
