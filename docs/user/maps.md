# Maps, Layers, and Rasters

## What this does

Maps combine an image with placed events and entities, drawn paths and regions,
temporal trajectories, nested detail maps, and optional editable raster layers.

Start with an open world and an image for a new map, or an existing map for
editing. Use this guide to choose the operation that matches your intended
change. [Time and historical state](temporal-model.md#shape-location-and-presence)
explains why a border, a journey and existence dates are separate assertions.

## Create and open a map

1. Open the Explorer's **New** menu.
2. Select **Create Map**.
3. Choose an image and provide a name.
4. Select the map in Project or the Map panel.

Check that the image appears before placing features. Creating a map does not
place your existing Events or Entities on it. Cancel the creation dialog if
the wrong image was selected; avoid creating a second map to repair a missing
asset without first checking the world's asset files.

(help-map-features)=

## Add markers and features

Use markers to place entries on a map, paths to draw routes or lines, and regions to
draw areas.

1. Open a map.
2. Choose **Add Marker**, **Draw Path**, or **Draw Region**.
3. Place the marker preview or draw the vertices.
4. Choose **Confirm** or press **Enter** to finish. Choose **Cancel** or press **Escape** to discard the draft.

Check the saved feature on the map and in Layers. A preview alone is not a
saved marker, path or region. Use Undo for an accepted supported feature change.

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

(help-map-appearance)=

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

View a date before the change, then return to its date to verify both shapes.
Use Undo if the accepted state is wrong. Do not change visibility dates to
repair the vertices of a historical border.

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
3. Set **Exists from** and **Exists until**. Choose **Manual date**, a named
   **Event**, **Date not known**, or **Unbounded** independently for each side.
4. Confirm the changes.

View dates on either side of an exact boundary to check the result. If the
feature disappears, find it in Layers and use **Jump to valid time**; it has
not been deleted. Reopen **Visibility dates…** to correct a boundary.

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

### Follow a foundation or destruction event

Choose the Foundation Event for **Exists from** and the Destruction Event for
**Exists until**, then confirm with **OK**. The feature follows those Events when
their dates change. Reopening this editor retains the references; renaming an
Event updates its displayed name without changing the binding.

The default endpoint is **Occurrence / start**. Open **Endpoint and offset…** to
choose **Authored end**, a constrained date, or a signed offset. An Event's
authored end date takes precedence over its duration. Otherwise, a positive
duration determines the end relative to its uncertain start. An Event without
either has no known end: the reference stays unresolved until that information
is authored or you choose another boundary.

**Date before endpoint** and **Date after endpoint** record an independently
unknown boundary strictly before or after the shifted endpoint. They do not
mean “switch visibility at this Event.” **At event endpoint** shares the actual
transition. Use that choice when an old feature ends exactly when its successor
begins. Equal dates on different Events do not assert a shared transition.

Offsets can use fractional **Lore days**, whole **Calendar months**, or whole
**Calendar years**. Calendar offsets use the bound calendar's actual months,
leap rules and year variants; a month is not a fixed number of days. If the
target day or month does not exist, the binding remains unresolved. For coarse
dates, every possible occurrence must shift validly: a year-only date plus one
month can therefore remain unresolved until you refine its date.

**Use Playhead** instead copies a fixed exact lore date. It does not follow an
Event when that Event moves. A manually entered day or year retains its supplied
precision; it is not silently converted into an exact instant.

Group and feature dates apply together. A parent ending at the same uncertain
Event where its child begins has no joint presence. An empty interval is not an
occurrence; change its boundaries rather than expecting it to appear briefly.

Deleting a referenced Event is blocked while Map, Relation, Event, or chronology
references still use it. Replace or remove those references deliberately first.
Removing a referenced Event end is blocked in the same way.
Missing calendars and unsupported date metadata also remain saved, with an
explanation. Replace a boundary deliberately to change its meaning.
For an unsupported whole-window format, explicitly choose both boundary modes
to replace that format; changing only one side preserves it unresolved.

Event bindings resolve within ±10¹² lore days. At distant dates, a second or a
small fractional offset may be too fine for the stored coordinate to represent.
Kraken reports that limitation instead of inventing precision. **Jump to valid
time** is unavailable when no definitely valid date is known.

Changing existence dates does not redraw a border or path. Use historical geometry for
shape changes.

**Related:** {ref}`Historical geometry <help-map-historical-geometry>` · {ref}`Timeline
viewing <help-timeline-viewing>` · {ref}`Map features <help-map-features>`

(help-control-map-visibility)=

> Exists from and Exists until describe when a map feature is present, independently of its border or path geometry. An unknown boundary records unresolved timing; an unbounded side has no limit. Exists until is an exclusive boundary, so the feature is no longer present at that transition. Choose a date or boundary meaning appropriate to the world instead of changing geometry to hide a feature. A dated geometry state changes its shape, not its existence dates. Inspection does not move the playhead, toggle a layer or apply an unfinished map edit.

(help-inspect-map-anchor-options)=

**Endpoint and offset…** — Reveal the event endpoint, constrained-date meaning,
signed offset and unit. Collapsing these options retains their authored values.

(help-inspect-map-anchor-endpoint)=

**Event endpoint** — Follow the Event's occurrence/start or its authored end.
An authored end date takes precedence over a duration. Without either, an end
binding stays unresolved; it never falls back to the start.

(help-inspect-map-anchor-relative)=

**Boundary date** — At the endpoint shares its transition. Before/after means an
independently unknown date strictly before/after the endpoint plus offset.
These constrained dates do not share an identity merely because their Event matches.

(help-inspect-map-anchor-offset)=

**Signed offset** — Shift the selected Event endpoint before applying the chosen
boundary-date meaning. Zero retains the original transition. Lore days can be
fractional; calendar months and years must be whole numbers.

(help-inspect-map-anchor-unit)=

**Offset unit** — Choose lore days, calendar months or calendar years. Calendar
offsets follow the bound calendar. Invalid target dates remain unresolved,
including when only some possible occurrence dates would be invalid.

(help-inspect-map-visibility-scroll)=

**Visibility date fields** — Scroll to reach advanced boundary options. OK and
Cancel remain outside the scrolling fields; scrolling does not apply the draft.

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

Move the playhead across the saved route to verify the recorded locations.
Changing the view during this check does not edit a location's date.

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

(help-map-layers)=

## Work with layers

The layer panel groups markers, features, and rasters. You can:

- create and rename groups;
- show or hide a layer or group;
- move content within the hierarchy;
- edit layer properties;
- delete a subtree with a preview of affected content.

Structural layer changes participate in undo and redo.

(help-map-raster)=

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

(help-map-calibration)=

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

(help-map-icons)=

## Choose and manage map icons

Choose an icon for a selected point marker, or open the Icon Library to manage reusable
artwork. Imported icons are copied into the world’s assets. Changing an icon changes
appearance, not the linked entry, location or existence dates.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-init-self-state-list)=

