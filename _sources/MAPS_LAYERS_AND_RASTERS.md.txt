# Maps, Layers, and Rasters

Projekt Kraken treats each map as a worldbuilding workspace. Its layer tree,
placed entities and events, paths, regions, trajectories, raster metadata, and
raster files form one logical map state. Actions such as deleting a group are
therefore undone as one action rather than as a series of unrelated edits.

## Layers

The **Layers** panel controls order, visibility, opacity, and grouping. Open
**Properties** on a layer to edit:

- its name, visibility, opacity, and notes;
- mutually exclusive children for groups;
- inclusive first and last lore dates;
- minimum and maximum zoom ratios.

Zoom limits edited in Properties are relative to **Fit to Map**. A ratio of
`1.0` is the fitted view, so the result is stable when the window changes size.
Older layers retain their previous zoom behaviour until their properties are
edited.

Deleting a group or raster shows the number of nested groups, features, raster
layers, and dated raster states that will be affected. The whole subtree is
deleted and restored together.

## Raster purposes

Choose the purpose before creating a raster:

- **Visual overlay** preserves imported RGB colours. Use it for illustrated
  terrain, scans, or reference imagery. It has no numeric mapping or painting.
- **Classified world data** stores integer categories such as biome, political
  control, geology, or land use. Values can have labels, colours, and links to
  entities or events.
- **Continuous measured field** stores a scalar surface such as elevation,
  rainfall, temperature, population density, or magical intensity. It supports
  a gradient and optional real-world value range and unit.

The creation dialog shows the chosen resolution and approximate uncompressed
working memory. Spatial queries exclude visual overlays. They identify layers
by UUID, resample categorical data with nearest-neighbour interpolation, and
resample continuous fields bilinearly onto the largest selected grid.

## Timeline states and editing

A raster has an undated base file and may have dated states. Dated states are
**effective from** their exact lore date:

1. Before the first dated state, the base is displayed.
2. At any later date, the latest state at or before the playhead is displayed.
3. Moving the playhead stops editing and makes the resolved display read-only.

Use **Create Editable State** to copy the currently resolved raster into a new
UUID-named state at the current lore date. Use **Edit This State** on an exact
dated-state row, or **Edit base** to make the undated file the explicit target.
Painting is saved in stroke order. A failed save reverts that stroke and every
dependent queued stroke and pauses editing for that raster.

Raster strokes are undoable during the current application session. Structural
actions and destructive raster operations are also retained in persistent
history, including their file artifacts.

## Calibration and measurement

New and legacy maps without a positive `width_meters` value are uncalibrated.
They show no metric scale bar, and paths and regions display **Calibrate map to
measure** instead of fabricated distances or areas.

Use the map scale action to enter a positive total map width or calibrate from a
known measured segment. Calibration affects measurement display; it does not
change raster resolution or pixel data.

## Compatibility

Existing world folders remain readable. Legacy `maps.attributes["layers"]` and
`raster_layers` records are accepted without an eager migration. Unchanged
legacy raster metadata round-trips in its original form. Newly created or
modified raster records use `schema_version: 2`, full-precision lore-date keys,
and UUID filenames for dated states.
