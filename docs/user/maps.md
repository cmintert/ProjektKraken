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
- Right-click a feature and choose **Edit Vertices…** to move, insert, or
  remove vertices.

Snapping helps align new or edited vertices with existing geometry. Paths need
at least two vertices; regions need at least three.

## Edit a trajectory

Select an entity that already has a trajectory, then choose **Edit Trajectory**.
The map shows a working copy of the route while the saved trajectory remains
unchanged.

- Drag a dated point to change its position.
- Drag a midpoint handle to insert a new dated point between two existing
  points.
- Select a point and choose **Edit Date** to change when the entity reaches it.
  Opening the date controls does not move the timeline.
- Choose **Use Playhead** before or during date editing to copy the current
  timeline position into the selected point. Moving the timeline by itself
  never changes a keyframe date.
- Select a point and choose **Set Start Anchor**, then select a later point and
  choose **Equalize** to preview evenly timed travel over that section.
- Choose **Equalize Whole** to preview even timing across the complete route.

Review the proposed dates before applying speed equalization. Choose **Apply**
to save the complete trajectory as one undoable change, or **Cancel** to discard
the working copy. Applying or cancelling an equalization preview returns you to
the trajectory session; it does not save or close the session by itself.

The ordinary entity marker shows its position at the current playhead time. It
cannot be dragged to reshape a trajectory; open **Edit Trajectory** and move the
dated points instead.

If a date would overlap another point, ProjektKraken keeps the working copy
open and explains the conflict. Correct the date or cancel the date edit before
applying the trajectory. Moving a date past another point is allowed; the route
reorders the points by date while keeping each point's map position attached.

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