**Geometry states** — Review Base Geometry and dated border or path states. Selecting a
row chooses the state for the adjacent actions.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-init-edit-button)=

**Edit geometry** — Prepare the selected geometry state for editing on the map. Confirm
or cancel its working copy separately.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-init-date-button)=

**Change geometry date** — Change when the selected dated geometry state takes effect.
Base Geometry remains the undated fallback.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-init-delete-button)=

**Delete geometry state** — Remove the selected dated geometry state after confirmation.
This differs from deleting the feature itself.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-init-close-button)=

**Close geometry history** — Close the geometry-state manager without starting another
geometry edit.

(help-inspect-src-gui-dialogs-feature-geometry-states-dialog-featuregeometrystatesdialog-change-date-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-self-name-edit)=

**Icon name** — Name this project icon for identification in the icon library.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-self-category-edit)=

**Icon category** — Assign a library category to help find this icon. This does not
change the linked world entry's type.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-self-diameter)=

**Native icon diameter** — Set the icon's reference diameter used by marker sizing.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-self-anchor-x)=

**Horizontal anchor** — Set the artwork's attachment point from left to right. The
anchor changes placement relative to the map coordinate.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-self-anchor-y)=

**Vertical anchor** — Set the artwork's attachment point from top to bottom. This is
independent of the feature's saved map coordinate.

(help-inspect-src-gui-dialogs-icon-metadata-dialog-iconmetadatadialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-setup-ui-self-search)=

**Search** — Find matching items in IconPicker. Searching changes the displayed matches
without editing their content.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-setup-ui-self-category)=

**Icon category** — Filter the icon library by category without changing icon metadata.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-setup-ui-self-import-btn)=

**Import Icons…** — Add one or several SVG, PNG, JPEG or WebP icons.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-setup-ui-self-status)=

**Icon import status** — Read import progress or errors. This status is read-only.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-setup-ui-close)=

**Close icon library** — Close the icon picker without choosing another icon.

(help-inspect-src-gui-dialogs-icon-picker-dialog-iconpickerdialog-make-icon-button-button)=

**Choose icon** — Choose this library icon for the requesting marker. In library-
management mode, inspect or manage it without assigning a marker.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-name)=

**Layer name** — Rename this layer or group without changing the entries linked to its
features.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-visible)=

**Layer visibility** — Show or hide this layer. Hiding does not delete its features or
change their existence dates.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-opacity)=

**Layer opacity** — Set how strongly this layer is drawn over the layers beneath it.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-notes)=

**Layer notes** — Add notes about this layer for later reference and supported context
use.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-exclusive)=

**Exclusive group** — Allow only one child layer in this group to be visible at a time.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-min-zoom)=

**Minimum zoom** — Set the minimum view zoom at which this layer is shown. This is a
display limit, separate from existence dates.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom-enabled)=

**Maximum zoom limit** — Enable an upper zoom limit for displaying this layer.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-self-max-zoom)=

**Maximum zoom** — Set the upper view zoom at which this layer is shown. This does not
resize its saved geometry.

(help-inspect-src-gui-dialogs-layer-properties-dialog-layerpropertiesdialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-map-edit-transition-dialog-mapedittransitiondialog-init-self-apply-button)=

