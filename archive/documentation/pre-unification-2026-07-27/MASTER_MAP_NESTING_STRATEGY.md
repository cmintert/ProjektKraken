# Master Map Nesting Strategy

**Date:** 2026-04-25
**Updated:** 2026-04-25 (codebase feasibility review + correctness pass)
**Status:** Living design note — integration points verified against current source
**Scope:** Strict 2D map nesting inside one world, anchored to a single master map

> **Field rename:** the parent reference is named `parent_map_id`, not
> `parent_map_id`. It points to the **direct parent** map (which may itself
> be a detail map). The root master is reached by walking the chain. The
> rename avoids the trap of readers assuming the field always names the
> root.

## Goal

Support a single **master map** for a world and allow additional maps to be
registered as **detail maps** inside that master coordinate space.

This design explicitly avoids real-world GIS concerns:

- No lat/long
- No EPSG or CRS handling
- No external georeferencing requirement
- No reprojection or raster warping

The problem is purely: "where does this detail map sit on the master map, and
how do we move between them consistently?"

## Decision

ProjektKraken should use a **master-map-relative 2D coordinate model**.

Each world has one canonical 2D coordinate space. The master map defines that
space. Every detail map is registered into it using a lightweight transform.

This is not georeferencing in the GIS sense. It is an internal 2D placement
system for nested maps.

## Why This Fits The Existing Codebase

Current map handling is already image-local and 2D:

- markers use normalized image coordinates
- scale is tracked as a single width-in-meters value
- map metadata already lives in `Map.attributes`
- raster layers are already treated as aligned to the owning map

Relevant implementation anchors:

- `src/core/map.py`
- `src/services/repositories/map_repository.py`
- `src/commands/map_crud_commands.py`
- `src/gui/mixins/map_calibration_mixin.py`
- `src/gui/widgets/map_widget.py`
- `src/services/spatial_context_builder.py`

The codebase does **not** currently maintain a full map-to-map transform model.
That missing abstraction is the real groundwork.

## Codebase Feasibility Review

### Summary

The design is **fully feasible** without any schema migrations in Phase 1.
All relevant extension points already exist in the codebase and follow
established patterns.  The `Map.attributes` dict and the `UpdateMapCommand`
attribute-merge path are the primary anchors; no new tables or dataclass
fields are required until query pressure justifies them.

### Key Files and Their Roles

| File | Role for this feature |
|---|---|
| `src/core/map.py` | `Map.attributes` is the zero-migration storage for all nesting metadata; `to_dict`/`from_dict` already round-trips arbitrary attribute content. |
| `src/services/repositories/map_repository.py` | `get_all_maps()` and `get_map(id)` are the query surface. Phase 1 can scan `Map.attributes` in Python after `get_all_maps()`; a SQL JSON extract is an optional optimisation later. |
| `src/commands/map_crud_commands.py` | `UpdateMapCommand.execute()` already deep-merges `attributes` safely. A `SetMasterMapCommand` and `RegisterDetailMapCommand` can either reuse this command with targeted payloads or be thin wrappers that call `UpdateMapCommand`. `DeleteMapCommand` must be updated to clear `parent_map_id` references from orphaned detail maps. |
| `src/commands/registry.py` | Any new dedicated nesting commands must be registered here for command history to survive restarts. |
| `src/app/map_handler.py` | `on_map_selected()` reads `attributes["width_meters"]` to restore scale — the same pattern applies to reading `registration` metadata. `on_map_scale_changed()` uses `UpdateMapCommand` to persist attributes; nesting registration can follow the same write path. The map overflow menu (`btn_map_overflow`) is the correct home for "Set as Master Map" and "Register as Detail Map…" actions. |
| `src/gui/widgets/map_widget.py` | The existing `QComboBox` map_selector handles multi-map navigation. Breadcrumb navigation (Phase 4) should be a label added left of this selector, not a replacement. The overflow menu (`_show_map_overflow_menu`) is the attach point for nesting actions. |
| `src/gui/mixins/map_calibration_mixin.py` | Provides the pattern for a dialog-backed map property workflow. A new `MapNestingMixin` (or additions to `MapDialogMixin`) should follow the same structure: open a dialog, gather user input, emit a signal, let `MapHandler` dispatch the command. |
| `src/gui/widgets/map/map_graphics_view.py` | Footprint overlay items (Phase 3) live here as scene-level `QGraphicsItem` subclasses, not as normal markers. The raster layer pipeline in `raster_layer_item.py` is the closest existing pattern for non-marker scene overlays. |
| `src/services/spatial_context_builder.py` | Currently enforces strict single-map context. The existing `SpatialContextBuilder.build()` docstring already documents the "no fallback" design decision. Phase 5 cross-map AI context should be an opt-in extension of this method, not a silent merge. |
| `src/app/constants.py` | `MAP_DEFAULT_WIDTH_METERS` is defined here. New string constants (`MAP_ROLE_MASTER`, `MAP_ROLE_DETAIL`) should follow the same pattern. |

