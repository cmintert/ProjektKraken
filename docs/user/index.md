(help-manual-home)=

# User Manual

This manual describes the capabilities available in the current ProjektKraken
desktop application. It is organized around tasks rather than internal
implementation.

(help-manual-inspect)=

## Help while you work

Press **F1** or choose **Help → Help for current task** to open an explanation
for the focused control, active map operation, dialog or panel. If no task is
mapped, Help opens this manual. **Help → User manual** opens the manual directly.

Help appears in a separate, resizable window. It leaves your selection, unsaved
writing, map edits and viewed time in place. **Back** and **Forward** navigate
only through Help pages. **Manual** returns to the manual home.

Help keeps the displayed topic when you continue working. Press F1 again from
your work, or choose **Refresh context**, to request another explanation.
**Return to work**, Escape in Help, and closing the Help window restore focus to
the originating control when it is still available. Help does not apply or
cancel an unfinished operation, including while Focus writing is active.

The manual is available offline in the matching release. If Help cannot load,
follow its local recovery instruction. External references do not automatically
open a browser.

Choose **Search** in Help, or press **Ctrl+F while Help has focus**, to search
the complete offline manual. Results update after a short pause while you type.
Single click selects a result; double-click or Enter opens it. Enter in the query
opens the selected result, or the first result after a new query. Search keeps
your query when you open a topic. Escape hides search first, then returns from
Help to your work.

Point at a supported control and press **Shift+F1** to read its explanation
without clicking it. For keyboard use, focus the control with Tab and press
**Ctrl+Shift+F1**. In an open menu, this explains the highlighted action.
Alternatively, choose **Help → Inspect control**, then click the control.
The inspection click does not activate the control or change a map selection.
Escape dismisses inspection or its explanation before affecting your work.
Use **Read the task in Help** in an explanation for the full procedure.
The explanation describes the software operation; it does not read or diagnose
your entered values. Associated form labels can also be inspected. The same
information remains available through the manual and search.
If no explanation is available at the target, the popup says so; press F1 for
Help about your current task.

## Where Inspect control works

Start in **Project Explorer**: inspect **New…**, **Delete**, the search field or
the filtering controls. You can also inspect inspector fields, writing tools,
Timeline navigation and map tools. Disabled controls explain their purpose
without becoming enabled.

To inspect menu actions, enter inspection and move over a menu heading to reveal
its items, then click the item to explain it. Overflow items use the same meaning
as their toolbar controls. The inspection click does not run the action.

| Surface | Examples to inspect |
| --- | --- |
| {ref}`Explorer <help-explorer-browsing>` | New, Delete, search, filters and sorting. |
| {ref}`Inspectors <help-authoring-details>` | Name, type, description, attributes, tags, gallery and Connections actions. |
| {ref}`Writing <help-writing-edit>` | Formatting, Rich/Source, links, headings, Focus writing and spelling settings. |
| {ref}`Timeline <help-timeline-viewing>` | Play, step, Go to date, Set Current Time and grouping. |
| {ref}`Map and Layers <help-map-features>` | Marker/path/region tools, feature actions, visibility, appearance and raster tools. |
| {ref}`Connections <help-relations-create>` | Create/refine, direction, timing boundaries and state-change fields. |
| {ref}`Longform <help-longform-recovery>` | Content membership, outline arrangement, find, export and publishing controls. |
| {ref}`Graph <help-graph-exploring>` | Search, filters, temporal mode and type styling. |
| {ref}`Search and Analysis <help-ai-search>` | World search, result limits, analysis scope, findings and report export. |
| {ref}`World tools <help-world-transfer>` | Import/export choices, review fields, backups and world management. |

The specialist explanations below provide more detail about controls whose
meanings are easy to confuse.

| Explanation | Where to find the supported controls |
| --- | --- |
| {ref}`Date precision <help-date-precision>` | Expand **Date details & uncertainty…**: qualification, month, day and **Possible date limits…**. |
| {ref}`Event timing <help-event-timing>` | Enable **Event has duration**, then open **End date / duration…**: Duration and the Duration / End Date choices. |
| {ref}`Historical Entity editing <help-entity-historical-editing>` | The destination prompt when adding an attribute: **Entity baseline** and **At this time**. |
| {ref}`Value Source <help-entity-value-source>` | The Entity description's **Source** label and the attribute table's Source column. |
| {ref}`Relation creation <help-relations-create>` | **More actions → Add detailed relation…**: the direction/reverse-connection control. |
| {ref}`Relation timing <help-relations-timing>` | Relation refinement/full editor: Meaning, start/end boundaries and shared-event binding controls. |
| {ref}`Historical geometry <help-map-historical-geometry>` | **Manage historical borders… / Manage historical paths…**: dated state and Base Geometry rows. |
| {ref}`Feature visibility <help-map-visibility>` | **Visibility dates…**: Exists from and Exists until. |
| {ref}`Timeline viewing <help-timeline-viewing>` | The Viewing / World current time readout and visible time-marker lines. |

Open the relevant surface before entering inspection. Decorative text, empty
space, scrollbars, Help's own controls and system-owned file dialogs do not have
separate explanations. A forbidden cursor marks an unsupported target. Use **F1**
for the current task, or search the manual, if a target has no explanation.

```{toctree}
:maxdepth: 1

getting-started
workspace
events-entities-relations
wiki-editor-markdown
timeline-and-calendars
maps
longform
search-ai-and-analysis
import-export-and-backups
keyboard-shortcuts
troubleshooting
```

ProjektKraken saves world content as you work. Undo and redo remain available
for supported content changes; opening worlds, changing the window layout, and
restoring backups are not ordinary undoable edits.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-help-menu)=

**Help** — Open the Help menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-current-action)=

**Help for current task** — Open the offline Help route for this task. Help leaves the
authoring draft and selection in place.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-manual-action)=

**User manual** — Open the offline User Manual. Its search covers the complete packaged
manual.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-inspect-action)=

**Inspect control** — Enter inspection mode to read a control explanation without
activating the operation.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-shortcuts-action)=

**Keyboard Shortcuts...** — Show the application shortcut reference. Reading the
reference does not execute a shortcut.

(help-inspect-src-app-ui-manager-uimanager-create-help-menu-about-action)=

**About ProjektKraken** — Show application version and project information without
changing the world.

## Standard dialog actions

(help-inspect-dialog-accept)=

Accept the current dialog choices after validation. Review the fields first; inspecting
this button does not accept or close the dialog.

(help-inspect-dialog-cancel)=

Close this dialog without accepting its pending choices. Work already saved before the
dialog opened is not undone.

(help-inspect-dialog-apply)=

Apply the current dialog choices without necessarily closing it. Review the task for the
resulting changes.

(help-inspect-dialog-destructive)=

Perform the destructive operation described by this dialog. Review its scope and
recovery options before accepting; inspection does not run it.

(help-inspect-dialog-reset)=

Reset the choices described by this dialog. This is separate from restoring an entire
world backup.

(help-inspect-dialog-help)=

Open the Help associated with this dialog without accepting its choices.