**Apply map edits** — Save the current map working copy before continuing the requested
transition.

(help-inspect-src-gui-dialogs-map-edit-transition-dialog-mapedittransitiondialog-init-self-keep-button)=

**Keep editing** — Stay in the current map operation with its working copy intact.

(help-inspect-src-gui-dialogs-map-edit-transition-dialog-mapedittransitiondialog-init-self-discard-button)=

**Discard map edits** — Discard the map working copy and continue the requested
transition. Saved feature data is retained.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-search-edit)=

**Find entry for map** — Search existing entries to choose which one a map feature will
represent.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-new-location-button)=

**New Location** — Create a Location Entity for this map placement. This is separate
from adding a dated journey location.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-new-entity-button)=

**New Entity** — Open Entity creation for this map placement.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-new-event-button)=

**New Event** — Create an Event for this map placement.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-results-list)=

**Map entry results** — Choose an existing Event or Entity for the new map feature.

(help-inspect-src-gui-dialogs-map-object-picker-dialog-mapobjectpickerdialog-init-self-cancel-buttons)=

**Cancel buttons** — Cancel this MapObjectPicker operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-dialogs-raster-notes-dialog-rasternotesdialog-init-self-text-edit)=

**Text edit** — Add notes about this raster layer….

(help-inspect-src-gui-dialogs-raster-notes-dialog-rasternotesdialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-raster-orphan-warning-dialog-rasterorphanwarningdialog-init-ref-list)=

**Raster references** — Review raster layers that still refer to the entry being
deleted. Choose whether those references should also be removed.

(help-inspect-src-gui-dialogs-raster-orphan-warning-dialog-rasterorphanwarningdialog-init-self-btn-remove-and-delete)=

**Delete + Remove refs** — Delete the entity and remove its mapping from all raster
layers.

(help-inspect-src-gui-dialogs-raster-orphan-warning-dialog-rasterorphanwarningdialog-init-self-btn-delete-anyway)=

**Delete anyway** — Delete the entity but leave the raster mappings as orphaned entries.

(help-inspect-src-gui-dialogs-raster-orphan-warning-dialog-rasterorphanwarningdialog-init-self-btn-cancel)=

**Cancel deletion** — Keep the entry and its raster references by cancelling this
deletion.

(help-inspect-src-gui-dialogs-raster-query-dialog-rasterquerydialog-build-ui-btn-add)=

**Add query condition** — Append another raster-layer condition to the spatial query.

(help-inspect-src-gui-dialogs-raster-query-dialog-rasterquerydialog-build-ui-self-btn-remove)=

**Remove query condition** — Remove the last condition from the query draft. This does
not delete raster data.

(help-inspect-src-gui-dialogs-raster-query-dialog-rasterquerydialog-build-ui-btn-box)=

**Box** — Review the dialog’s choices, then use its acceptance or cancellation action.
Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-self-parent-combo)=

**Parent map** — Choose the parent map for this detail map. The relationship supports
navigation between the maps.

(help-inspect-src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-init-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-enabled)=

**Existence boundary** — Enable a date boundary for this feature. With no boundary on
this side, existence is unbounded on that side.

(help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-mode)=

**Boundary meaning** — Choose how the existence boundary relates to its date. This
affects presence at the boundary, independently of geometry states. A named Event
follows its occurrence/start or authored end when that Event changes. A manual
date stays fixed; Date not known and Unbounded remain distinct choices.

(help-inspect-src-gui-dialogs-temporal-validity-dialog-temporalvaliditydialog-optional-date-use-playhead)=

**Use playhead date** — Copy the current Timeline playhead date into this existence
boundary. World current time stays unchanged.

(help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-dist-input)=

**Measured distance** — Enter the real distance represented by the line measured on the
map.

(help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-unit-selector)=

**Distance unit** — Choose the unit for the measured real-world distance used to
calibrate the map.

(help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-cancel)=

**Cancel** — Cancel this CalibrationDistance operation without accepting its pending
changes. This is separate from applying or saving them.

(help-inspect-src-gui-widgets-map-calibration-distance-dialog-calibrationdistancedialog-init-self-btn-ok)=

**Apply calibration** — Use the measured line and real distance to set this map's scale.

(help-inspect-src-gui-widgets-map-feature-actions-featureactionpresenter-show-layers-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-feature-actions-featureactionpresenter-show-canvas-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-header-self-temporal-count-button)=

**0 in date · 0 outside** — Show only vector features outside the current playhead date.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-header-self-btn-new-group)=

**New group** — New Group — Create a new layer group.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-header-self-btn-new-raster)=

**New raster** — New Raster — Create a new raster / heatmap layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-header-self-btn-delete)=

**Delete** — Remove the selected layer or feature after reviewing the available
confirmation. Deleting map content is separate from merely hiding it.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-feature-actions-row-self-btn-feature-actions)=

**Feature actions** — Show the selected feature's supported actions, such as editing
geometry, appearance or existence dates.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-tool-mode-buttons-btn)=

**Raster tool** — Choose the indicated raster editing tool. Changing tools is separate
from painting a cell.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-advanced-paint-toggle)=