### What Exists Now

- Multiple maps per world are supported.
- A single object can appear on multiple maps.
- Each map can store flexible metadata in `attributes`.
- Each map can store a width-based scale calibration
  (`attributes["width_meters"]`), persisted via `UpdateMapCommand` with an
  attribute-merge. The same mechanism directly supports registration metadata.
- AI spatial context enforces a strict single-active-map policy
  (`SpatialContextBuilder`).

### What Does Not Exist Yet

- A canonical master map flag or query helper.
- Parent/detail map relationships.
- Detail-map footprint overlays on another map's canvas.
- Map-to-map coordinate transforms.
- Cross-map navigation triggered from a footprint click.
- AI selection rules across nested maps.

## Core Model

### 1. One canonical master map per world

Each world should have exactly one map flagged as the master map.

Responsibilities of the master map:

- define the canonical world-local 2D coordinate space
- act as the reference surface for all detail maps
- host region footprints and detail-map entry points

### 2. Detail maps register into master space

Each detail map should store enough metadata to answer:

- where its covered area lies on the master map
- how a local point on the detail map maps into master-map coordinates
- how a master-map point maps back into the detail map, when applicable

### 3. Keep coordinates 2D and world-local

Use a world-specific coordinate space such as:

- normalized master coordinates `[0..1] x [0..1]`, or
- master pixels, or
- master-map world units derived from the existing width calibration

Recommended choice:

- use **normalized master coordinates** for registration metadata

Reason:

- independent of image resolution
- stable if master image is replaced with a higher-resolution version
- compatible with existing normalized marker placement model

## Transform Model

### Aspect-ratio-locked affine (Phase 1 — required)

The user's requirement that the footprint preserves the detail map's intrinsic
aspect ratio while supporting scale, rotation, and translation means a full
affine transform (without shear) is required from the start.  The simplified
axis-aligned extent approach is **not used**.

The transform is parameterised as:

- **centre** in master normalised coordinates `(cx, cy)`
- **scale** — width of the footprint in master normalised units
- **rotation** in degrees
- **aspect ratio** — derived from the detail map's image dimensions at
  registration time; stored and locked thereafter

See the "Resolved Design Decisions" section for the full matrix form.

### Future extension

If independent scaling of width and height ever becomes needed (deliberately
distorted placement), that can be added by replacing the single `scale_norm`
with `scale_x_norm` and `scale_y_norm`.  An explicit skew parameter is not
planned; the transform stays four-parameter (centre, scale, rotation,
aspect) for Phase 1 even though the composed master-space matrix already
contains an effective shear when rotation is non-zero and aspect ≠ 1.

## Proposed Metadata Shape

Store this in `Map.attributes`.

**This is the canonical metadata shape for the feature.** Any later
section in this document that quotes a different shape is informational
restatement only — when in doubt, this block wins.

Master map:

