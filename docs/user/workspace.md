# Workspace and Layouts

## What this does

ProjektKraken uses one stable workspace with four destinations: Left, Center,
Right, and Bottom. Feature panels can move between those zones as tabs, while
the number of zones remains fixed.

Use this guide to arrange panels, save a layout and find your entries. Begin
with an open world. Layout changes affect application preferences; they do not
reorganize the world's Events, Entities or chronology.

(help-workspace-navigation)=

## Main workspace

- **Project** lists events, entities, and maps.
- **Event** edits the selected event.
- **Entity** edits the selected entity.
- **Timeline** shows dated events and the playhead.
- **Map** displays maps, markers, features, layers, and rasters.
- **Graph** visualizes relations.
- **Longform** arranges world content into a narrative outline.
- **AI Search** searches indexed world content.
- **History** shows available undo and redo operations.
- **Analysis** provides validation, temporal, and intelligence reports.

Use the checked entries under **View → Panels** to see which panels are open.
Check an entry to open its panel and activate its tab in its current zone;
uncheck it to close the panel. You can also close a panel with the close button
on its tab. Closing retains the panel's live content and editing state. Reopen it
from **View → Panels**, or use its activity-bar button where available.

Drag tabs within a zone's tab bar to change their order. Drag a tab onto another
zone's tab bar to move it, placing it before or after the tab at the drop position.
You can also right-click a tab and choose **Move to Left**, **Move to Center**,
**Move to Right**, or
**Move to Bottom**. Moving a panel preserves its current editing state.
Empty or hidden zones temporarily open as **Drop panel here** targets while a
tab is being dragged. They collapse again if the drag is cancelled or ends
somewhere else.
If all Center panels are closed, the empty zone shows
**Open a panel from View → Panels**. Closing the last panel in another zone hides
that zone; reopening a panel reveals it again.

When a panel becomes narrow, its primary action remains visible and secondary
actions move into a **⋯** menu. Buttons keep their full labels instead of being
compressed. Widening the panel restores actions to the toolbar automatically.

Use **View → Zones** to hide or show Left, Right, or Bottom. Center always
remains available. Opening a panel in a hidden zone reopens that zone at its
previous useful size.

## Save a layout

1. Arrange the panels and resize the four zones.
2. Open **Layouts → Save Current Layout…**.
3. Enter a layout name.
4. Confirm the name, then use the layout's **Restore** entry under **Layouts**
   to check the arrangement. Its **Delete** entry removes the saved layout.

Saved layouts contain panel locations, tab order, active tabs, closed panels,
zone sizes, and zone visibility. They do not contain the outer window's screen
coordinates.

Use **Layouts → Reset Layout** or **View → Reset Layout** to restore the
factory panel arrangement without moving or resizing the outer window. Layout
changes affect only the interface, not world content.

## Change the theme

1. Open **View → Theme** and select an available theme.
2. Check the workspace in that theme. The choice is retained with application
   preferences; select your previous theme through the same menu to return.

(help-explorer-browsing)=

## Find and organize Explorer entries

1. Open **Project** from **View → Panels** if the Explorer is closed.
2. Enter part of an existing entry's name in its search field.
3. Review the filters if the expected entry is missing, then select the result.
4. Clear the search and filters to show the full list again.

The selected entry opens through the normal draft safeguards. Sorting changes
display order, not saved dates or content; filtering never deletes entries.

(help-history-undo)=

## Review undo and redo history

Undo reverses a supported content change; Redo reapplies it. The History panel lists the
available operations. Clearing history removes these recovery steps without undoing
their effects. World restore and interface layout changes are not ordinary undoable
content edits.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.



(help-inspect-src-gui-dialogs-about-dialog-aboutdialog-init-close-btn)=

**Close** — Close the application information dialog.

(help-inspect-src-gui-dialogs-filter-dialog-filterdialog-init-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-keyboard-shortcuts-dialog-keyboardshortcutsdialog-init-close-btn)=

**Close shortcuts** — Close the keyboard-shortcut reference.

(help-inspect-src-gui-dialogs-raster-query-dialog-conditionrow-init-self-layer-combo)=

**Query layer** — Choose the raster layer tested by this spatial-query condition.

(help-inspect-src-gui-dialogs-raster-query-dialog-conditionrow-init-self-op-combo)=

**Comparison** — Choose how raster values are compared for this condition, such as
equality or a range.

(help-inspect-src-gui-dialogs-raster-query-dialog-conditionrow-init-self-value-spin)=

**Comparison value** — Set the value tested by this spatial-query condition, using the
selected layer's value scale.

(help-inspect-src-gui-dialogs-raster-query-dialog-conditionrow-init-self-max-spin)=

**Range maximum** — Set the upper value for a range condition. Other comparison types do
not require this bound.

(help-inspect-src-gui-widgets-empty-state-widget-emptystatewidget-add-action-button)=

**Start this task** — Start the task offered by this empty view. The linked task
describes its creation or recovery steps.

(help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-btn-refresh)=