**Advanced** — Show raw raster values for specialist workflows.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-display-value-spin)=

**Paint value in display units** — Set the continuous raster value to paint using the
layer's configured display scale.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-rgba-color-button)=

**Paint colour** — Choose the RGBA colour to paint on this colour raster layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-rgba-alpha-spin)=

**Paint alpha** — Set the opacity component of the RGBA paint colour.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-gradient-from-spin)=

**Gradient start value** — Set the starting value for a raster gradient.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-gradient-to-spin)=

**Gradient end value** — Set the ending value for a raster gradient.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-rgba-gradient-from-button)=

**Gradient start colour** — Choose the starting RGBA colour for a raster gradient.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-rgba-gradient-to-button)=

**Gradient end colour** — Choose the ending RGBA colour for a raster gradient.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-paint-value-selector-self-paint-value-spin)=

**Paint value spin** — Raw raster value to paint (0–65535) — drag to scrub, double-
click to type.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-entity-picker-self-entity-picker-combo)=

**Entity picker combo** — Shows the mapped class for the current paint value. Select a
class here to jump to its value, or type a value above to auto-highlight the matching
class.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-falloff-curve-combo-self-falloff-curve-combo)=

**Falloff curve combo** — Cosine: smooth S-curve (default) | Linear: uniform ramp |
Gaussian: tight centre, rapid falloff.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-gradient-sub-combo-self-gradient-sub-combo)=

**Gradient sub combo** — Select gradient style (only applies when Gradient tool is
active).

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-edit-action-row-self-btn-edit-toggle)=

**Paint** — Enter/exit raster edit mode — changes are applied to the active layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-edit-action-row-self-btn-palette)=

**Palette** — Palette — Open the colour map / class palette editor.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-edit-action-row-self-btn-stats)=

**Analyze** — Stats — Show coverage statistics for this raster layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-snapshot-row-self-btn-snapshot)=

**Create state** — Create Editable State — branch the displayed raster at the current
timeline date.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-snapshot-row-self-btn-edit-base)=

**Edit base** — Explicitly display and edit the undated base raster.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-snapshot-row-self-btn-edit-state)=

**Edit this state** — Select the dated raster state shown in the layer tree as the edit
target.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-layer-settings-self-blend-combo)=

**Blend combo** — How this layer blends with layers below it.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-layer-settings-self-btn-notes)=

**Notes** — Notes — Add or edit text notes for this raster layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-layer-settings-self-preset-combo)=

**Preset combo** — Apply a saved brush preset to the current layer.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-layer-settings-self-btn-query)=

**Query** — Query — Build a cross-layer spatial query.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-layer-settings-self-btn-clear-query)=

**Clear query** — Clear Query — Remove the spatial query overlay.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-make-button-btn)=

**Raster action** — Use this raster editing action in the current layer. The linked task
explains the raster working modes.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-make-labeled-spinbox-spin)=

**Raster tool amount** — Set the indicated raster tool amount within its displayed range
and units.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-make-slider-scrubber-row-spin)=

**Raster tool amount** — Set the indicated raster tool amount with the numeric control
or adjacent slider.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-jump)=

**Jump to raster state** — Move Viewing time to the selected raster state's date. World
current time remains unchanged.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-edit)=

**Edit raster state** — Choose the selected dated raster snapshot as the editing target.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-del)=

**Delete raster snapshot** — Remove this dated raster snapshot after confirmation. This
is separate from deleting the layer or its undated base.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-unlock)=

**Unlock layer** — Allow supported edits to this layer again. Unlocking does not change
its saved data by itself.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-toggle)=

**Layer visibility** — Show or hide this layer without deleting it or changing its
existence dates.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-rename)=

**Rename layer** — Change the layer's display name without renaming linked world
entries.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-properties)=

**Layer properties** — Edit layer visibility, opacity, notes and zoom limits.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-temporal-action)=

**Existence dates** — Edit when this feature exists, independently of its historical
geometry states.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-delete)=

**Delete layer** — Remove this layer or feature after confirmation. Hiding it instead
retains the saved map content.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-group)=

**New layer group** — Create a group for organizing related layers. Grouping does not
create a world relation.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-show-context-menu-action-raster)=

**New raster layer** — Create a raster layer with a chosen data mode, resolution and
initial data.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-populate-feature-layer-actions-properties)=

**Layer properties** — Edit the selected layer's visibility, opacity, notes and zoom
limits.

(help-inspect-src-gui-widgets-map-map-layer-panel-maplayerpanel-populate-feature-layer-actions-rename)=

**Rename layer** — Change this layer's display name without renaming linked world
entries.

(help-inspect-src-gui-widgets-map-map-scale-dialog-mapscaledialog-init-self-width-input)=

**Map width** — Set the physical width represented by the complete map image.

(help-inspect-src-gui-widgets-map-map-scale-dialog-mapscaledialog-init-self-unit-selector)=

**Map scale unit** — Choose the physical distance unit used for this map's scale.

(help-inspect-src-gui-widgets-map-map-scale-dialog-mapscaledialog-init-calibrate)=