```json
{
  "map_role": "master"
}
```

Detail map (aspect-ratio-locked affine, supersedes the previous axis-aligned
extent shape):

```json
{
  "map_role": "detail",
  "parent_map_id": "uuid-of-direct-parent-map",
  "registration": {
    "mode": "aspect_locked_affine",
    "version": 1,
    "master_center_norm": { "x": 0.40, "y": 0.53 },
    "scale_norm": 0.175,
    "rotation_deg": 0.0,
    "aspect_ratio": 1.333,
    "confidence": "user_confirmed"
  }
}
```

Notes:

- `parent_map_id` points to the **direct parent**, not necessarily the root
  master map.  `MapNestingService.resolve_to_root()` walks the chain.
- `aspect_ratio` is `image_width / image_height` of the detail map, captured
  at registration time.  It is stored so the footprint can be reconstructed
  without reloading the image.
- `scale_norm` is the footprint width expressed in parent normalised
  coordinates `[0..1]`.  Height = `scale_norm / aspect_ratio`.
- `rotation_deg` is clockwise-positive to match the Qt `QTransform` convention.


## Registration Workflow

### Resolved workflow (canvas placement with aspect-lock)

1. User opens the parent map (master or an intermediate detail map).
2. User opens the overflow menu → "Register Detail Map…".
3. User picks the detail map from a list.
4. The app enters a **footprint placement mode** on the parent canvas:
   - A semi-transparent rectangle is shown, locked to the detail map's
     aspect ratio.
   - The user drags to move, uses handles to scale, and uses a rotation
     handle to rotate.
   - No corner-only picking; the entire footprint is constrained.
5. User confirms placement.
6. `RegisterDetailMapCommand` stores the affine registration in
   `detail_map.attributes`.
7. The footprint is rendered persistently on the parent map.

### Footprint tool interaction model

- **Drag body**: translate footprint centre.
- **Corner handles** (4): scale uniformly, preserving aspect ratio.
- **Rotation handle** (one, offset above the footprint): rotate around centre.
- **Escape / Cancel**: discard and exit placement mode without saving.

### Re-registration

Running "Register Detail Map…" on a map that is already a detail map is a
**replace**, not an error.  `RegisterDetailMapCommand` captures the
previous `parent_map_id` and `registration` block before overwriting, so a
single undo restores the prior parent and prior placement atomically.

The "Edit Footprint" action (parent-canvas drag-handle editing) is the
common path for tweaking placement under the same parent; full
re-registration is the path for moving a detail map to a different parent.

The validation contract in Phase 2 still applies to re-registration —
moving a detail map to a new parent can introduce a cycle even when the
original placement was legal.

### Later UX additions (not planned for Phase 1)

- Numeric precision panel (enter exact centre, scale, rotation as numbers).
- Snap footprint corners to nearby named features.

## UI/UX Integration Findings

### UI surface integration points

- `MapWidget` toolbar and overflow menu should remain the primary entry point:
  add `Set as Master Map`, `Register Detail Map...`, and
  `Edit Footprint` actions into the existing map overflow menu.
- `MapWidget` should add a compact breadcrumb chip row directly beside the
  existing map selector, not a separate panel, so map switching stays one-hop.
- `MapGraphicsView` should own all footprint rendering and editing handles
  through dedicated scene items, preserving the current dumb-UI boundary.
- `MapHandler` should be the only place that translates UI intent into
  commands, matching existing map scale and marker workflows.

### Clean interaction model

- Mode entry: selecting `Register Detail Map...` switches the view into a
  dedicated `footprint_edit` mode and updates the mode pill text.
- Mode affordance: the active footprint gets clear handles
  (corners for scale, top handle for rotation, body drag for translation).
- Mode exit: `Enter` confirms, `Escape` cancels, and clicking another map
  prompts to apply/discard pending footprint edits.
- Command timing: create/update commands should execute only on confirm,
  while drag operations remain local and transient for smooth interaction.

