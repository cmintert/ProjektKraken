# Longform Writing

Use Longform to arrange existing Events and Entities into a document. Begin
with an open world containing the entries you want to include. Their saved
content remains shared with their inspectors; the outline controls membership
and order. See [portability and recovery](portability-and-recovery.md) when
deciding between publication, export and backup.

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

For recovery, use Undo for supported edits. Follow the canonical
{ref}`backup and restore procedure <help-backup-restore>` when replacing saved
world data; it has different consequences from restoring document membership.

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

(help-longform-export)=

## Export

Open **File → Import / Export… → Export** and choose the publication or lore
format that matches your goal. Follow [Publish Longform](import-export-and-backups.md#publish-longform)
for Markdown, Word or PDF in authored outline order. For separate linked notes,
follow [Export Lore](import-export-and-backups.md#export-lore).

Review the output preview and warnings before **Create output**, then open the
resulting file to check it. Export does not change the world's outline or text.

## Tips and gotchas

- Enable **Settings → Auto-Refresh Longform Editor** when you want changes to
  appear immediately.
- Very large documents may be easier to maintain as several top-level sections.
- Wiki links remain useful after Markdown or Obsidian export.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-add)=

**Add content…** — Choose existing entries to include in this document. Re-adding an
excluded entry does not create a duplicate world entry.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-outline-actions)=

**Outline actions** — Select an outline item to arrange or remove it.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-outline-actions-menu)=

**Outline actions menu** — Open the Outline actions menu menu to choose a related
operation. Opening the menu does not apply any of its actions.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-open-inspector)=

**Open in inspector** — Open the selected section’s underlying Event or Entity in its
inspector. This deliberately navigates away from reading and protects unfinished edits.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-refresh)=

**Refresh** — Refresh the displayed document from current world content. Deliberately
excluded entries stay excluded; refresh does not recover deleted world entries.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-filter)=

**Filter...** — Choose which items are shown in Longform. Filtering leaves the saved
world entries and connections unchanged.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-clear-filters)=

**Clear document filters** — Remove the active Longform filters so included sections are
visible again. Document membership is retained.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-export)=

**Export Markdown** — Save this Longform document as Markdown without deleting or moving
its world entries.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-export-vault)=

**Export as Vault** — Export each entity and event as separate Obsidian-compatible .md
files.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-publish)=

**Publish Locally** — Start or stop local publishing for this document. Local publishing
is separate from LAN sharing; inspecting this control does not start a server.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-share-lan)=

**Share on LAN...** — Start or stop sharing this document on the local network. This
changes network exposure; review the sharing controls before enabling it.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-btn-find)=

**Find in document** — Show the text-search controls for this Longform document.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-search-input)=

**Search input** — Find matching items in Longform. Searching changes the displayed
matches without editing their content.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-prev)=

**Previous match** — Move to the previous text match in this Longform document.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-next)=

**Next match** — Move to the next text match in this Longform document.

(help-inspect-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-btn-close)=

**Close find** — Hide the document's text-search controls and return to reading.

(help-inspect-src-gui-widgets-longform-membership-longformmembershipwidget-init-self-search)=

**Find document content** — Search existing Events and Entities to add to this Longform
document.

(help-inspect-src-gui-widgets-longform-membership-longformmembershipwidget-init-self-results)=

**Available entries** — Select an existing Event or Entity to add to the document.
Adding membership does not duplicate the entry.

(help-inspect-src-gui-widgets-longform-membership-longformmembershipwidget-init-self-add-button)=

**Add to document** — Select an existing entity or event first.

(help-inspect-src-gui-widgets-longform-membership-longformmembershipwidget-init-self-cancel-button)=

**Cancel** — Cancel this LongformMembership operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-action)=

**Outline action unavailable** — Select an outline item before arranging it or changing
its membership.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-move-up-action)=

**Move Up** — Move the selected item earlier in the displayed order. This changes
arrangement rather than its date.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-move-down-action)=

**Move Down** — Move the selected item later in the displayed order. This changes
arrangement rather than its date.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-promote-action)=

**Promote** — Lift the selected outline section one level while retaining its underlying
world entry.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-demote-action)=

**Demote** — Nest the selected outline section beneath its preceding sibling without
creating a new world entry.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-remove-action)=

**Remove from document** — Keep the world entry and lift its child sections.

(help-inspect-src-gui-widgets-longform-outline-longformoutlinewidget-populate-actions-menu-delete-action)=

**Delete from world** — Delete the selected section's underlying world entry after
confirmation. Remove from document instead keeps the world entry.

(help-inspect-empty-longformeditorwidget-setup-ui-289)=

Choose existing entries to include in this document without creating duplicate world
entries.

(help-inspect-empty-longformeditorwidget-setup-ui-292)=

Clear the active document filters so its included sections are visible again. This does
not delete document membership or world entries.

(help-inspect-view-src-gui-widgets-longform-editor-longformeditorwidget-setup-ui-self-outline)=

**Longform outline** — Choose a section to read, or arrange its document membership with
Outline actions. Removing membership differs from deleting the world entry.