**Calibrate from Measurement...** — Measure a known distance on the map to calculate its
total width.

(help-inspect-src-gui-widgets-map-map-scale-dialog-mapscaledialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-marker-size-dialog-markersizedialog-init-self-mode-selector)=

**Marker size behavior** — Choose map-scaled sizing or a fixed screen size. This affects
how the marker appears while zooming.

(help-inspect-src-gui-widgets-map-marker-size-dialog-markersizedialog-init-self-size-input)=

**Marker size** — Set the marker's size in the units appropriate to the selected sizing
behavior.

(help-inspect-src-gui-widgets-map-marker-size-dialog-markersizedialog-init-self-unit-selector)=

**Marker size unit** — Choose the measurement unit for the marker's size.

(help-inspect-src-gui-widgets-map-marker-size-dialog-markersizedialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-name-edit)=

**Raster layer name** — Name this raster layer for identification in Layers.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-mode-combo)=

**Raster data mode** — Choose discrete classes, continuous values or RGBA colours. The
mode determines painting and palette controls.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-res-combo)=

**Raster resolution** — Choose the new raster's pixel dimensions. Resolution determines
the amount of editable raster detail.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-default-spin)=

**Default value:** — Initial value for all pixels (0–65535).

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-browse-btn)=

**Browse…** — Import an existing image as the raster layer data.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-self-clear-btn)=

**Clear image source** — Remove the selected raster import image from this draft. The
source image file is retained.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-init-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-build-value-range-group-self-display-min-edit)=

**Display minimum** — Set the real-world display value corresponding to the low end of
the raw raster range.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-build-value-range-group-self-display-max-edit)=

**Display maximum** — Set the real-world display value corresponding to the high end of
the raw raster range.

(help-inspect-src-gui-widgets-map-raster-layer-dialog-rasterlayerdialog-build-value-range-group-self-display-unit-edit)=

**Display unit** — Name the unit shown for mapped raster values, such as degrees or
metres.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-ui-btn-box)=

**Box** — Review the dialog’s choices, then use its acceptance or cancellation action.
Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-discrete-ui-btn-auto-color)=

**🎨 Auto-color** — Assign a qualitative colour palette to each row in sequence.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-discrete-ui-btn-export)=

**Export palette** — Save this raster colour map or class palette for reuse. This does
not export the raster's painted cells.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-discrete-ui-btn-import)=

**Import palette** — Load a colour map or class palette for this raster. Review its
entries before accepting it.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-discrete-ui-self-table)=

**Raster classes** — Edit each class's raw value, colour, label and optional world-entry
mapping.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-discrete-ui-btn-add)=

**Add palette entry** — Add a discrete raster class with its value, colour and optional
linked entry.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-preset-combo)=

**Gradient preset** — Choose a preset colour gradient for continuous raster display.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-add-stop-btn)=

**+ Add stop** — Add a new colour stop to the gradient.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-stretch-min-spin)=

**Stretch min spin** — Minimum value mapped to the start colour — drag to scrub.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-stretch-max-spin)=

**Stretch max spin** — Maximum value mapped to the end colour — drag to scrub.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-btn-auto-stretch)=

**Auto-stretch** — Set stretch range from actual data range.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-btn-reset-stretch)=

**Reset** — Reset stretch to full 0–65535 range.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-mapping-enabled)=

**Map raw values to real-world units** — Display values in the legend and probe popup
using a real-world scale (e.g. 0–65535 → -10–40 °C).

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-min-edit)=

**Display minimum** — Set the real-world value corresponding to the raw raster range's
low end.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-max-edit)=

**Display maximum** — Set the real-world value corresponding to the raw raster range's
high end.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-unit-edit)=

**Display unit** — Name the unit used in this raster's legend and probe values.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-format-edit)=

**{:.2f}** — Python format string applied to each display value, e.g. {:.1f} or {:.0f}.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-display-scale-combo)=

**Display scale** — Choose how raw raster values map to the configured display range.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-linked-item-controls-self-linked-type-combo)=

**Linked entry type** — Choose whether the palette's linked world entry is an Entity or
Event.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-linked-item-controls-self-linked-name-edit)=

**Linked name edit** — Link this colour map to a world entity or event by name.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-stop-row-pos-spin)=

**Pos spin** — Stop position along the gradient (0 = start, 100 = end) — drag to scrub.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-stop-row-color-btn)=

**Gradient stop colour** — Choose the colour at this gradient stop. Intervening colours
are calculated between stops.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-stop-row-del-btn)=

**Remove gradient stop** — Remove this colour stop from the gradient draft.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-spin)=

**Spin** — Raster pixel value for this class — drag to scrub, double-click to type.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-btn)=

**Class colour** — Choose the display colour for this discrete raster class.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-label-edit)=

**Class label** — Name this raster class for the palette and legend.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-type-combo)=

**Class entry type** — Choose whether this class maps to an Entity or Event.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-entity-name-edit)=

**Class world entry** — Choose the world entry represented by this raster class. The
class value remains a raster value, separate from its name.

(help-inspect-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-add-entry-row-remove-btn)=