### Pretty and readable visual design

- Keep styling theme-aware via `StyleHelper` and `ThemeManager`; no hardcoded
  colors for footprint fills, outlines, handles, hover, or selected states.
- Use a two-layer footprint visual:
  1) translucent fill for area readability,
  2) high-contrast outline for edge precision.
- Use semantic state colors from theme tokens:
  default, hover, active-edit, invalid (out-of-bounds/depth-limit).
- Render labels with subtle contrast plate (rounded rect + text) so names stay
  readable over noisy map imagery.

### Usability and accessibility details

- Minimum handle hit-size should be visually small but interaction-large for
  precision on high-DPI displays.
- Add keyboard nudging while editing:
  arrow keys move, `Shift+arrow` moves faster, `[`/`]` rotate in fixed steps.
- Show a lightweight status hint in the existing overlay/banner area:
  `Drag to move · corners scale · top handle rotates · Enter save · Esc cancel`.
- Ensure all new actions have tooltips and are reachable from menu actions so
  the workflow is discoverable without hidden gestures.

### Safety UX and error handling

- On delete of a parent map with children, show a blocking dialog listing
  affected maps and provide quick actions to jump to each child.
- On invalid registration (depth cap exceeded, malformed metadata), keep the
  user in edit mode and show inline error feedback rather than failing silently.
- On world load, if nesting metadata is partially invalid, degrade gracefully:
  show non-editable footprints with a warning badge and keep map navigation
  functional.

### Performance and polish

- Use lightweight `QGraphicsItem` footprint objects; avoid rebuilding all
  items on every mouse move.
- During drag, update only the active footprint item; defer expensive
  overlap/validation checks with a short debounce.
- Keep animation subtle: quick fade-in for footprint labels and hover highlight
  transitions only. Avoid continuous animations while panning/zooming.

### Suggested phased UX rollout

This UX-only sequence runs alongside the implementation phases below.
The mapping is:

| UX phase | Implementation phase(s) | What ships |
| --- | --- | --- |
| A | Phases 1 + 3 | Master/detail roles, registration command, read-only footprints, click-to-open. |
| B | Phase 3 (edit mode) | Drag-handle editing on the parent canvas with confirm/cancel. |
| C | Later UX additions | Keyboard precision, numeric inspector panel. |
| D | Later UX additions | Overlap guidance, snapping to named features. |

Phase 4 (breadcrumb navigation) and Phase 5 (AI-aware policy) are not
gated by the UX-phase sequence — they layer onto Phase A as soon as the
underlying data exists.


## Implementation Strategy

### Phase 1: Add map nesting metadata

Add support for:

- one master map flag
- detail-map role
- master-map reference
- aspect-ratio-locked affine registration metadata

**Concrete steps:**

1. Add `MAP_ROLE_MASTER = "master"` and `MAP_ROLE_DETAIL = "detail"` to
   `src/app/constants.py`.

2. Add a `SetMasterMapCommand` to `src/commands/map_crud_commands.py`:
   - `__init__(self, map_id: str)` — the previous master is **state**, not
     input; the command must discover it itself at execute time so undo
     remains correct even if the world's master changed between submission
     and execution.
   - `execute(db_service)`: scans all maps for the current master (if any),
     captures it into `self._previous_master_id` for undo, clears
     `map_role` on that map via the attribute-merge path, then sets
     `map_role = MAP_ROLE_MASTER` on the target map. Same capture-then-mutate
     pattern as `UpdateMapCommand.execute` (`_previous_map`).
   - `undo`: re-applies `MAP_ROLE_MASTER` to the captured previous master
     (if any) and clears it on the target.
   - Register in `src/commands/registry.py`.

3. Add a `RegisterDetailMapCommand` to `src/commands/map_crud_commands.py`:
   - `__init__(self, detail_map_id, parent_map_id, registration: dict)` where
     `registration` matches the `aspect_locked_affine` shape above.
   - `execute`: writes `map_role`, `parent_map_id`, and `registration`
     into `detail_map.attributes` via the existing attribute-merge path.
   - `undo`: removes nesting keys and restores previous attributes.
   - Register in `src/commands/registry.py`.

