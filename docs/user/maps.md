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
- Deleting a map, group, or raster can affect nested content; read the
  confirmation summary carefully.