**Remove palette entry** — Remove this class mapping from the palette draft. This does
not erase painted raster cells.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-content-self-btn-confirm-map-edit)=

**Confirm** — Confirm the active marker, drawing or geometry working copy. The banner
identifies the operation being saved.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-content-self-btn-cancel-map-edit)=

**Cancel** — Discard the active map-tool working copy and keep the saved feature. This
does not delete the underlying Event or Entity.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-status-row-self-temporal-outside-button)=

**0 features outside this date** — Filter the Layers panel to features outside the
current date.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-inspector-control-self-open-inspector-action)=

**Open in inspector** — Deliberately open the selected map feature’s linked Event or
Entity. Ordinary map selection can remain local instead.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-feature-actions-control-self-feature-actions-menu)=

**Feature actions** — Review operations available for the selected map feature.
Inspection explains each action without activating it.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-feature-actions-control-self-feature-actions-action)=

**Feature actions** — Open the selected feature's editing, appearance, history and
visibility actions.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-breadcrumb-self-btn-parent)=

**Parent map** — Navigate from this detail map to its parent map, using the existing
unfinished-map-edit safeguards.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-edit-strip-self-btn-delete-trajectory-keyframe)=

**Delete journey point** — Remove the selected point from the journey working copy.
Apply the journey separately to save the change.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-edit-strip-self-btn-add-trajectory-location)=

**Add Location** — Add a dated location at the current playhead.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-edit-strip-self-btn-accept-second-trajectory-location)=

**Accept Second Location** — Add the destination marker at the current later playhead
date.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-commit-buttons-self-btn-reload-trajectory)=

**Discard and reload journey** — Reload the saved journey into the working copy,
discarding local changes while keeping the journey editor open.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-commit-buttons-self-btn-apply-trajectory)=

**Apply** — Save the complete journey working copy as one undoable change. Accepting an
individual location or timing preview does not save the whole journey.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-commit-buttons-self-btn-cancel-trajectory)=

**Cancel** — Discard the journey working copy and keep the saved track. Cancelling does
not move the Timeline back.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-feature-geometry-edit-strip-self-btn-geometry-discard-reload)=

**Discard and reload geometry** — Reload saved geometry into the current working copy,
discarding local changes without deleting the feature.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-segment-panel-self-trajectory-arrival-mode)=

**Trajectory arrival mode** — Choose how this location is reached from the previous one:
Travel follows the route; Relocation switches at the arrival date without implying a
travelled path.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-controls-self-btn-trajectory-date-previous)=

**One day earlier** — Move the selected journey point's draft date one lore day earlier.
The whole journey still requires Apply to save.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-controls-self-btn-trajectory-date-next)=

**One day later** — Move the selected journey point's draft date one lore day later. The
whole journey still requires Apply to save.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-controls-self-btn-shift-trajectory-later)=

**Shift Later** — Apply this date change to all later locations.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-controls-self-btn-edit-trajectory-date)=

**Edit journey date** — Open date editing for this journey point. Changes remain within
the journey working copy until Apply.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-mode-controls-self-btn-trajectory-date-use-playhead)=

**Use Playhead** — Set this keyframe's date to the current timeline playhead.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-mode-controls-self-btn-finish-trajectory-date)=

**Finish point date** — Accept the edited point date into the journey working copy. This
does not save the complete journey yet.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-mode-controls-self-btn-cancel-trajectory-date)=

**Cancel Date** — Restore the point’s date from before this date edit. The journey
session stays open and the Timeline stays where it is.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-mode-controls-self-btn-make-trajectory-route-point)=

**Make Route Point** — Calculate this point's date automatically from its travel leg.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-trajectory-date-mode-controls-self-btn-make-trajectory-timed-location)=

**Make Timed Location** — Keep this point's calculated date as an independently editable
date.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-anchor-controls-self-btn-set-trajectory-speed-anchor)=

**Set Start Anchor** — Keep this keyframe fixed as the start of a speed-equalization
range.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-anchor-controls-self-btn-equalize-trajectory-speed)=

**Equalize Speed to Here** — Preview constant speed between the fixed start and this
keyframe.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-anchor-controls-self-btn-make-intermediate-automatic)=

**Make Intermediate Automatic** — Keep the timed endpoints and calculate every point
between them.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-anchor-controls-self-btn-equalize-whole-trajectory)=

**Equalize Whole** — Preview constant speed between the trajectory endpoints.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-preview-controls-self-btn-clear-trajectory-speed-anchor)=

**Clear Anchor** — Remove the selected speed start anchor without changing dates.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-preview-controls-self-btn-apply-speed-equalization)=

**Apply Equalization** — Accept this timing preview into the journey working copy. Use
the journey’s Apply action separately to save the complete track.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-speed-preview-controls-self-btn-cancel-speed-equalization)=

**Cancel Equalization** — Restore the working dates from before this preview.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-management-controls-self-map-selector)=

**Map selector** — Switch between maps in this world.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-management-controls-self-btn-new-map)=

**New Map** — Create a new map in this world.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-map-management-controls-self-btn-map-overflow)=