4. Add a helper `get_master_map(maps: list[Map]) -> Map | None` in
   `src/services/repositories/map_repository.py` (or as a static utility
   in `MapRepository`) that scans `Map.attributes["map_role"]`.  No SQL
  change needed.  Also add `get_children_of(parent_id, maps)` for
  multi-level traversal and the delete-guard check.

5. Add "Set as Master Map" and "Register as Detail Map…" items to the
   existing `_show_map_overflow_menu` in `MapWidget`.

6. Wire overflow actions through `MapHandler` → command dispatch, following
   the same pattern as `on_map_scale_changed`.

Implementation notes:

- Keep metadata in `Map.attributes`.
- Persist through `UpdateMapCommand` or the new thin wrappers above.
- Avoid schema migrations until query pressure justifies them.
- `DeleteMapCommand` must **block** if any map has `parent_map_id` pointing
  to the map being deleted. Show a warning that lists those child maps by
  name. Do not silently cascade-clear registrations.

### Phase 2: Add transform service

Introduce `src/services/map_nesting_service.py` that can convert:

- detail local normalised → master normalised
- master normalised → detail local normalised

**Placement rules:**

- Must live in `src/services/`, not inside any widget or mixin.
- `MapWidget` / `MapGraphicsView` must never call transform math directly.
- `MapHandler` calls the service and passes pre-computed geometry to the
  view layer.

Responsibilities:

- Validate registration metadata shape.
- Compute aspect-ratio-locked affine transforms (translate, scale, rotate).
- Walk multi-level parent chains (`resolve_to_root`) to express a local point
  in root-master normalised space.
- Answer point-in-detail-map checks (used by the AI context extension).
- Provide footprint geometry (four normalised corner points in parent space)
  for rendering.
- Enforce depth cap (reject registration if chain depth would exceed 5).

#### Validation contract

`RegisterDetailMapCommand.execute` **must** call
`nesting_service.validate_registration(detail_map_id, parent_map_id, registration, all_maps)`
**before** mutating any attributes.  The service is the single source of
truth for legality; the command never inspects the chain itself.

`validate_registration` raises a `NestingValidationError` (or returns a
structured failure) when any of the following hold:

1. **Self-parent.** `parent_map_id == detail_map_id`.
2. **Unknown parent.** `parent_map_id` is not in `all_maps`.
3. **Parent is not a master or detail.** Parent's `map_role` is missing
   (the parent must first be designated a master or already-registered
   detail).
4. **Cycle.** Walking the parent's chain reaches `detail_map_id`. This is
   the case the depth-cap alone does not catch — short cycles
   (A→B→A) sit well under the cap. Cycle detection runs before depth
   counting.
5. **Depth cap exceeded.** Resulting chain length (root → … → detail) > 5.
6. **Malformed registration payload.** Wrong `mode`, missing keys, scale
   ≤ 0, aspect ≤ 0, non-finite numbers.

The same validation is reused on world load to flag corrupted
registrations (see "Safety UX and error handling" — degraded read-only
display of invalid footprints).

### Phase 3: Add master-map footprint overlays

On the master map, render each detail map's extent as:

- rectangle outline
- optional label
- optional hover summary
- click target to open that detail map

**Concrete integration:**

- Add a `DetailMapFootprintItem(QGraphicsRectItem)` in
  `src/gui/widgets/map/detail_map_footprint_item.py`, following the
  existing `MarkerItem` / raster overlay pattern.
