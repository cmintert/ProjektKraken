(help-manual-home)=

# User Manual

This manual describes the capabilities available in the current ProjektKraken
desktop application. It is organized around tasks rather than internal
implementation.

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

For the reviewed date, duration, source, relation, geometry, existence and time
controls, focus the control and press **Shift+F1** to read its explanation.
Alternatively, choose **Help → Inspect control**, then click the control.
The inspection click does not activate the control or change a map selection.
Escape dismisses inspection or its explanation before affecting your work.
Use **Read the task in Help** in an explanation for the full procedure.
Other controls inherit ordinary F1 task help; they do not each have a separate
inspection explanation. Non-focusable labels can also be inspected, and their
topics remain available through the manual and search.

## Where Inspect control works

Start with the Timeline text **Viewing: … World current time: …**, or open an
Event and inspect **Duration**. These are examples of the limited set of controls
with individual explanations. Most navigation and toolbar buttons are outside
this set and show the forbidden cursor in inspection mode. Use **F1** for their
ordinary task or panel Help instead.

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

Open the relevant surface before entering inspection. Where a control has an
associated registered label, that label also provides the explanation. Inspecting
a target explains its meaning without activating it. This guide does not add
inspection coverage to every control.

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