**Map actions** — Open map-level actions such as master/detail-map setup and map
deletion.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-viewport-controls-self-btn-fit-view)=

**Fit to View** — Zoom and pan to fit all content in view.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-viewport-controls-self-btn-settings)=

**Settings** — Configure map scale and distance calibration.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-drawing-controls-self-btn-add-marker)=

**Add Marker** — Add a marker to the map (click the map to choose its position).

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-drawing-controls-self-btn-draw-path)=

**Draw Path** — Draw a polyline path (click vertices, then Confirm or press Enter).

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-drawing-controls-self-btn-draw-region)=

**Draw Region** — Draw a polygon region (click vertices, then Confirm or press Enter).

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-view-toggle-controls-self-btn-snap)=

**Snap** — Enable snapping while placing or editing map geometry. This helps align
points; it does not change saved geometry by itself.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-view-toggle-controls-self-btn-legend-toggle)=

**Legend** — Show / hide the raster layer legend overlay.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-view-toggle-controls-self-btn-temporal-ghosts)=

**Temporal Ghosts** — Show outside-time features as faint authoring ghosts. This
session-only view does not change their existence dates or bypass manual hiding.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-mode-controls-self-btn-edit-trajectory)=

**Edit Trajectory** — Edit this entity's trajectory directly on the map.

(help-inspect-src-gui-widgets-map-widget-mapwidget-build-mode-controls-self-mode-indicator)=

**● Normal** — Current editing mode — click to exit.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-master-action)=

**Set as master map** — Designate this map as the world's master map for detail-map
relationships.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-register-action)=

**Register as Detail Map…** — Designate a master map first before registering a detail
map.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-show-footprints-action)=

**Show detail footprints** — Show or hide detail-map footprints on the parent map. This
does not delete the detail maps.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-edit-footprint-action)=

**Edit detail footprint** — Edit the detail map's footprint on its parent map using a
map working copy.

(help-inspect-src-gui-widgets-map-widget-mapwidget-show-map-overflow-menu-delete-action)=

**Delete map** — Delete this map after confirmation. Review the scope carefully; hiding
a layer is a separate operation.

(help-inspect-src-gui-dialogs-icon-picker-dialog-projecticoncard-show-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-dialogs-icon-picker-dialog-projecticoncard-show-context-menu-edit)=

**Edit Icon…** — Edit the name, category, size and anchor.

(help-inspect-src-gui-dialogs-icon-picker-dialog-projecticoncard-show-context-menu-delete)=

**Delete Icon…** — Remove an unused icon; restore it with Undo.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-feature-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-trajectory-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-trajectory-context-menu-edit-action)=

**Edit trajectory** — Open the selected Entity marker's journey working copy. Apply
saves the complete track; Cancel discards the working copy.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-map-background-context-menu-menu)=

**Menu** — Open the Menu menu to choose a related operation. Opening the menu does not
apply any of its actions.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-map-background-context-menu-add-action)=

**Add marker here** — Start placing a marker at this map location, then choose the Event
or Entity it represents.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-map-background-context-menu-draw-path-action)=

**Draw path here** — Start drawing a path from this map location. Confirm saves the
drawing; Cancel discards it.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-map-background-context-menu-draw-region-action)=

**Draw region here** — Start drawing a region from this map location. Confirm saves the
drawing; Cancel discards it.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-border-strength-dialog-spin)=

**Border Width (px):** — Set border width (px) for this view, using the units and
allowed range shown beside the field.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-border-strength-dialog-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-feature-style-dialog-stroke-btn)=

**Stroke Color:** — Choose a display colour for this style. Styling does not create or
remove a world relation.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-feature-style-dialog-line-style-combo)=

**Line style** — Choose a solid or dashed outline for this path or region. This changes
global appearance rather than historical vertices.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-feature-style-dialog-fill-btn)=

**Fill Color:** — Choose a display colour for this style. Styling does not create or
remove a world relation.

(help-inspect-src-gui-widgets-map-interaction-handler-interactionhandler-show-feature-style-dialog-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-map-raster-stats-panel-rasterstatspanel-init-close-btn)=

**Close raster statistics** — Close the raster coverage statistics view.

(help-inspect-src-gui-widgets-map-raster-stats-panel-rasterstatspanel-build-discrete-view-table)=

**Raster coverage** — Read per-class coverage statistics for this raster layer. This is
a read-only analysis of existing raster data.

(help-inspect-feature-lock)=

Lock the feature against ordinary map interaction without changing its geometry or
existence dates.

(help-inspect-feature-unlock)=

Unlock the feature so its supported editing actions can be used again.

(help-inspect-feature-jump)=

Move Viewing time to a date when this feature is present. World current time stays
unchanged. This action is unavailable when no definitely valid date is known,
including empty inherited windows. Inspect Visibility dates to resolve the cause.

(help-inspect-feature-validity)=

Edit Exists from and Exists until independently of the feature’s geometry.

(help-inspect-feature-layers)=

Reveal the selected feature in Layers without changing its saved content.

(help-inspect-feature-geometry)=

Prepare a working copy of the border or path at the viewed date. Confirm saves it;
Cancel discards it.

(help-inspect-feature-style)=