- `MapGraphicsView` manages footprint items in a dedicated container that
  sits above features but below markers.  Add a new Z constant in
  `src/app/constants.py`:
  `MAP_LAYER_Z_FOOTPRINTS = 9` — between `MAP_LAYER_Z_FEATURES = 8` and
  `MAP_LAYER_Z_MARKERS = 10`.  All footprint items call
  `setZValue(MAP_LAYER_Z_FOOTPRINTS)`; their handles (corners, rotation
  knob) sit one tick higher (`+ 0.5`) so they always render above the
  rectangle body during edit but stay below markers.
- `MapHandler.on_map_selected()` checks whether the newly selected map is
  the master map; if so, it queries for registered detail maps and loads
  their footprints.
- Footprint clicks emit a `detail_map_clicked(map_id: str)` signal, which
  `MapHandler` handles by calling `map_selector.setCurrentIndex(…)` — the
  same path as a manual combobox selection.

### Phase 4: Add navigation

Support these actions:

- open detail map from master footprint click (see Phase 3 above)
- "Back to master map" button in the toolbar (conditional, visible only
  when active map is a detail map with a `parent_map_id`)
- breadcrumb label left of `map_selector`: `Master Map › Northern Kingdom`

**Concrete integration:**

- Add an optional `QLabel` breadcrumb widget in `MapWidget.__init__`,
  hidden by default.
- `MapHandler.on_map_selected()` reads `attributes["map_role"]` and
  `attributes["parent_map_id"]` from the newly loaded map and signals the
  widget to update the breadcrumb.

### Phase 5: Add AI-aware map policy

Once nesting exists, `SpatialContextBuilder.build()` should follow a strict
policy:

1. Use the active map first (no change from today).
2. If the active map is the master map and a registered detail map clearly
   covers the relevant location, optionally surface that fact as a note in
   the context block.
3. Never silently merge unrelated map contexts.

**Concrete integration:**

- Accept an optional `nesting_service: MapNestingService` in
  `SpatialContextBuilder.__init__`.
- When present and the active map is the master, check whether the marker's
  normalised position falls inside any registered detail map extent.
- Append one line to the context block: `Detail map available: <name>`.
- The caller (generation pipeline) decides whether to follow up.

## Rendering And Data Rules

### Keep local editing local

Markers, paths, and regions should remain authored in the local coordinates of
the current map.

Why:

- avoids forcing all editing into master space
- preserves current tool assumptions
- keeps map widgets simple

### Derive master-space positions when needed

When the app needs cross-map reasoning, derive master-space positions through
the registration transform.

Use cases:

- showing where a local entity sits on the master map
- detecting whether two detail maps overlap
- enabling AI to understand broader placement

### Marker reconciliation across nested maps

The same entity or event may legitimately have a marker on the master map
**and** on a detail map (e.g. a city pinned on the world map and again,
more precisely, on the city map).  Rules:

- **Authoring stays local.**  Placing a marker on a detail map never
  auto-creates a master-map marker, and editing one never edits the other.
  Each marker belongs to its own map.
- **No silent deduplication.**  The same `(object_id, object_type)` may
  appear on multiple maps.  This is by design.
- **AI canonicality follows Decision 5.**  When the active map is a detail
  map and that detail map has a marker for the object, that marker wins.
  When the active map is the master and a registered detail map's
  footprint covers the master-map marker, `SpatialContextBuilder` may
  surface a "detail map available" hint per Phase 5 — but the master
  marker remains the canonical source for the active context.
- **Optional UI hint (Phase 4+).**  The detail map's marker list may
  display a small badge when a co-named marker also exists on the parent
  chain.  This is a usability nicety, not a correctness requirement, and
  is out of scope for Phase 1.

### Footprints partially outside the parent rect

A detail map's footprint may extend outside the parent's `[0..1]²` extent —
for example a regional map covering an area whose master image was cropped
tightly.  This is **allowed** so users can re-image the master without
losing registrations.  Rendering rules:

- The footprint geometry is stored in master normalised coordinates and is
  not clamped at registration time.
- `MapGraphicsView` clips the rendered footprint to the visible canvas
  using Qt's normal scene-rect culling — out-of-bounds corners are still
  reachable when the user pans.