**Refresh** — Reload the current EntityList view from its available data. Refresh does
not mean undo or backup restoration.

(help-inspect-src-gui-widgets-entity-list-entitylistwidget-init-self-list-widget)=

**Entity list** — Browse Entities in the current world and choose one to inspect.

(help-inspect-src-gui-widgets-event-list-eventlistwidget-init-self-btn-refresh)=

**Refresh List** — Reload the current EventList view from its available data. Refresh
does not mean undo or backup restoration.

(help-inspect-src-gui-widgets-event-list-eventlistwidget-init-self-list-widget)=

**Event list** — Browse Events in the current world and choose one to inspect.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-list-include)=

**Included filters** — Choose the tags or types that matching entries must satisfy. Any
and All control how these choices combine.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-radio-include-any)=

**Match any included filter** — Include entries matching at least one selected include
criterion.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-radio-include-all)=

**Match all included filters** — Include only entries matching every selected include
criterion.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-list-exclude)=

**Excluded filters** — Choose tags or types to exclude from this view. The adjacent Any
or All choice controls how exclusion criteria combine.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-radio-exclude-any)=

**Exclude any match** — Exclude entries that match at least one selected exclusion
criterion.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-radio-exclude-all)=

**Exclude all matches** — Exclude entries only when they match every selected exclusion
criterion.

(help-inspect-src-gui-widgets-filter-widget-filterwidget-setup-ui-self-check-case)=

**Case-sensitive filters** — Distinguish uppercase and lowercase when matching these
filter criteria.

(help-inspect-src-gui-widgets-history-panel-historypanelwidget-setup-ui-self-undo-btn)=

**⟲ Undo** — Reverse the most recent available content operation. This does not restore
a world backup or reset the workspace layout.

(help-inspect-src-gui-widgets-history-panel-historypanelwidget-setup-ui-self-redo-btn)=

**⟳ Redo** — Reapply the next available operation that was undone. A new content change
can replace the redo branch.

(help-inspect-src-gui-widgets-history-panel-historypanelwidget-setup-ui-self-clear-btn)=

**✕ Clear** — Clear the available undo/redo history. Existing world changes remain in
place, but these history steps can no longer be used to reverse them.

(help-inspect-src-gui-widgets-history-panel-historypanelwidget-setup-ui-self-command-list)=

**Undo history** — Review recorded content operations and their undo or redo status. Use
the Undo or Redo buttons to change content.

(help-inspect-src-gui-widgets-inspector-section-auxiliarysectionhome-init-show)=

**Show** — Reveal the indicated panel, section or information without creating a new
world entry.

(help-inspect-src-gui-widgets-inspector-section-auxiliarysectionhome-init-restore)=

**Return section here** — Move this inspector section back to its original tab location
while retaining its live editing state.

(help-inspect-src-gui-widgets-inspector-section-auxiliarysectionhome-init-return-button)=

**Return section here** — Move this inspector section back to its original tab location
while retaining its live editing state.

(help-inspect-src-gui-widgets-overflow-toolbar-overflowtoolbar-init-self-overflow-menu)=

**Overflow menu** — Open the Overflow menu menu to choose a related operation. Opening
the menu does not apply any of its actions.

(help-inspect-src-gui-widgets-overflow-toolbar-overflowtoolbar-add-button-action)=

**Overflow action** — Use the same operation as the corresponding toolbar control.
Inspection retains that control's own task explanation.

(help-inspect-src-gui-widgets-splitter-tab-inspector-draggabletabwidget-init-self-overflow-button)=

**Overflow button** — Open the Overflow button menu to choose a related operation.
Opening the menu does not apply any of its actions.

(help-inspect-src-gui-widgets-splitter-tab-inspector-draggabletabwidget-init-self-overflow-menu)=

**Overflow menu** — Open the Overflow menu menu to choose a related operation. Opening
the menu does not apply any of its actions.

(help-inspect-src-gui-widgets-splitter-tab-inspector-draggabletabwidget-show-layout-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-splitter-tab-inspector-draggabletabwidget-show-layout-menu-split)=

**Split active section below** — Place the active inspector section in a separate split
below. The underlying entry and description remain the same.

(help-inspect-src-gui-widgets-splitter-tab-inspector-splittertabinspector-populate-sections-split)=

**Split active section below** — Place the active inspector section in a separate split
below. The underlying entry and description remain the same.

(help-inspect-src-gui-widgets-splitter-tab-inspector-splittertabinspector-populate-sections-action)=

**Inspector section placement** — Show or move the indicated inspector section. Its live
editor and underlying entry are retained.

(help-inspect-src-gui-widgets-splitter-tab-inspector-splittertabinspector-populate-sections-restore)=

**Restore section** — Return this inspector section from its split to the ordinary tab
layout. This does not restore a world backup.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-refresh)=

**Refresh** — Reload the Explorer list from the current world. Refresh does not delete
entries or change their content.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-search-bar)=

**Search bar** — Filter Explorer entries by the text you enter. This narrows the visible
list without editing the entries.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-filter-combo)=

**Filter combo** — Filter the list by primary category type.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-filter)=

