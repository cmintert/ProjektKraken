# Longform Writing

## What this does

The Longform Editor arranges events and entities into a hierarchical narrative
without duplicating the underlying world content. All entities and events are
included automatically. New entries append without changing existing hierarchy.

## Build an outline

1. Open **View → Panels → Longform**.
2. Existing entities and events appear automatically. To restore a deliberately
   removed entry, choose **Add content…**, search for it, select it, then choose
   **Add to document**. It returns at the end of the outline. Entries already in
   the document keep their current arrangement.
3. Select an outline item and open **Outline actions**. **Move Up/Move Down**
   reorder siblings; **Demote** nests the item beneath its preceding sibling;
   **Promote** lifts it one level. The same actions are available by right-click.
   At narrow widths, controls remain available through **More actions (…)**.
4. Select an item, then choose **Open in inspector** to edit its underlying
   content. Clicking an entry keeps Longform visible when the inspector shares
   its workspace pane. An inspector already visible in a separate pane can
   follow completed clicks through the usual draft guards. Title and wiki links
   deliberately open their destination. Holding a press, dragging an outline
   entry or selecting document text does not switch inspector tabs.

Removing an item from Longform does not delete the event or entity from the
world. Choose **Remove from document** to exclude it deliberately. Child
sections lift one level and keep their relative order. Refresh, filtering and
export retain this choice, including after reopening. Undo restores the removed
section and its hierarchy. Exclusion applies only to that document.

**Delete from world…** is a separate action that deletes the underlying entity
or event, its connections and its membership in all documents. It asks for
confirmation; **Cancel** keeps it. Existing inspector draft and raster-reference
guards still apply. World deletion can be undone.

Choose **Find** (or Ctrl+F) to search document text. Enter finds the next result;
Shift+Enter finds the previous result; Escape closes the local search or content
chooser. Adding and arranging membership do not select another inspector entry.

## Export

Use **File → Export → Export Longform to Markdown…** for one document. Use
**Export as Obsidian Vault…** when you want linked Markdown files suitable for
an Obsidian workspace.

## Tips and gotchas

- Enable **Settings → Auto-Refresh Longform Editor** when you want changes to
  appear immediately.
- Very large documents may be easier to maintain as several top-level sections.
- Wiki links remain useful after Markdown or Obsidian export.
