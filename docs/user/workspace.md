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

1. Open **Settings** and choose **Appearance**.
2. Under **Kraken**, choose the default theme. Under **This World**, choose an
   override or **Use Kraken default**.
3. Choose **Apply** to use the saved choice.

(help-settings-center)=

## Configure Kraken and the current world

Choose **Settings** in the main menu bar. It opens Settings Center directly,
without a dropdown. The window stays open while you work. All configuration
pages are reached here; other panels do not contain settings launchers.

Choose **Kraken** for local preferences or **This World — ‹name›** for portable
world configuration. Search finds settings in both scopes and shows each
result's scope. Pending edits survive page, scope and search changes.

| Category | Kraken | This World |
| --- | --- | --- |
| Appearance | Default theme | World theme override |
| Writing | Longform refresh; spelling, language and LanguageTool account | Auto-create relations from WikiLinks |
| Timeline | Snap to Events | Calendar, grouping order and tag colours |
| Analysis | Editorial checks | — |
| AI | Providers, models, connections, automatic indexing and summary settings | Creative preferences, prompts, templates and index exclusions |
| Graph | — | Visual lexicon: node and relation styles |
| Backups & storage | Backup interval, retention and locations | — |
| Advanced | Targeted preference and workspace resets | — |

**Apply** saves pending edits and keeps the window open. **OK** saves and closes.
**Cancel** discards changes since the last successful Apply. Closing with pending
changes offers **Apply / Discard / Keep editing**. World changes appear as one
undoable history action; local preferences and credentials are saved separately.
If a backend fails, the failed edits remain pending and the message explains the
failure. Successfully saved groups are not undone by a later Cancel.

**Pending** identifies unsaved edits; **Customized** identifies saved non-default
values. Inline controls such as Snap to Events apply immediately. If another
control changes a setting you are editing, choose **Use current value** or
**Keep my edit** before applying. Selecting another world protects pending world
changes while retaining independent Kraken drafts. World selection currently
requires an application restart.

### Reset selected preferences

Search for a preference to use **Reset selected setting**, or choose **Reset page**.
These actions stage eligible defaults until Apply. **Advanced → Reset Kraken
preferences** also stages local defaults, without resetting world configuration.
Calendar contents, authored tag colours and task-template resources are excluded
from generic resets. World theme reset restores inheritance from Kraken.

**Reset workspace state…** requires confirmation and Apply, then takes effect on
the next startup. It resets transient window/view state and filters. Worlds,
registered world locations and trust, credentials, named layouts, brush presets
and recent colour history remain intact. The launcher option `--reset-settings`
uses the same local preference boundary and does not clear those resources.

### Connections, portability and index changes

Provider connections, local model paths and credentials remain on this computer.
LanguageTool credentials use the OS credential store. A failed credential
migration retains the previous value rather than silently losing access.

WikiLink auto-relations and semantic-index exclusions are world policies. Existing
worlds import their legacy local values once; newly created worlds begin with
auto-relations off and no additional excluded attributes. Moving a world retains
its saved policy. Changing exclusions does not remove already indexed material:
apply the setting, then explicitly rebuild the complete index. Index rebuilding
and backup creation/restoration are operations, not effects of Apply.

(help-inspect-settings-center-search)=

**Search all settings** — Find configuration by its name, category or aliases in
both Kraken and This World. Search never examines credential values.

(help-inspect-settings-center-open)=

**Settings** — Open or raise the single configuration window directly from the
main menu bar. Reopening preserves pending changes.

(help-inspect-settings-center-scope)=

**Scope** — Kraken settings stay local. This World settings travel with the named
world. Switching scope preserves unapplied edits.

(help-inspect-settings-center-navigation)=

**Categories and results** — Select a category or search result to reveal its
controls. Pending and Customized identify different saved states.

(help-inspect-settings-center-preference)=

**Preference** — Edit the named setting in the displayed scope. Apply saves;
Cancel discards unapplied changes. Reset is available only for eligible defaults.

(help-inspect-settings-center-apply)=

**Apply** — Validate and save pending edits across pages. The window remains open;
failed groups remain pending with an explanation.

(help-inspect-settings-center-ok)=

**OK** — Apply pending edits and close after successful persistence.

(help-inspect-settings-center-cancel)=

**Cancel** — Discard changes since the last successful Apply and close. Already
acknowledged changes remain saved.

(help-inspect-settings-center-exclusions)=

**Index exclusions** — Enter comma-separated attribute names excluded from this
world's semantic index. Apply saves the policy; explicitly rebuild the full index
to replace existing indexed material. Attributes beginning with `_` are already
excluded by the indexing rules.

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

**Appearance** — Configure theme defaults and overrides under **Settings →
This World → Appearance**. The former View launcher is removed.

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

**Grouping** — Choose tags, their order and multi-tag behavior under
**Settings → This World → Timeline**. Choose Apply to save.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-self-grouping-clear-action)=

**Clear grouping** — Remove the Timeline grouping configuration without deleting tags or
Events.

(help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-calendar-action)=

**Calendar** — Configure lore date formatting under **Settings → This World
→ Timeline**. Review calendar changes carefully before Apply.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-settings-menu)=

**Settings** — Open or raise Settings Center directly from the main menu bar.
There is no Settings dropdown. Opening the window does not apply pending edits.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-self-auto-relation-action)=

**Auto-Create Relations from Wikilinks** — When enabled, saving a wiki link creates a
mentions relation to its target in this world. The policy travels with the world.

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

**Interface theme** — Configure the Kraken default and the world's optional override
in the Settings Center. Applying a theme preserves the authoring origin.

(help-inspect-workspace-saved-layout)=

**Saved workspace layout** — Choose Restore to apply this saved panel arrangement, or Delete to remove the named layout. These actions do not restore or delete world content.
