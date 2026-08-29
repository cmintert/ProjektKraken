# Workspace and Layouts

## What this does

ProjektKraken uses one stable workspace with four destinations: Left, Center,
Right, and Bottom. Feature panels can move between those zones as tabs, while
the number of zones remains fixed.

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

Choose any panel under **View → Panels**. Kraken reveals the zone where that
panel currently lives and activates its tab. The activity bar provides quick
access to the most frequently used panels.

Drag a tab onto another zone's tab bar to move it. You can also right-click a
tab and choose **Move to Left**, **Move to Center**, **Move to Right**, or
**Move to Bottom**. Moving a panel preserves its current editing state.
Empty or hidden zones temporarily open as **Drop panel here** targets while a
tab is being dragged. They collapse again if the drag is cancelled or ends
somewhere else.

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
4. Restore or delete it later from the **Layouts** menu.

Saved layouts contain panel locations, tab order, active tabs, zone sizes, and
zone visibility. They do not contain the outer window's screen coordinates.

Use **Layouts → Reset Layout** or **View → Reset Layout** to restore the
factory panel arrangement without moving or resizing the outer window. Layout
changes affect only the interface, not world content.

## Change the theme

Open **View → Theme** and select an available theme. The choice applies to the
workspace and is retained with your application preferences.
