# Longform Writing

[Back Up and Restore](import-export-and-backups.md#back-up-and-restore)

(help-longform-recovery)=

## Organize Longform and recover safely

Longform arranges Events and Entities into a narrative outline without duplicating their
underlying content. Entries are included automatically; arranging them changes the
document’s structure, not the world’s chronology.

1. Open **View → Panels → Longform**.
2. Use **Outline actions** to reorder, promote or demote sections.
3. Choose **Open in inspector** to edit an entry’s underlying content.
4. If an entry was deliberately removed from the document, use **Add content…** to include it again.

**Remove from document** excludes an entry from that document without deleting it from
the world. Its children move up one level. Refresh and reopening preserve the exclusion;
Undo restores the removal and hierarchy.

**Delete from world…** is different: it deletes the underlying entry and affects its
connections and document memberships. Review the confirmation carefully.

If displayed content appears out of date, use **Refresh**, or enable **Settings →
Auto-Refresh Longform Editor**. Refresh updates the view; it does not recover deleted
world content.

For recovery, use Undo for supported edits or **File → Backup & Restore** for saved
database backups. Restoring replaces saved world data, is not ordinarily undoable and
requires unfinished edits to be resolved. Database backups do not contain assets; use a
portable world package when images and maps must travel with the world.

**Example:** Remove Ada’s biography from one narrative without deleting Ada. Add it back
through **Add content…** if you want it in that document again.

**Related:** {ref}`Add details <help-authoring-details>` · {ref}`Writing and links
<help-writing-links>`

See {ref}`Backup and restore <help-backup-restore>` and {ref}`World transfer
<help-world-transfer>` for the full recovery and asset-transfer procedures.

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