- Validation does not reject negative or > 1 corner coordinates; only
  malformed (non-finite, non-numeric) values are rejected.

### Replacing a parent map's image

Stored registrations are in the parent's **normalised** coordinate space,
so they survive an image swap that preserves aspect ratio (e.g. higher
resolution of the same map).  When the replacement image has a different
aspect ratio, two side-effects to be aware of:

- All existing footprints stay anchored at the same normalised centres
  and scales.  Visually they shift along the axis whose aspect changed.
  This is the desired behaviour: rotation and scale parameters were
  authored in normalised space, not pixel space.
- Detail-map `aspect_ratio` values are unaffected — they describe the
  detail map's own image, not the parent's.

If the user wants footprints to retarget against the new master image,
that is a manual re-registration per detail map.  No automatic recompute
is provided in Phase 1.

## Architecture Fit

This feature preserves the current layer boundaries.

### Core layer (`src/core/`)

- No changes to `Map` or `MapLayerNode` required.
- New string constants in `src/app/constants.py` (`MAP_ROLE_MASTER`,
  `MAP_ROLE_DETAIL`).

### Command layer (`src/commands/`)

- New `SetMasterMapCommand` and `RegisterDetailMapCommand` in
  `src/commands/map_crud_commands.py`.
- Both registered in `src/commands/registry.py`.
- `DeleteMapCommand` updated to block deletion when child maps are registered.

### Services layer (`src/services/`)

- New `src/services/map_nesting_service.py` owns transform math and
  registration validation.
- `MapRepository` gains a `get_master_map(maps)` helper.
- `SpatialContextBuilder` gains an optional `nesting_service` parameter.

### App layer (`src/app/`)

- `MapHandler` dispatches new commands and feeds footprint data to the view.
- `on_map_selected()` extended to load footprints when master map is active
  and to show/hide breadcrumb on any map switch.
- No changes to `AppCoordinator` or `CommandCoordinator` — the existing
  `command_requested` signal path is sufficient.

### GUI layer (`src/gui/`)

- `MapWidget` overflow menu gains two new actions.
- `MapWidget` toolbar gains an optional breadcrumb label.
- `MapGraphicsView` gains footprint item management.
- New `DetailMapFootprintItem` in `src/gui/widgets/map/`.
- No business logic in any widget — all transform math stays in the
  service layer.

### Threading

No new threading concerns.  All command dispatch follows the existing
queued-connection path through `CommandCoordinator` → `DatabaseWorker`.
`MapNestingService` is a pure stateless math/validation utility; it can be
called from either thread.

## Risks To Avoid

- Do not add CRS, EPSG, or lat/long terminology to this feature.
- Do not overload the existing width-in-meters calibration into pretending to be
  map nesting.
- Do not store nesting logic only in ad hoc marker attributes.
- Do not let AI select map context implicitly without a clear rule.
- Do not put transform math inside `MapWidget` or `MapGraphicsView`.

## Recommendation

Build this as **strict 2D master-map nesting**, not georeferencing.

Revised first slice (updated to reflect resolved decisions):

1. Opt-in master map designation per world (zero is valid until set).
2. Multi-level nesting: detail maps may be registered under any map that
   has a `map_role` of `master` or `detail`, up to a depth cap of 5.
3. Aspect-ratio-locked affine registration: canvas footprint tool on the
   parent map with scale, rotation, and translation handles.
4. `MapNestingService` with composable transform chain for multi-level
   resolution.
5. Clickable footprints with drag-handle editing on the parent map canvas.
6. Full breadcrumb navigation chain.
7. Blocking delete guard on any map with registered children.

This gives ProjektKraken a powerful and spatially consistent maps-in-maps
system without introducing real-world geospatial complexity.

## Resolved Design Decisions

All open questions resolved 2026-04-25.

