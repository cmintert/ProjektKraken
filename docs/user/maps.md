# Maps, Layers, and Rasters

## What this does

Maps combine an image with placed events and entities, drawn paths and regions,
temporal trajectories, nested detail maps, and optional editable raster layers.

## Create and open a map

1. Open the Explorer's **New** menu.
2. Select **Create Map**.
3. Choose an image and provide a name.
4. Select the map in Project or the Map panel.

(help-map-features)=

## Add markers and features

Use markers to place entries on a map, paths to draw routes or lines, and regions to
draw areas.

1. Open a map.
2. Choose **Add Marker**, **Draw Path**, or **Draw Region**.
3. Place the marker preview or draw the vertices.
4. Choose **Confirm** or press **Enter** to finish. Choose **Cancel** or press **Escape** to discard the draft.

Before confirming a marker, click elsewhere to move its preview. Paths require at least
two vertices; regions require at least three.

Click an existing feature to select it on the map. Choose **Open in inspector** when you
deliberately want to open its linked Event or Entity. Selection can update an inspector
already visible in another workspace zone, subject to draft safeguards; it does not
automatically replace a hidden inspector or one sharing the map’s zone.

Use **Feature actions** for appearance changes, historical geometry and other feature
operations. The actions are also available through Layers and the toolbar overflow at
narrow widths.

**Example:** Place Ada’s court as a marker and draw the kingdom as a region. Use a
trajectory for movement over time, historical geometry for changing borders, and
existence dates for when a feature is present.

**Related:** {ref}`Historical geometry <help-map-historical-geometry>` · {ref}`Feature
visibility <help-map-visibility>` · {ref}`Map trajectories <help-map-trajectories>`

### Feature appearance and sizing

Select a point marker and choose **Feature actions > Change icon…** to use a bundled icon,
reuse an icon stored in the world, or import an SVG, PNG, JPG/JPEG, or WebP
file. Imported icons are copied into the portable world's `assets/images/`
folder. SVG markers support fill and border styling. Raster icons retain their
original colours and transparency; their vector-only styling actions are
disabled, but their size controls remain available.

Point-marker icons scale with the map by default. This gives character tokens
and location symbols a stable footprint: zooming in makes both the map and its
icons larger. Choose **Feature actions > Advanced appearance > Size &
Zoom…** to set that marker's behavior and size. Uncalibrated maps use a
percentage of total map width; calibrated maps also offer metres and
kilometres as alternate representations of the same map-space footprint.

Choose **Fixed on screen** for an individual overview symbol that should remain
readable at every zoom level. Different markers on the same map may use
different modes and sizes. Labels stay screen-sized and collision-managed, but
remain visually attached to their marker instead of drifting away from it.

Use **Feature actions > Advanced appearance > Copy appearance** and **Paste appearance** to transfer a
marker's icon, colours, border, sizing, and icon anchor without copying its
position, layer, timeline validity, or linked object. Choose **Feature actions >
Edit appearance** for direct manipulation: drag the corner handle to resize the
marker and move the anchor handle to select the point in the artwork that
should remain attached to the map coordinate. The edit banner shows the active
size and anchor percentages. Choose **Confirm** or press **Enter** to save the
edit as one undoable change; **Cancel** or **Escape** restores the previous
appearance. Use
**Reset Anchor to Centre** to return to the legacy centred attachment.

Snapping helps align new or edited vertices with existing geometry. Paths need
at least two vertices; regions need at least three.

Select a path and choose **Feature actions > Edit appearance…** to select its stroke width,
colour, and line pattern. Available patterns are **Solid**, **Dotted**,
**Short Dash**, **Long Dash**, and **Dash Dot**. The chosen pattern applies to
the whole path and is saved as part of its global feature style.

(help-map-historical-geometry)=

## Dated path and region geometry

Historical geometry lets one map feature have different shapes at different dates.
**Base Geometry** supplies its shape before the first dated state.

1. Move the Timeline playhead to the date of the change.
2. Select the region or path.
3. Choose **Feature actions → Edit border at current date** or **Edit path at current date**.
4. Edit the working copy, then choose **Confirm** or press **Enter**. **Cancel** or **Escape** discards the edit.