**Filter...** — Open advanced filtering options (tags, subtypes).

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-clear-filters)=

**Clear Filters** — Reset all search terms and active filters.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-sort-combo)=

**Sort combo** — Choose whether the Explorer is ordered by name, creation time, lore
date or type. Sorting does not alter event dates.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-sort-dir)=

**Sort dir** — Switch between Ascending and Descending order.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-init-self-btn-hashed-colors)=

**Hashed colors** — Color-code items by their unique Type category.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-unified-list-unifiedlistwidget-show-context-menu-export-action)=

**Export to Obsidian (.md)...** — Choose the destination and options for exporting the
selected content. Export produces a separate output; it does not delete the source
entries.

(help-inspect-src-gui-workspace-pane-container-panecontainer-show-tab-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-workspace-pane-container-panecontainer-show-tab-menu-action)=

**Move panel** — Move the panel to the indicated workspace destination while retaining
its current editing state.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-file-menu)=

**File** — Open the File menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-icon-library-action)=

**Icon Library...** — Import and manage project icons without selecting a marker.

(help-inspect-src-app-ui-manager-uimanager-create-file-menu-exit-action)=

**Exit** — Close the application through its normal unfinished-work safeguards.
Inspecting this action does not close the session.

(help-inspect-src-app-ui-manager-uimanager-create-edit-menu-edit-menu)=

**Edit** — Open the Edit menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-edit-menu-self-undo-action)=

**Undo** — Reverse the most recent available content operation. This does not restore a
world backup or reset the workspace layout.

(help-inspect-src-app-ui-manager-uimanager-create-edit-menu-self-redo-action)=

**Redo** — Reapply the next available operation that was undone. A new content change
can replace the redo branch.

(help-inspect-src-app-ui-manager-uimanager-create-view-menu-view-menu)=

**View** — Open the View menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-view-menu-panels-menu)=

**Panels** — Open the Panels menu to choose a related operation. Opening the menu does
not apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-view-menu-zones-menu)=

**Zones** — Open the Zones menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-view-menu-theme-menu)=

**Theme** — Open the Theme menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-view-menu-reset-action)=

**Reset Layout** — Restore the factory panel arrangement. This changes the interface
layout, not world content.

(help-inspect-src-app-ui-manager-uimanager-create-layouts-menu-self-layouts-menu)=

**Layouts** — Open the Layouts menu to choose a related operation. Opening the menu does
not apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-save-action)=

**Save current layout** — Name and save the current workspace arrangement for later
reuse. This does not save or back up world content.

(help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-no-layouts)=

**No saved layouts** — No named workspace layouts are available yet. Save Current Layout
creates one.

(help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-restore-action)=

**Restore layout** — Apply this saved workspace arrangement. World content is unchanged.

(help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-delete-action)=

**Delete saved layout** — Remove this named workspace layout. The current world's
content and backups are retained.

(help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-reset-action)=

**Reset Layout** — Restore the factory panel arrangement. This changes the interface
layout, not world content.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-timeline-menu)=

**Timeline** — Open the Timeline menu to choose a related operation. Opening the menu
does not apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-self-grouping-config-action)=

**Configure grouping** — Choose Timeline grouping tags, their order and whether multi-
tagged Events appear once or in each matching group.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-self-grouping-clear-action)=

**Clear grouping** — Remove the Timeline grouping configuration without deleting tags or
Events.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-calendar-action)=

**Calendar Configuration...** — Open the calendar configuration used to interpret and
format lore dates. Review calendar changes carefully before saving.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-settings-menu)=

**Settings** — Open the Settings menu to choose a related operation. Opening the menu
does not apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-self-auto-relation-action)=

**Auto-Create Relations from Wikilinks** — When enabled, saving a wiki link creates a
mentions relation to its target.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-self-longform-refresh-action)=

**Automatic Longform refresh** — Choose whether Longform automatically refreshes when
world content changes. This is separate from document membership and world backup
recovery.

(help-inspect-src-gui-dialogs-grouping-config-dialog-taglistitem-init-self-checkbox)=

**Include grouping tag** — Include this tag as a Timeline group. Its position in the
list determines priority in First Match mode.


(help-inspect-workspace-show-panel)=

**Panel visibility** — Check to open and activate the indicated workspace panel;
uncheck to close it. Its existing content and editing state are retained.

(help-inspect-workspace-close-panel)=

**Close panel** — Close this panel's tab while retaining its live content and
editing state. Reopen it from **View → Panels** in its current workspace zone.
Closing a panel does not delete world content.

(help-inspect-workspace-show-zone)=

**Workspace zone** — Show or hide the indicated group of workspace panels. Hidden panels and world content are retained.

(help-inspect-workspace-theme)=

**Interface theme** — Apply this interface theme. Theme changes preserve Help reading position and the authoring origin.

(help-inspect-workspace-saved-layout)=

**Saved workspace layout** — Choose Restore to apply this saved panel arrangement, or Delete to remove the named layout. These actions do not restore or delete world content.