| # | Decision | Choice |
|---|---|---|
| 1 | Master map required? | **Opt-in.** Zero master maps allowed; nesting activates when the user explicitly designates one. |
| 2 | Nesting depth | **Multi-level.** Detail maps may nest under other detail maps, enabling world → region → city chains. |
| 3 | Registration method | **Aspect-ratio-locked canvas placement.** Rectangle draw on the master map, but the footprint is constrained to the detail map's intrinsic aspect ratio. The user operates with scale, rotation (integer degrees or free), and translation — no distortion. |
| 4 | Footprint editing | **Canvas-editable with drag handles.** Rotate, scale, and move directly on the master map canvas. |
| 5 | AI canonical source | **Active map wins.** Detail map marker is canonical when that detail map is active; master map marker is the fallback otherwise. |
| 6 | Delete master map | **Block with warning**, listing the affected detail maps by name. User must re-register or delete them first. |

### Design Impact of Decision 2 (Multi-Level Nesting)

Multi-level nesting requires the transform chain to compose, not just look up
a single parent. Implementation notes:

- `MapNestingService` must support `resolve_to_master(detail_map_id, local_point)` that walks the parent chain until it reaches the master map.
- `DeleteMapCommand` must block when descendants are registered and present a
  warning with affected-map names.
- Breadcrumb (Phase 4) must render the full chain: `World Map › Northern Kingdom › Capital District`.
- Nesting depth should be capped (e.g. 5 levels) to prevent runaway chains.

### Design Impact of Decision 3 (Aspect-Ratio-Locked + Rotation)

The user's clarification means **Phase 2 (affine support) is required from
Phase 1**, not deferred. The registration must store:

- the footprint centre in master normalised coordinates
- the scale factor (footprint width in master normalised units)
- the rotation angle in degrees (stored as float)
- the detail map's intrinsic aspect ratio (derived from image dimensions at
  registration time and stored as `aspect_ratio: float`)

The axis-aligned `x_min/y_min/x_max/y_max` extent shape from any earlier
draft is **superseded**.  The canonical metadata shape lives in the
"Proposed Metadata Shape" section above — refer to that block as the
single source of truth.  This section only adds the math.

The transform from detail normalised `(u, v)` to master normalised `(x, y)`
is:

$$
\begin{bmatrix} x \\ y \end{bmatrix}
=
\begin{bmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{bmatrix}
\begin{bmatrix} s & 0 \\ 0 & s / r \end{bmatrix}
\begin{bmatrix} u - 0.5 \\ v - 0.5 \end{bmatrix}
+
\begin{bmatrix} c_x \\ c_y \end{bmatrix}
$$

where $s$ = `scale_norm`, $r$ = `aspect_ratio`, $\theta$ = `rotation_deg`
in radians, and $(c_x, c_y)$ = `master_center_norm`.

**Sign convention.**  `rotation_deg` is **clockwise-positive** as seen on
screen, matching `QTransform`.  The matrix above is written in standard
mathematical (counter-clockwise) form; because Qt's coordinate system is
y-down, applying a positive-θ counter-clockwise math rotation produces a
visually clockwise rotation on screen.  The two cancel out, so the formula
is correct as written — but implementers must not "fix" the sign of the
sin terms without also flipping the y-axis convention.

**Shape of the transform.**  The composition is rotation × non-uniform
scale × translation.  When `aspect_ratio ≠ 1`, the `diag(s, s/r)` factor
is non-uniform, so the composed 2×2 matrix is **not** a similarity
transform — viewed in the master's axes it has an effective shear
component for non-zero rotations.  The transform is still strictly affine
(no skew parameter, four parameters total), and the inverse is a
closed-form 2×2 matrix inversion: not "trivially identical to the
forward", but standard.

## Current Conclusion

The right foundation is a **single-master, strict-2D nesting model** with
detail maps registered into master-map normalized space.

That is enough to support:

- world map -> regional map -> city map workflows
- reliable navigation between map levels
- future cross-map AI reasoning
- future footprint overlays and overlap detection

without introducing real-world geospatial complexity.