At an existing state’s exact date, this edits that state. At another date, Kraken
prepares a new state from the shape currently shown. Confirming saves the change as one
undoable operation.

The latest applicable state remains in effect until the next state. Shapes switch at
their dates; they do not gradually morph.

Use **Manage historical borders…** or **Manage historical paths…** to edit Base
Geometry, change a state’s date or delete a dated state. Deleting a state reveals the
preceding shape.

**Example:** To record a border change in 962, go to the intended date in 962 and edit
the border there. Earlier dates keep their earlier shape.

Geometry changes do not change **Exists from / Exists until**. Appearance, labels and
layer assignment remain global.

**Related:** {ref}`Feature visibility <help-map-visibility>` · {ref}`Timeline viewing
<help-timeline-viewing>` · {ref}`Map features <help-map-features>`

(help-control-map-historical-geometry)=

> Base Geometry is the undated shape used before a dated geometry state takes effect. A dated state replaces the border or path from its effective date until a later state takes over. Edit the border at the current date to work on the playhead's historical shape; manage historical states to choose Base Geometry or a dated state deliberately. Changing a shape does not set Exists from or Exists until. Those controls govern whether the feature exists, independently of its vertices. Inspecting a state leaves the current selection and unfinished working copy intact.

Base Geometry cannot be deleted, and two geometry states cannot share a date. Point
markers use ordinary positions or trajectories rather than dated border states.

(help-map-visibility)=

## Temporal visibility

Visibility dates describe when a marker, path or region is present. They are independent
of its shape and ordinary layer visibility.

1. Select the feature on the map or in **Layers**.
2. Choose **Feature actions → Visibility dates…**.
3. Set **Exists from** and **Exists until**, choosing **Manual date**, **Date not known**, or **Unbounded** for each side.
4. Confirm the changes.

**Date not known** means the boundary is unresolved. **Unbounded** means there is no
limit on that side. Partial dates retain their precision; uncertain presence is marked
with reduced opacity and `(?)`.

The start is inclusive and the end is exclusive. With exact boundaries, a feature is
present at its start but absent at its end transition.

Features outside their dates remain available in Layers with a clock badge and dimmed
name. Use **Jump to valid time** to inspect one. An eye-slash instead indicates manual
hiding.

**Example:** An old fortress ceases to exist when its replacement begins. Give the old
feature an end boundary matching the replacement’s start to avoid an overlap or gap.

Changing existence dates does not redraw a border or path. Use historical geometry for
shape changes.

**Related:** {ref}`Historical geometry <help-map-historical-geometry>` · {ref}`Timeline
viewing <help-timeline-viewing>` · {ref}`Map features <help-map-features>`

(help-control-map-visibility)=

> Exists from and Exists until describe when a map feature is present, independently of its border or path geometry. An unknown boundary records unresolved timing; an unbounded side has no limit. Exists until is an exclusive boundary, so the feature is no longer present at that transition. Choose a date or boundary meaning appropriate to the world instead of changing geometry to hide a feature. A dated geometry state changes its shape, not its existence dates. Inspection does not move the playhead, toggle a layer or apply an unfinished map edit.

Group dates apply to their vector features. **Use Playhead** copies the active lore date
into either boundary.

### Ghosts, locking and uncertain presence

**Temporal Ghosts** is an optional, session-only authoring view. It shows
outside-time features as faint dashed shapes while still respecting manual,
group, and zoom hiding. Ghosts can be selected, but cannot be dragged or edited
directly; use their menu to jump to a valid date, change validity, or reveal the
feature in Layers.

Use the lock icon at the right of a point marker, path, or region in the layer
tree to protect it from map interaction. You can also select it in Layers or on
the map and choose **Feature actions > Lock**, or right-click the unlocked feature and
choose **Lock**. A locked feature remains visible and shows its hover tooltip,
but cannot be selected, opened, or moved on the map.
Selecting a locked feature in Layers exposes **Feature actions > Unlock**.
Right-clicking it also offers only **Unlock**. Layers keeps hidden and absent
features available: visibility-date management remains accessible, while edits
requiring a visible canvas representation explain that prerequisite.

