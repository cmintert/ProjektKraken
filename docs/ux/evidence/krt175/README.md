# C: connected-map geometry

## Scope and source review

KRT-175 follows the separate B commit `2b5556d2` on `detail-maps`. It extends the
same opt-in connected-display pipeline to paths and regions. `ProjectedGeometry`
represents all surviving polygon/line components with holes and source, target,
state and effective-date identity, without extending persisted feature geometry.
The projector compares complete representations before clipping/simplification;
point-versus-geometry disagreements are ambiguous, never silently selected.
Local authored placement retains precedence.

The canonical dated-geometry resolver selects Base Geometry or its effective
replacement at the playhead. Source topology is validated without repair or
anchor fallback and cached by immutable state identity. Full affine projection
supports rotated/anisotropic chains. Shapely clipping retains every surviving
component. Topology-preserving simplification has a half-screen-pixel budget and
falls back if component or hole counts change. Nothing rewrites source geometry,
markers, trajectories, temporal facts, calibration or command history.

The database adapter now captures serialized snapshots only. Chronology,
projection, clipping and simplification run on a dedicated calculation thread.
The coordinator coalesces both stages, rejects obsolete generations and joins
calculation before owner teardown. A blocked-calculation test verifies another
queued database capture completes while calculation is held. No new worker slot
or feature responsibility is added to the transitional choke points.

## Authoring and presentation review

Contracts 1/2/4/5/6/7/9/11 and B's visible settings routes remain unchanged. Region
outlines use independent odd-even rings; every fragment belongs to one selectable,
non-draggable source item. Theme-owned entity/event identity colors and cosmetic
outline strokes retain meaning across zoom. Hollow/outline display identifies
derived content. Source tooltips distinguish Base Geometry and dated geometry.
Double-click/Enter navigates through the existing protected source-map route;
Delete/Backspace cannot mutate the projection. Other keys retain normal ownership.
Authored Layers and working copies remain independent. No policy exception or
baseline regeneration is used.

## Documentation review record

| Field | Record |
| --- | --- |
| Reader / purpose | Existing map authors; how-to in the maps manual |
| Canonical release/pages | Unreleased; maps task and developer architecture explanation |
| Source identity | B baseline above plus C files in this commit |
| Sources inspected | Dated geometry, spatial/region primitives, derived model, geometry projector, reader/calculator/coordinator, overlay and tests |
| Help IDs/anchors | Existing map.hierarchy, connected-display and issues targets retained; no menu route meaning changes |
| Persistence/recovery | Display toggles only; source-map edits use existing command/Undo ownership; disabling projection clears derived items |
| Rendered review | Six-theme geometry captures under artifacts/krt175/presentation; dark/enlarged and light/normal outlines, split gap and retained hole inspected |
| Human prose/live Help approval | Pending |
| Reader-round owner/cohort/date | Pending; no participant-performance claim |

Use the [documentation review form](../../../developer/documentation-review.md)
and [reader protocol](../../../developer/documentation-reader-testing.md) for
human acceptance. Offscreen evidence does not establish native DPI/GPU usability.

## Verification

The final B/C group covers point compatibility, split regions/retained holes,
disconnected path fragments, exact dated-state boundary/provenance, equivalent
ring order, mixed-representation conflicts, invalid topology, rotated/anisotropic
chains, serialized derived models and immutable saved rows. Actual scene paths
exclude holes and gaps; Delete produces no command; source navigation waits for
the edit safeguard. Serialized database capture and CPU calculation have separate
thread ownership with explicit shutdown.

Larger-data regressions retain 500 polygon components and 250 holes from 250
regions and simplify a 10,000-vertex path within the half-pixel Hausdorff bound.
Their five-second ceilings are broad regression guards, not claimed creator
latency or production-world benchmarks. Cached source topology is reused across
playhead frames. All six palettes have 10pt/20pt menu/outline/keyboard checks.

The final combined projection/dependency/choke-point group passes 114 cases,
including 47 B/C behavior/presentation cases. Repository Ruff/mypy (711 source
files), visual/complexity policy, Help inspection/build, strict Sphinx and test
inventory pass before the C commit. These results precede the full push gate.

Repository checks and final delivery evidence are recorded in KRT-175. Human
prose, native full-app DPI/GPU, package acceptance and a fresh reader round remain
Pending / Not tested. The required branch push gate is run after the C commit.
