# Maps, Layers, and Rasters

## What this does

Maps combine an image with placed events and entities, drawn paths and regions,
temporal trajectories, nested detail maps, and optional editable raster layers.

## Create and open a map

1. Open the Explorer's **New** menu.
2. Select **Create Map**.
3. Choose an image and provide a name.
4. Select the map in the Explorer or Map dock.

## Add markers and features

- Select **Add Marker**, then click once on the map.
- Use **Draw Path** or **Draw Region** to create a feature.
- Double-click or use **Finish Sketch** to complete a drawing.
- Press **Escape** to cancel the current tool.
- Right-click a feature and choose **Edit Geometry at Playhead…** to move,
  insert, or remove vertices in a working copy.

Right-click a point marker and choose **Change Icon…** to use a bundled icon,
reuse an icon stored in the world, or import an SVG, PNG, JPG/JPEG, or WebP
file. Imported icons are copied into the portable world's `assets/images/`
folder. SVG markers support fill and border styling. Raster icons retain their
original colours and transparency; their vector-only styling actions are
disabled, but marker scale remains available.

Point-marker icons scale with the map by default. This gives character tokens
and location symbols a stable footprint: zooming in makes both the map and its
icons larger. Right-click a marker and choose **Visual Styling > Size &
Zoom…** to set that marker's behavior and base diameter. Uncalibrated maps use
a percentage of total map width; calibrated maps also offer metres and
kilometres. The scale multiplier is useful for creature size or emphasis.

Choose **Fixed on screen** for an individual overview symbol that should remain
readable at every zoom level. Different markers on the same map may use
different modes and sizes. Labels stay screen-sized and collision-managed, but
remain visually attached to their marker instead of drifting away from it.

Use **Visual Styling > Copy Appearance** and **Paste Appearance** to transfer a
marker's icon, colours, border, sizing, and icon anchor without copying its
position, layer, timeline validity, or linked object. Choose **Edit
Appearance…** for direct manipulation: drag the corner handle to resize the
marker and move the anchor handle to select the point in the artwork that
should remain attached to the map coordinate. The edit banner shows the live
scale factor and anchor percentages. Press **Enter** to save the edit as one
undoable change or **Escape** to restore the previous appearance. Use
**Reset Anchor to Centre** to return to the legacy centred attachment.

Snapping helps align new or edited vertices with existing geometry. Paths need
at least two vertices; regions need at least three.

## Dated path and region geometry

Every path and region has Base Geometry and may have dated geometry states.
Before the first dated state, ProjektKraken draws Base Geometry. On a state's
exact date and until the next state, it draws the latest applicable state.
Geometry switches immediately; shapes are not interpolated or morphed.

Choose **Edit Geometry at Playhead…** from a feature's context menu. On the
exact date of an existing state, this edits that state. At any other date,
ProjektKraken clones the currently resolved geometry into a new state at the
playhead, so editing a later border never silently changes earlier history.
Choose **Apply** to save the working copy as one undoable operation, or
**Cancel** to restore the geometry appropriate for the playhead.

Choose **Manage Geometry States…** to edit Base Geometry explicitly, edit a
dated state, change its calendar-aware date, or delete it. Base Geometry cannot
be deleted, and two states cannot share a date. Deleting a dated state reveals
the preceding state or Base Geometry at affected dates.

Feature style, label, and layer assignment remain global. Event-date
future/past presentation is separate from geometry-state resolution. Point
markers continue to use their ordinary positions or trajectories.

## Temporal visibility

Point markers, paths, and regions can exist only during part of the timeline.
Right-click a feature or its layer and choose **Temporal Validity…**, then set
optional **Exists from** and **Exists until** dates. Temporal validity has its
own focused editor; ordinary layer properties remain separate. Group dates
apply to the vector features beneath them.

Validity uses an inclusive start and exclusive end. A feature is present when
the playhead is on or after **Exists from**, but it is absent on the exact
**Exists until** date. This lets one feature end exactly when its replacement
begins without an overlap or gap. **Use Playhead** copies the active lore date
into either endpoint.

The layer tree keeps absent features available for authoring. A clock badge and
dimmed name mean the feature is outside the current date; an eye-slash means it
is manually hidden. The panel and map status show how many vector features are
outside the date. Select that count to filter the tree, then use **Jump to
Start** or **Jump to Last Valid Day** to inspect a hidden feature.

**Temporal Ghosts** is an optional, session-only authoring view. It shows
outside-time features as faint dashed shapes while still respecting manual,
group, and zoom hiding. Ghosts can be selected, but cannot be dragged or edited
directly; use their menu to jump to a valid date, change validity, or reveal the
feature in Layers.

Trajectory dates continue to answer where an entity would be. Temporal
validity separately decides whether it exists on the map. A normal selected
route disappears with an invalid owner, while an already-open trajectory or
geometry editing session remains visible as an authoring aid. Playhead-aware
spatial generation also excludes features that do not exist at the requested
date.

## Create or edit a trajectory

Select an entity marker and choose **Create Trajectory**. ProjektKraken starts
an unsaved track with one dated location: the marker's current map position at
the current playhead date. Choose **Cancel** to leave the entity unchanged, or
**Apply** to create the track as one undoable change. Event markers cannot have
trajectories.

For an entity that already has a track, choose **Edit Trajectory**. The map
shows a working copy while the saved track remains unchanged.

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