Trajectory dates continue to answer where an entity would be. Temporal
validity separately decides whether it exists on the map. A normal selected
route disappears with an invalid owner, while an already-open trajectory or
geometry editing session remains visible as an authoring aid. Playhead-aware
spatial generation also excludes features that do not exist at the requested
date.
When the owner's presence is possible or unknown at the playhead, a normal
selected route stays visible with reduced opacity and a tooltip explaining the
uncertainty; `(?)` marks its keyframe labels.

(help-map-trajectories)=

## Create or edit a trajectory

A trajectory places an Entity marker at different locations over time. It records
movement or changes of location without changing the Entity’s written description or
relations.

1. Select an Entity marker and choose **Feature actions → Create journey**.
2. Place the second location, move the Timeline to its later arrival date, then choose **Accept Second Location**.
3. Add further locations as needed.
4. Choose **Apply** to save the complete journey as one undoable change, or **Cancel** to discard it.

For an existing journey, choose **Edit journey**. Changes remain in a working copy until
you apply them. Event markers cannot have trajectories.

**Timed locations** carry dates you explicitly record. **Route points** shape the path
between them, with dates calculated from distance. Moving the Timeline alone does not
change a location’s date; use **Edit Date** or **Use Playhead** deliberately.

Choose **Travel** for movement along a route. Matching consecutive positions record a
**Stay**. **Relocation** holds the previous position until the next date, then switches
immediately without implying a travelled route.

**Example:** Record Ada at her court, travelling to a fortress, then staying there. If
the evidence establishes only a later location without a known route, use Relocation.

Before the first dated location, the ordinary marker position applies. After the last,
the final location is retained. Feature visibility dates still determine whether the
marker is present.

**Related:** {ref}`Map features <help-map-features>` · {ref}`Timeline viewing
<help-timeline-viewing>` · {ref}`Feature visibility <help-map-visibility>`

### Edit the working copy

- Drag a dated point to change its position.
- Choose **Add Location** to add a point at the playhead. It begins at the
  entity's resolved position at that date. Leave it there to record a stay, or
  drag it to a new place.
- Drag a midpoint handle to insert a new dated point between two existing
  travel locations when you want to shape the route. Midpoint handles create
  **Route points** whose dates are calculated automatically from path distance.
- Select a point and choose **Edit Date** to change when the entity reaches it.
  Opening the date controls does not move the timeline.
- Choose **Use Playhead** before or during date editing to copy the current
  timeline position into the selected point. Moving the timeline by itself
  never changes a keyframe date.
- Select a point and choose **Set Start Anchor**, then select a later point and
  choose **Equalize** to preview evenly timed travel over that section.
- Choose **Equalize Whole** to preview even timing across the complete route.

### Timed locations and route points

**Timed locations** carry authoritative dates. Departures, arrivals, stops,
and other historically meaningful positions should remain timed locations.
Editing either end of a Travel leg automatically recalculates every Route point
between them while preserving the path and the opposite endpoint.

**Route points** shape a Travel leg without creating dates that must be edited
individually. Moving a Route point recalculates its date and the other Route
points in that leg by cumulative distance. Choose **Make Timed Location** when
a calculated point becomes historically significant.

To simplify an existing densely timed route, set a timed start location,
select a later timed location, and choose **Make Intermediate Automatic**.
ProjektKraken keeps the endpoints and converts every point between them into
automatically timed Route points. Relocations cannot contain Route points.

### Travel, stays, and relocation

Each point after the first has an **Arrival from previous** setting:

- **Travel** moves the marker steadily from the previous location to this one.
  Different intervals and distances naturally produce different average
  speeds.
- **Stay** is shown automatically when consecutive locations have the same map
  coordinates. It records that the entity remained there for the interval.
- **Relocation** keeps the marker at the previous location until this point's
  exact date, then switches immediately. The broken connector marks a change
  of place without implying a travelled route. This is useful for teleporting,
  an off-page voyage whose path is deliberately unspecified, or records that
  only establish where someone was at two different times.

The selected segment shows its duration, map distance, and average speed.
Calibrated maps use the calibrated unit; otherwise distance and speed are
relative map values. A stay reports speed as `0`. A relocation reports `—`
because no travelled path or meaningful speed is known.