Edit the path or region’s global appearance. This does not change historical vertices or
existence dates.

(help-inspect-feature-history)=

Manage Base Geometry and dated geometry states, including their dates and deletion.

(help-inspect-feature-appearance)=

Edit the marker’s size and artwork anchor in a working copy. Confirm saves the
appearance; Cancel restores it.

(help-inspect-feature-icon)=

Choose a library or imported icon for the marker without moving it or changing its
linked entry.

(help-inspect-feature-journey)=

Create or edit the Entity marker’s dated journey. Apply saves the complete track;
individual point edits remain a working copy until then.

(help-inspect-feature-copy)=

Copy the selected marker’s appearance without copying its location, layer, linked entry
or timeline validity.

(help-inspect-feature-paste)=

Paste the copied appearance onto this marker. Its location, layer, linked entry and
timeline validity remain unchanged.

(help-inspect-feature-anchor)=

Reset the artwork attachment to the icon’s centre without changing the feature’s saved
map coordinate.

(help-inspect-feature-size)=

Choose map-scaled or fixed-on-screen marker sizing and its size units.

(help-inspect-feature-reset-size)=

Restore this library icon’s default marker size without changing its linked entry or
location.

(help-inspect-feature-border)=

Set the vector marker’s border strength. This changes appearance rather than historical
border vertices.

(help-inspect-feature-fill)=

Choose the vector marker fill colour without changing its location or identity.

(help-inspect-feature-border-color)=

Choose the vector marker outline colour without changing its geometry.

(help-inspect-feature-no-fill)=

Make the vector marker fill transparent while retaining its outline and location.

(help-inspect-feature-no-border)=

Remove the vector marker outline while retaining its fill and location.

(help-inspect-empty-mapwidget-build-map-content-351)=

Create a map from an image, then name it. Creating a map does not automatically place
Events or Entities on it.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-tree-view-self-tree)=

**Layers tree** — Select and organize map layers, groups, features and dated raster
states. Visibility and locking are separate from deletion.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-opacity-bar-self-opacity-slider)=

**Layer opacity** — Adjust how strongly the selected layer is drawn over layers beneath
it.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-mode-specific-paint-controls-self-fill-tolerance-slider)=

**Fill tolerance** — Set how similar raster values must be for the fill tool to include
them.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-paint-value-selector-self-swatch-grid)=

**Class paint value** — Choose the discrete raster class to paint. Selecting a swatch
does not paint a cell.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-build-paint-value-selector-self-gradient-scrubber)=

**Continuous paint value** — Choose a continuous raster paint value from the displayed
gradient. Choosing a value is separate from painting the map.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-make-slider-scrubber-row-slider)=

**Raster tool amount** — Adjust the indicated raster tool amount using the slider or
adjacent numeric control.

(help-inspect-view-src-gui-widgets-map-map-layer-panel-maplayerpanel-make-labeled-slider-slider)=

**Raster tool percentage** — Adjust the indicated raster tool percentage within its
displayed range.

(help-inspect-view-src-gui-widgets-map-raster-palette-editor-rasterpaletteeditor-build-gradient-ui-self-stretch-scrubber)=

**Gradient stretch** — Adjust the range mapped to the continuous raster palette's
gradient colours. This changes display mapping rather than painted values.

(help-inspect-view-src-gui-widgets-map-widget-mapwidget-init-self-view)=

**View** — Inspect and navigate the map canvas. Active tools can place or edit features;
inspection explains the canvas without selecting, moving or confirming a feature.


(help-inspect-map-stroke-width)=

**Stroke width** — Set the global outline width of this path or region in pixels. This changes appearance rather than historical vertices.

(help-inspect-map-stroke-decrease)=

**Decrease stroke width** — Reduce this path or region outline by one width step. This does not change its geometry.

(help-inspect-map-stroke-increase)=

**Increase stroke width** — Increase this path or region outline by one width step. This does not change its geometry.

(help-inspect-appearance-hex-colour)=

**Hex colour** — Enter the colour as a hexadecimal RGB value. The preview shows the proposed colour before confirmation.

(help-inspect-appearance-accept-colour)=

**Use colour** — Confirm this colour choice and close the picker. The requesting style control determines which appearance is changed.

(help-inspect-raster-fill)=

**Raster fill** — Fill a contiguous raster region with the selected value or colour. Tolerance controls which neighbouring values are included.

(help-inspect-raster-gradient)=

**Raster gradient** — Paint a transition between the configured start and end values or colours using the selected gradient shape.

(help-inspect-raster-sample)=

**Raster sample** — Read a raster cell to choose its value for painting. Sampling does not repaint the cell and is unavailable for RGBA layers.

(help-inspect-raster-hardness)=

**Brush hardness** — Set brush edge hardness: zero gives a soft edge and 100 gives a hard edge.

(help-inspect-raster-brush-opacity)=

**Brush opacity** — Set brush strength: 100 fully replaces the affected value, while zero makes no change.

(help-inspect-raster-brush)=

**Raster brush** — Paint raster cells with the selected value or colour. Brush size, hardness and opacity control its effect.