Speed equalization is available only when every selected segment is Travel and
changes location. A stay has no distance to distribute, and a relocation has
no route whose speed can be inferred, so ProjektKraken explains the conflict
instead of inventing timing.

### Change dates without changing the route

Route order is explicit. During **Edit Date**, the allowed dates
between the previous and next points are shown, and a value outside those
bounds is rejected. This lets you change segment speeds without accidentally
changing which locations come first.

The date editor shows the original date, proposed date, allowed range, and
current timeline playhead separately. **Use Playhead** is available only when
the displayed playhead date fits the allowed range. If it does not, the editor
explains which boundary the playhead must cross instead of silently rejecting
the button press.

Choose **Shift this and later** after changing a date to move that point and
every later point by the same amount. Later journey and stay durations remain
unchanged. A backward shift that would cross the preceding point is rejected.

Review the proposed dates before applying speed equalization. Choose **Apply**
to save the complete trajectory as one undoable change, or **Cancel** to discard
the working copy. Applying or cancelling an equalization preview returns you to
the trajectory session; it does not save or close the session by itself.

Before the first dated location, the ordinary marker position is shown. The
track activates on the first location's exact date and retains the final
location after the last date. A one-location track follows the same rule: the
ordinary position appears before its date, then its recorded location is held.
The ordinary marker can be moved before the first date. This changes its
pre-trajectory position without drawing a route to the first location. From
the first date onward, the playback marker cannot be dragged; open the editor
and move the dated locations instead.

If a date would overlap another point, ProjektKraken keeps the working copy
open and explains the conflict. Correct the date or cancel the date edit before
applying the trajectory.

Deleting a final trajectory location shows a warning. For a saved trajectory,
confirming the warning prepares its removal; choose **Apply** to save that
removal, or **Cancel** to keep the saved trajectory unchanged.

**Cancel Date** restores the date from before that date edit and leaves the
timeline where it is. Cancelling the complete trajectory likewise discards the
route changes without moving the timeline.

## Work with layers

The layer panel groups markers, features, and rasters. You can:

- create and rename groups;
- show or hide a layer or group;
- move content within the hierarchy;
- edit layer properties;
- delete a subtree with a preview of affected content.

Structural layer changes participate in undo and redo.

## Add raster layers

Create a raster from the layer panel and choose its purpose:

- **Discrete** for categories such as biomes or political control.
- **Continuous** for values such as elevation, rainfall, or temperature.
- **RGBA** for a painted visual overlay.

Select the Base state or a dated state before painting. Available tools depend
on the raster mode and can include brush, fill, gradient, sample, and
eyedropper. Wait for the visible save state before switching targets or closing
the world.

Raster strokes are undoable in the current session. Structural and destructive
raster operations use persistent command history.

## Dated raster states

A raster has an undated Base state and may have dated states. At the current
playhead time, ProjektKraken resolves the latest applicable state. Use
**Create Editable State** when you want to branch from the currently visible
state without changing the Base raster.

## Master and detail maps

Use the map overflow menu to designate a master map or register another map as
a detail map. Registered detail maps appear as footprints on their parent.
Footprints can be shown or hidden, opened, and edited. Breadcrumb navigation
returns through the map hierarchy.

## Calibration and queries

Calibrate a map by measuring a known distance. Calibration affects displayed
measurements and the scale bar; it does not resample the map image or raster.

ProjektKraken assumes every map is north-up. Spatial context evaluates point
markers at their position, paths along their full line, and regions across
their full boundary and area. For dated paths and regions, it uses the geometry
resolved at the requested date. Feature anchors remain responsible for labels
and selection but do not stand in for an extended feature during spatial
comparisons. If extended geometry is invalid, Kraken omits the affected spatial
claim instead of approximating it from the anchor.

Cross-layer spatial queries compare compatible raster layers at a selected
location. Review the layer purpose and value range before interpreting a
result.

## Tips and gotchas

- Map coordinates are normalized so content remains aligned when the view is
  resized.
- A detail map can have its own markers independently of the parent map.
- Trajectories are edited as a complete route, so one undo restores the whole
  route rather than only its last point.
- Deleting a map, group, or raster can affect nested content; read the
  confirmation summary carefully.
