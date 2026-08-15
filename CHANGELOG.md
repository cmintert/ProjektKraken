---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-08-15
**Commit:** 3708c68c
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- *(2026-08-15)* **Maps / Marker Icons**: Added portable SVG, PNG, JPG/JPEG,
  and WebP project icons for point markers, with secure world-relative path
  resolution, aspect-preserving raster rendering, and raster-aware styling
  controls.

### Fixed

- *(2026-08-15)* **Maps / Marker Labels**: Kept labels adjacent to each
  marker's current rendered edge across map-relative and fixed-screen sizing.
- *(2026-08-15)* **Maps / Feature Deletion**: Fixed path and region layer
  deletion leaving persistent marker geometry that reappeared as `Unknown`.
- *(2026-08-13)* **CI / Prerelease Assets**: Restricted GitHub release uploads
  to the public ZIP and checksum so packaged-smoke report directories cannot
  interrupt publication.

### Changed

- *(2026-08-15)* **Maps / Marker Sizing**: Point-marker icons now scale with
  their map by default, with per-marker percentage or calibrated metric sizing,
  an optional fixed-screen mode, readable labels, and reliable small-token
  pointer targets.
- *(2026-08-15)* **Maps / Status Bar**: Replaced redundant float timeline
  values with the current fit-relative map zoom factor.
- *(2026-08-15)* **Documentation / Testing**: Updated the map guide and added
  regression coverage for marker sizing, label placement, pointer targets, and
  zoom status.
- *(2026-08-13)* **Documentation / Windows Onboarding**: Replaced source
  launcher instructions for testers with the verified download, checksum,
  extraction, and double-click workflow; kept source launch details in the
  developer guide.
- *(2026-08-15)* **Testing / Map Icons**: Added format, renderer-transition,
  path-containment, and raster-styling regression coverage.
- *(2026-08-15)* **Testing / Feature Deletion**: Added path and region
  regression coverage for persistent deletion and undo restoration.
- *(2026-08-15)* **Testing / Marker Labels**: Added rendered-gap regression
  coverage across map-relative and fixed-screen zoom levels.

## [0.19.4]

### Changed

- *(2026-08-13)* **Release**: Bumped project and application metadata to
  version 0.19.4.

### Fixed

- *(2026-08-13)* **CI / Packaged Smoke**: Increased the bounded executable
  cold-start allowance for hosted Windows runners and retained application and
  PyInstaller diagnostics when the package gate fails.

## [0.19.3]

### Changed

- *(2026-08-13)* **Release**: Bumped project and application metadata to
  version 0.19.3.

### Fixed

- *(2026-08-13)* **Packaging / Windows Extraction**: Shortened the ZIP's root
  directory and added an archive-entry length gate so normal user extraction
  paths remain below Windows' legacy path limit; generalized the clean-VM
  validation record for exact future beta candidates.
- *(2026-08-13)* **CI / Prerelease**: Added an exact-tag manual recovery path
  and explicit GitHub repository context for protected beta publication.

## [0.19.2]

### Changed

- *(2026-08-13)* **Release**: Bumped project and application metadata to
  version 0.19.2.

### Fixed

- *(2026-08-13)* **Packaging / Clean Runner**: Classified the optional SciPy
  compatibility import warning emitted by the hash-pinned PyInstaller hooks.

## [0.19.1]

### Added

- *(2026-08-12)* **Packaging / Windows**: Added a hash-pinned Windows x64
  PyInstaller package pipeline, audited runtime manifest, two-launch packaged
  smoke test, ZIP checksum, protected prerelease workflow, and clean-VM release
  gate.

### Fixed

- *(2026-08-13)* **Packaging / Clean Checkout**: Tracked the offline PyVis graph
  runtime assets required by clean Windows CI builds and classified PyInstaller
  warnings for unused optional SQL drivers.

- *(2026-08-12)* **Packaging / Resources**: Bundled the default layout and
  Longform web assets, excluded development tooling, and added Windows icon,
  version, architecture, and package-content validation.

### Changed

- *(2026-08-13)* **Release**: Bumped project and application metadata to
  version 0.19.1.
- *(2026-08-12)* **Release / Status**: Recognized plain and beta-package Git
  tags without moving the existing `0.19.0` release tag.

- *(2026-08-12)* **Release**: Bumped project and application metadata to
  version 0.19.0.
- *(2026-08-12)* **Tooling**: Updated release checks and bump guidance for the
  centralized runtime version source.

## [0.19.0]

### Added

- *(2026-08-12)* **Analysis / Trust and Actionability**: Added explicit AI
  scopes and request presets, strict repaired JSON contracts, stable evidence
  references and strength, honest coverage states, source navigation,
  session-only comparison and dismissal, stale-report tracking, and Markdown
  and JSON export.
- *(2026-08-12)* **Analysis / Integrity**: Added duplicate relation, wiki-link,
  attachment and map path, finite date and duration, shared temporal-window,
  malformed lifespan, and related out-of-lifespan checks, with optional
  remembered editorial checks.

- *(2026-08-10)* **Map / Temporal Visibility**: Added half-open existence
  windows for markers and vector geometry, calendar-aware validity editing,
  layer-tree awareness and filtering, selectable temporal ghosts, and
  playhead-aware spatial exclusion.

- *(2026-08-10)* **Map / Temporal Geometry**: Added Base plus dated replacement
  geometry for paths and regions, with cached playhead playback,
  calendar-aware state management, working-copy editing, persistent undo, and
  historical spatial-context resolution.

- *(2026-08-09)* **Editor / Context Tags**: Added per-world remembered session
  context tags for interactive entity and event creation, with autocomplete,
  persistent active-state reminders, and explicit enable and disable controls.
- *(2026-08-09)* **Editor / Recovery**: Added a local recovery ledger and
  selective, undoable cleanup for records affected by context tags without
  changing autosave or portable world formats.

### Fixed

- *(2026-08-12)* **Analysis / UI**: Matched result-row selection to the Project
  Explorer, preserved readable themed contrast, and expanded wrapped result text
  without clipping.
- *(2026-08-12)* **Analysis / AI**: Made lore-suggestion string contracts
  explicit and safely normalized numeric dates returned by providers.
- *(2026-08-12)* **Architecture / Stability**: Restored worker-owned database
  access, atomic command and tag persistence, asynchronous semantic search,
  deterministic resource cleanup, and one-way source dependencies.
- *(2026-08-12)* **UI / Maintainability**: Replaced unexplained thresholds and
  hard-coded interface colors with named constants and theme-aware styling.

- *(2026-08-11)* **Map / Styling**: Preserved translucent region fills during
  style edits and kept map-label opacity independent from marker and geometry
  opacity.

- *(2026-08-11)* **Map / Temporal Editing**: Kept layer validity editing open
  while the playhead moves, refreshed property-only layer changes immediately,
  and preserved layer selection and expansion state.
- *(2026-08-11)* **Map / Geometry**: Kept applied base geometry authoritative
  without restart, recovered failed geometry saves, and prevented temporal
  status changes from shifting the map viewport.

- *(2026-08-10)* **Map / Visibility**: Unified manual, inherited, zoom, and
  temporal visibility, kept selected trajectories aligned with their owners,
  and composed layer opacity with future and ghost styling.

- *(2026-08-09)* **Editor / Tags**: Restored normalized tags during entity and
  event update undo, and prevented deferred chip-layout callbacks from outliving
  closed editors and dialogs.

- *(2026-08-09)* **Security / Storage**: Prevented ordinary world manifests
  from redirecting databases through traversal, absolute, drive, UNC, or
  symlink paths, and required local approval for external databases.
- *(2026-08-09)* **Stability / Storage**: Prevented missing approved external
  databases from being silently recreated and added explicit recovery warnings.

### Changed

- *(2026-08-12)* **Analysis / Usability**: Replaced duplicated full lore text in
  result rows with compact previews and labeled, scrollable details and sources.
- *(2026-08-12)* **Documentation / Testing**: Documented the lore master-detail
  workflow and added selection, wrapping, schema, and panel regressions.
- *(2026-08-12)* **Refactor / Maintainability**: Centralized version and shared
  configuration contracts, decomposed oversized UI constructors, and added
  enforceable complexity, public-docstring, magic-value, and dependency gates.
- *(2026-08-12)* **Testing / Quality**: Added transactional command, worker
  boundary, timeline-cache, and architectural regression coverage; verified
  the complete unit, integration, GUI, CLI, security, and reproduction suites.

- *(2026-08-12)* **Documentation / Testing**: Documented scoped advisory
  analysis, evidence, partial failures, stale reports, and instant relations;
  added focused contract, GUI, worker, and integration regressions.
- *(2026-08-12)* **Analysis / Completeness**: Replaced the opaque world-health
  score with transparent 100-point entity and event documentation profiles.
- *(2026-08-12)* **Relations / Temporal Semantics**: Made event-only relations
  explicit instants that follow their source event while preserving invalid
  manual equal-bound intervals.

- *(2026-08-11)* **Map / Temporal Editing**: Separated temporal validity from
  general layer properties with a focused date-range editor and scope-safe
  persistence.
- *(2026-08-11)* **Documentation / Testing**: Documented the separated temporal
  workflow and added dialog-scope, playhead capture, validation, switching, and
  partial-update regressions.

- *(2026-08-11)* **Testing / Map**: Added regressions for region fill channels,
  alpha-preserving style edits, and independent label opacity.

- *(2026-08-11)* **Map / Labels**: Unified point, path, and region labels with
  theme-aware collision placement and emphasized geometry Apply as the primary
  action.
- *(2026-08-11)* **Testing / Map**: Added temporal capture, layer
  reconciliation, geometry cache recovery, viewport stability, and shared-label
  regressions.

- *(2026-08-10)* **Documentation / Testing**: Documented vector-feature
  validity and added resolver, rendering, ghost, filtering, command,
  trajectory, dialog, and spatial-context regressions.

- *(2026-08-10)* **Documentation / Testing**: Documented temporal path and
  region editing, regenerated schema references, and added domain, repository,
  command, coordinator, deletion, playback, and spatial-context coverage.

- *(2026-08-09)* **Testing / Maintenance**: Added context creation, persistence,
  cleanup, database round-trip, and MainWindow coverage, and clarified Pillow
  thumbnail image typing.

- *(2026-08-09)* **Editor / Tags**: Replaced per-tag widgets and the custom
  flow layout with a theme-aware, wrapping model/view chip editor that supports
  keyboard removal, bounded long tags, and scalable bulk loading.
- *(2026-08-09)* **Graph / Accessibility**: Clarified the graph tag filter label
  and added accessible naming and non-mutating filter guidance.
- *(2026-08-09)* **Testing / UI**: Reworked tag-editor regression coverage for
  chip layout, interaction, autocomplete, theme updates, and large tag sets.
- *(2026-08-09)* **Editor / UX**: Improved reading-width wrapping and timeline
  cards, hid internal attributes while preserving them, and refreshed editor,
  tag, and generation styles on live theme changes.
- *(2026-08-09)* **Testing / UI**: Added regression coverage for readable text
  wrapping, timeline navigation, hidden attributes, checked indicators, and
  theme-aware editor controls.
- *(2026-08-09)* **AI / Audit Logging**: Replaced plaintext prompt-response logs
  with versioned per-world JSONL events that link exact prompts and raw model
  replies to review actions, ratings, comments, automatic filtering, and user
  edits for prompt-quality analysis.
- *(2026-08-09)* **Testing / AI**: Added regression coverage for structured
  generation, review, feedback, edit, summary, and per-world audit events.
- *(2026-08-09)* **Documentation / Branding**: Replaced the project logo and
  added it to the generated documentation sidebar.
- *(2026-08-09)* **World Storage**: Added complete world-folder registration,
  advanced external database linking, persisted approval, and revocation.
- *(2026-08-09)* **Documentation / Testing**: Documented portable and external
  storage behavior and added path-redirection, trust, startup, and World Manager
  regression coverage.
- *(2026-08-09)* **Release**: Bumped project and application metadata to
  version 0.18.8.
- *(2026-08-09)* **Tooling**: Added a validated project version-bump skill
  covering release checks, builds, commits, and tags.

## [0.18.8]

### Added

- *(2026-08-09)* **Timeline**: Added optional, persisted event snapping for
  manual playhead drags and ruler clicks using a zoom-independent screen
  distance.
- *(2026-08-09)* **Map / Trajectories**: Added authoritative Timed Locations,
  distance-timed Route points, bulk automatic conversion, and endpoint-driven
  route recalculation.
- *(2026-08-09)* **Map / Trajectories**: Allowed an entity's ordinary marker
  position to be moved before its first trajectory date, while retaining
  trajectory ownership from the first date onward and holding the final
  location indefinitely.
- *(2026-08-09)* **Map / Trajectories**: Added entity trajectory creation,
  playhead-based locations, Travel, derived Stay, explicit Relocation, safe
  route-preserving retiming, opt-in reordering, shift-later timing, and segment
  duration, distance, and average-speed feedback.
- *(2026-08-09)* **Architecture / Trajectories**: Added backward-compatible,
  lazily persisted keyframe UUID and segment-mode metadata while retaining the
  OGC MF-JSON `MovingPoint` payload and preserving unknown properties.
- *(2026-08-08)* **Map / Trajectories**: Added anchored and whole-trajectory
  speed equalization with distance-weighted date previews, calibrated or
  relative speed feedback, and reversible working-copy confirmation.
- *(2026-08-08)* **Map / Trajectories**: Added direct temporal keyframe
  editing through compact calendar controls and explicit playhead copying,
  with live reordering, date feedback, affected-segment highlighting, and
  scoped cancel.
- *(2026-08-08)* **Map / Trajectories**: Added direct spatial trajectory
  editing with draggable keyframes, midpoint insertion, snapping, compact
  Apply and Cancel controls, and focus-independent shortcuts.
- *(2026-08-08)* **Architecture / Trajectories**: Added atomic complete-row
  trajectory replacement, stale-snapshot conflict detection, and persistent
  exact undo and redo through `UpdateTrajectoryCommand`.
- *(2026-08-08)* **Map / Trajectories**: Added stable editable-keyframe values,
  independent snapshot cloning, midpoint-time inference, and validation for
  finite dates, normalized coordinates, and timestamp collisions.
- *(2026-08-03)* **Longform / LAN Sharing**: Added explicit authenticated LAN
  publishing with ephemeral eight-digit access codes and brute-force limits.

### Fixed

- *(2026-08-09)* **Map / Lore**: Used refreshed stored summaries for marker
  tooltips after event and entity changes, and formatted trajectory edit dates
  with the active calendar.
- *(2026-08-09)* **Map / Trajectories**: Reworked the date editor into readable
  summary, constraint, and control rows, with visible playhead dates, inline
  errors, and disabled invalid playhead assignment.
- *(2026-08-09)* **Map / Trajectories**: Prevented the first arrival-node
  selection from resizing the map viewport and visually displacing the marker
  and trajectory by reserving the segment-information row throughout editing.
- *(2026-08-08)* **Map / Trajectories**: Prevented the first keyframe selection
  from resizing the map viewport and visually shifting trajectory nodes, with
  regression coverage for stable edit-session geometry.
- *(2026-08-08)* **Map / Trajectories**: Discarded active trajectory edits
  when switching maps and suppressed ambiguous duplicate trajectory rows from
  playback instead of silently overwriting them.
- *(2026-08-08)* **Map / Trajectories**: Kept trajectory editing controls at
  their content height and collapsed inactive calendar controls so the map
  retains the available workspace.
- *(2026-08-08)* **Map / Trajectories**: Preserved one-keyframe trajectories
  and rejected ambiguous duplicate trajectory rows instead of silently choosing
  or deleting data.
- *(2026-08-03)* **Longform / Security**: Restricted default publishing to
  localhost and made HTTP longform reads unable to modify world databases.
- *(2026-08-06)* **Longform / Security**: Hardened embedded longform publishing
  with Content-Security-Policy headers, sanitized markdown rendering, and
  removed direct LAN shell access token exposure.

### Changed

- *(2026-08-09)* **Documentation / Testing**: Documented timeline event
  snapping and expanded regression coverage for snapping, marker refreshes,
  summary tooltips, calendar-aware trajectory labels, and visual styling.
- *(2026-08-09)* **Architecture / Trajectories**: Replaced compatibility repair
  with strict trajectory metadata v2 and logged removal of incompatible rows.
- *(2026-08-09)* **Documentation / Testing / Trajectories**: Documented automatic
  route timing and strict loading, regenerated schema guidance, and expanded
  domain, repository, coordinator, and map UI regression coverage.
- *(2026-08-09)* **Documentation / Trajectories**: Expanded trajectory
  authoring and playback guidance, clarified Escape priority, and corrected the
  database reference from legacy `[t, x, y]` arrays to MF-JSON plus versioned
  properties metadata.
- *(2026-08-08)* **Cleanup / Trajectories**: Removed legacy Draft and Clock
  modes, hover keyframe gizmos, granular mutation pathways, and obsolete
  command compatibility in favor of the atomic direct editor.
- *(2026-08-08)* **Documentation / Trajectories**: Documented direct route
  editing, explicit playhead date assignment, speed equalization, cancellation,
  and keyboard behavior.
- *(2026-08-08)* **Testing / Trajectories**: Added speed calculation,
  100-keyframe, anchor lifecycle, preview, keyboard, calibrated display, and
  compact-layout regression coverage.
- *(2026-08-08)* **Testing / Trajectories**: Added temporal edit-session,
  coordinator, overlay, shortcut, explicit playhead-copy, cancellation, and
  map-widget regression coverage.
- *(2026-08-08)* **Architecture / Trajectories**: Added isolated edit sessions,
  playback-marker protection, targeted authoritative reloads, and conflict
  handling that prevents external refreshes from overwriting working edits.
- *(2026-08-08)* **Testing / Trajectories**: Added spatial overlay, edit-session,
  coordinator, shortcut, map-widget, worker, and reload regression coverage.
- *(2026-08-08)* **Testing / Trajectories**: Added repository and command
  coverage for metadata preservation, zero- and one-point states, conflicts,
  rollback, snapshot isolation, and persistent history reconstruction.
- *(2026-08-08)* **Testing / Trajectories**: Added focused coverage for
  trajectory snapshot independence, validation boundaries, midpoint inference,
  and documented interpolation clamping behavior.
- *(2026-08-03)* **Testing / Security**: Added authentication, binding,
  read-only database, identifier-validation, and publishing UI regressions.
- *(2026-08-03)* **Release**: Bumped project and application metadata to
  version 0.18.7.

## [0.18.7]

### Added

- *(2026-07-28)* **AI / Summaries**: Added editable and deletable event and
  entity summaries with manual attribution, undoable persistence, and enforced
  30-percent and 150-word generation limits.
- *(2026-07-28)* **AI / Analysis**: Added cancellable, snapshot-based
  background analysis with partial results and capture timestamps.
- *(2026-07-27)* **Explorer**: Added an undoable Delete action to the
  event and entity context menu.
- *(2026-07-26)* **Map / UX**: Added a one-shot Add Marker toolbar tool with click-to-place guidance and Escape cancellation.
- *(2026-07-26)* **Raster / Painting**: Added mode-aware discrete, continuous, and RGBA brush, fill, gradient, sampling, and eyedropper operations with tiled stroke capture.
- *(2026-07-26)* **Raster / UX**: Added explicit Base or dated edit targets, mode-specific controls, accessible tool labels, and visible saving, saved, and failed states.
- *(2026-07-25)* **Map / Raster**: Added aggregate loading, raster asset and query services, reversible command artifacts, layer properties, and dated-state editing.
- *(2026-07-25)* **Documentation**: Added a guide to maps, layers, raster purposes, timeline states, queries, and calibration.
- *(2026-07-22)* **AI / LM Studio**: Added model discovery, separate generation and embedding model selection, connection testing, and per-world AI preferences for OpenAI-compatible local servers.
- *(2026-07-22)* **AI / Security**: Added operating-system keyring storage for provider credentials instead of retaining API keys in application settings.
- *(2026-07-22)* **AI / Task Templates**: Added four intent-based description tasks plus portable per-world custom templates with create, edit, duplicate, and delete workflows.

### Fixed

- *(2026-08-02)* **Map / Keyframes**: Exposed the first-keyframe action for
  selected entity markers while keeping event markers ineligible, with
  regression coverage for canvas and Layers selections.
- *(2026-08-01)* **Map / Theme**: Refreshed locally styled map controls and
  overlays when the active theme changes, with regression coverage.
- *(2026-08-01)* **GUI / Typing**: Corrected dialog, widget, model, graph,
  longform, map, raster, and Qt utility contracts without changing valid UI
  behavior.
- *(2026-08-01)* **Testing / Stability**: Updated coordinator tests for the
  queued invocation helper, isolated embedding tests from their optional
  dependency, and corrected the summary audit fixture.
- *(2026-08-01)* **Editor / Stability**: Made splitter tab drops transactional,
  gave Explorer rows explicit event and entity types, and replaced ambiguous
  timeline graphics-item state with typed ownership.
- *(2026-08-01)* **Production / Typing**: Corrected editor-mixin, parsing,
  backup, provider, raster, command, CLI, and webserver boundary contracts.
- *(2026-08-01)* **AI / Settings Stability**: Validated persisted AI and backup
  settings plus generation prompts at their runtime boundaries, falling back
  safely when stored values are malformed.
- *(2026-08-01)* **Qt / Typing**: Corrected command-history, map-editing,
  sheet-builder, and wiki-editor contracts while preserving runtime behavior.
- *(2026-08-01)* **Stability / Typing**: Typed persisted settings,
  worker-result, editor/gallery, Fast Inject, and map-mixin boundaries without
  changing valid runtime flows.
- *(2026-08-01)* **Qt / Typing**: Restored the native graphics-view scene API,
  centralized typed cross-thread slot invocation, and corrected timeline return
  contracts without changing queued delivery behavior.
- *(2026-08-01)* **CLI / Typing**: Updated backup and attachment commands to use
  the current service and domain-model contracts.
- *(2026-07-31)* **Stability / Typing**: Guarded analysis commands against
  unavailable databases, captured queued navigation selections, and validated
  copied layer trees before mutation.
- *(2026-07-31)* **Startup / Stability**: Validated persisted active-world
  settings before path construction and standardized disconnected repository
  failures through a checked connection accessor.
- *(2026-07-30)* **Import / Export**: Typed import completion, corrected
  failure results, and moved single-item Obsidian database access and file
  generation to queued worker-owned operations.
- *(2026-07-28)* **AI / Summaries**: Reduced over-limit failures with lower
  generation targets, draft-only compression retries, safe sentence-boundary
  fallback, and shorter-source rules without wiki-link constraints.
- *(2026-07-28)* **Editor / Summaries**: Kept newly generated and manually
  edited summaries visible by validating the wiki editor's render cache
  against its current document.
- *(2026-07-28)* **AI / Responsiveness**: Moved model requests off the
  database worker so editing, navigation, and queued database work remain
  available during AI Analysis.
- *(2026-07-28)* **Editor / UX**: Kept description-editor context menus
  opaque by limiting transparent styling to the text viewport.
- *(2026-07-28)* **Wiki / Relations**: Reconciled automatic mentions from
  saved wikilinks using canonical UUID endpoints, removing stale, malformed,
  and duplicate relations instead of appending offset-based rows.
- *(2026-07-28)* **Editor / Formatting**: Reset new paragraphs after headings
  using semantic block state and explicit body insertion formatting.
- *(2026-07-28)* **AI / Testing**: Made prompt-preview coverage headless-safe
  without bypassing real dialog construction.
- *(2026-07-28)* **Stability**: Made LanguageTool, semantic timers, theme
  callbacks, context menus, and Qt widget teardown lifecycle-safe.
- *(2026-07-28)* **Search**: Added accurate indexed, unchanged, and failed
  rebuild totals with monotonic worker and CLI progress reporting.
- *(2026-07-28)* **Map / Layers**: Kept worker-owned layer trees authoritative
  instead of applying stale UI snapshots.
- *(2026-07-26)* **Development / Typing**: Fixed mypy namespace-package discovery and stale window, worker, Qt, and map-mixin contracts, reducing the baseline from 1,217 to 1,017 errors.
- *(2026-07-26)* **Raster / Stability**: Kept Paint active across successful strokes, paused safely on failed saves, and prevented editing a stale raster target.
- *(2026-07-26)* **Map / Layers**: Removed deleted nodes from refreshed layer trees and cleared Paint controls when the selected raster no longer exists.
- *(2026-07-25)* **Map / Stability**: Made map and raster mutations transactional and kept undo and redo stacks unchanged when worker operations fail.
- *(2026-07-22)* **AI / Generation**: Preserved each model's reply structure through review and explicit apply actions for generated event and entity descriptions.
- *(2026-07-22)* **AI / Stability**: Added cancellation and lifecycle guards so stale generation results cannot update closed editors or interfere with application shutdown.
- *(2026-07-22)* **AI / Prompts**: Fixed duplicate version selection, event context labels, unsupported template variables, and unsafe editing or deletion of bundled assets.

### Changed

- *(2026-08-01)* **Testing / Typing**: Cleared the final 175 mypy errors,
  reaching zero errors across 315 source files, and restored all 4,325
  non-slow tests.
- *(2026-08-01)* **Testing / Typing**: Added splitter and Explorer regression
  coverage and reduced the mypy baseline from 306 to 175 errors, leaving no
  errors outside GUI and test modules.
- *(2026-08-01)* **Testing / Typing**: Cleared 196 errors from the selected
  application paths, reducing the mypy baseline from 553 to 357 errors.
- *(2026-08-01)* **Testing / Typing**: Cleared 197 errors from the selected
  application paths, reducing the mypy baseline from 750 to 553 errors.
- *(2026-08-01)* **Testing / Typing**: Added regression coverage for native
  scene access, real queued Qt invocation, and attachment statistics, reducing
  the mypy baseline from 908 to 750 errors.
- *(2026-07-31)* **Testing / Typing**: Corrected provider and import contracts,
  added focused lifecycle regressions, and reduced the mypy baseline from 940
  to 908 errors.
- *(2026-07-31)* **Testing / Typing**: Added malformed-setting and repository
  lifecycle regression coverage and reduced the mypy baseline from 955 to 940
  errors.
- *(2026-07-30)* **Testing / Typing**: Added coordinator and worker export
  regression coverage and removed 24 mypy errors from the project baseline.
- *(2026-07-28)* **Documentation / Testing**: Documented summary compression
  behavior and added regression coverage for targets, retries, legacy prompts,
  short descriptions, and immediate display refresh.
- *(2026-07-28)* **Documentation / Testing**: Documented summary management and
  added regression coverage for limits, retries, editing, deletion, legacy
  data, persistence, and undo.
- *(2026-07-28)* **Testing**: Added regression coverage for AI snapshot
  isolation, cancellation, stale jobs, failure recovery, database
  responsiveness, Qt heartbeats, and safe thread shutdown.
- *(2026-07-28)* **Testing**: Stabilized map-nesting label-overlap coverage
  by keeping the footprint fixture clear of viewport bounds.
- *(2026-07-28)* **Testing**: Added regression coverage for description-editor
  context-menu styling.
- *(2026-07-28)* **Wiki / Architecture**: Made saved descriptions the sole
  writer for system-owned mentions, stored multiple text occurrences in one
  source-target relation, and made automatic rows read-only in manual flows.
- *(2026-07-28)* **Database / Migration**: Normalized legacy relation targets,
  rebuilt derived mentions, enforced endpoint and uniqueness integrity, and
  cleared incompatible persistent undo history and artifacts.
- *(2026-07-28)* **Testing**: Added reconciliation, migration, endpoint,
  single-writer, undo, UI, CLI, and legacy-data regression coverage.
- *(2026-07-28)* **Development / CI**: Made smoke and fast regression jobs use
  cached Python 3.13 dependencies, serial execution, explicit timeouts, and
  always-uploaded test artifacts.
- *(2026-07-28)* **Testing**: Consolidated native INI-backed QSettings
  isolation and expanded lifecycle, progress, styling, and teardown coverage.
- *(2026-07-27)* **Documentation**: Replaced the mixed legacy `docs/` tree with
  canonical user, developer, and reference manuals; moved historical and
  planning material out of the Sphinx source; added deterministic schema
  checks; and made warning-free documentation builds a pull-request gate.
- *(2026-07-27)* **Testing**: Added regression coverage for deleting events and
  entities from the Explorer context menu.
- *(2026-07-27)* **Cleanup**: Removed obsolete generated research documents
  from the published documentation tree.
- *(2026-07-26)* **Testing**: Added regression coverage for marker toolbar toggling, cancellation, and normalized click placement.
- *(2026-07-26)* **Development / Workflow**: Established an incremental no-new-errors mypy ratchet with bounded cleanup thresholds for changed modules.
- *(2026-07-26)* **Testing**: Updated connection-manager fixtures for the worker and analysis coordinator contracts.
- *(2026-07-26)* **Raster / Architecture**: Generalized buffers, patches, commands, and PNG persistence for 16-bit value rasters and straight-alpha RGBA rasters.
- *(2026-07-26)* **Testing**: Added matrix coverage for raster modes and tools, tiled persistence, autosave queues, target selection, layer deletion, and Qt workflow state.
- *(2026-07-26)* **Development / Cleanup**: Normalized imports and removed unused imports across coordinators, colour pickers, spellcheck tests, and map-nesting tests.
- *(2026-07-25)* **Map / Architecture**: Moved map and raster mutations behind worker-owned services and made persisted aggregate state canonical for the UI.
- *(2026-07-25)* **Testing**: Expanded command, threading, layer, raster editing, query, snapshot, and display-mapping regression coverage.
- *(2026-07-22)* **AI / Architecture**: Reworked description generation around typed request, reply, and apply contracts with clearer provider capability handling and cloud providers disabled until configured.
- *(2026-07-22)* **Development / Workflow**: Made a dated `Unreleased` changelog update mandatory before every commit and documented pre-commit baseline metadata.
- *(2026-07-22)* **AI / Task Templates**: Replaced fantasy and length-only presets with genre-neutral create, revise, expand, and condense tasks; applying a selection is now explicit and preserves custom drafts.
- *(2026-07-22)* **Documentation**: Updated AI authoring and template-format guidance for per-world task management and explicit generation review.
- *(2026-07-22)* **Testing**: Added regression coverage for template catalogs, migration, validation, custom CRUD, independent drafts, prompt labels, and exact model replies.

## [0.18.6]

### Added

- *(2026-04-25)* **Map / Nesting**: Phase 1 — data foundation for a master/detail map hierarchy: `MAP_ROLE_MASTER` / `MAP_ROLE_DETAIL` attributes, `SetMapRoleCommand`, `RegisterDetailMapCommand`, and `RemoveDetailMapCommand`; all metadata stored in `Map.attributes` with no schema migration required.
- *(2026-04-25)* **Map / Nesting**: Phase 2 — `MapNestingService` pure-stateless transform & validation service: six-mode registration validator, `detail_to_parent` / `parent_to_detail` affine transforms (Qt y-down convention), and cycle-safe `iter_ancestors` walk.
- *(2026-04-26)* **Map / Nesting**: Phase 3 — `DetailMapFootprintItem` QGraphicsObject: translucent fill with accent-outline polygon overlay on the parent canvas, 4-corner drag-to-scale interactive edit mode, `detail_map_clicked` and `registration_changed` signals.
- *(2026-04-26)* **Map / Nesting**: Phase 4+5 — breadcrumb navigation bar (`set_breadcrumb`, `btn_parent` ↑ button) in `MapWidget`; AI-aware spatial advisory in `SpatialContextBuilder` that resolves nesting context (parent/sibling relationships) when a `nesting_service` is provided.
- *(2026-04-26)* **Map / Nesting**: Phase 6 — thumbnail previews (≤ 512 px, fill-with-crop scaling) rendered inside footprint polygons; footprint visibility toggle in the map overflow menu; smart label layout engine with greedy downward-scan de-overlap, bounds clamping, and zoom-aware scaling.
- *(2026-04-22)* **GUI / Text**: `LanguageToolWorker` async spell and grammar checker via the LanguageTool API; `LTMatch` dataclass for match representation; debounced checking with right-click suggestion menu integrated into `WikiTextEdit`; `SpellCheckSettingsDialog` for user configuration of the LanguageTool endpoint.
- *(2026-04-24)* **Raster**: Value metadata support for raster layers — `raster_image_analysis` now extracts display min/max/unit from GeoTIFF GDAL_METADATA and pixel ranges; `RasterLayerDialog` shows and allows editing of inferred value ranges for continuous layers; `CreateRasterLayerCommand` persists the metadata.
- *(2026-04-21)* **Raster**: Added brush opacity slider to the raster toolbar; opacity is applied after the cached kernel so both hard and feathered brushes share the same blend model; added `circle-half` Phosphor icon.
- *(2026-04-28)* **Import**: Added "Paste JSON" import dialog for importing world data directly from the clipboard, without a file picker.
- *(2026-04-29)* **Embedding**: `PK_SEMANTIC_COMPLETION_ENABLE_EMBEDDING` env var now controls semantic completion embedding; defaults to enabled on all platforms (was Windows-disabled by a compile-time platform check).
- *(2026-04-30)* **Embedding / Stability**: Sentence-transformers runs in an isolated child process on Windows (`SubprocessSentenceTransformersProvider`) to prevent native torch/tokenizers crashes from terminating the Qt process; a one-time preflight probe (`_ensure_semantic_probe`) disables the feature gracefully on failure.

### Fixed

- *(2026-04-30)* **Wiki / Relations**: Fixed `ProcessWikiLinksCommand` deduplication using hardcoded offset `0`; now uses `candidate.span[0]` so distinct wikilink spans to the same target each produce their own `mentions` relation instead of being falsely collapsed.
- *(2026-04-30)* **Wiki / DB**: Added DB migration to remove pre-existing duplicate `mentions` rows and create partial unique expression index `uq_mentions_src_tgt_offset` on `(source_id, target_id, start_offset)` to enforce uniqueness at the database layer.
- *(2026-04-27)* **Map / UX**: Moved breadcrumb navigation to its own row below the main toolbar to prevent label overflow on narrower windows.
- *(2026-04-22)* **Map / UX**: Close vertex editing when a path layer is hidden; previously left dangling edit handles visible on the canvas.

### Changed

- *(2026-04-30)* **Wiki / Relations**: `ProcessWikiLinksCommand` dispatch in `EditorCoordinator` is now gated behind the `SETTINGS_AUTO_RELATION_KEY` setting; wiki-link relation creation only runs when the user has explicitly opted in.
- *(2026-04-25)* **LLM**: Active-map spatial context (map name, bounds, visible markers, and registered detail maps) is now injected into entity/event generation prompts when a map is open in the editor.

### Performance

- *(2026-04-21)* **Raster / Import**: 3–30× faster large raster import via pixel subsampling before k-means colour analysis (capped at 50 K pixels; previously all pixels); a 4K image drops from ~30 s and ~3 GB peak memory to under 0.1 s and ~10 MB.

## [0.17.0]

### Added

- *(2026-04-21)* **Raster / GUI**: Redesigned paint-value selector with `NumericScrubberSpinBox` (press-drag editing), `SwatchGridWidget` for discrete rasters, `GradientScrubberWidget` for continuous rasters, and `RecentValuesStrip` for one-click access to recently-used values.
- *(2026-04-21)* **GUI**: Added reusable color-picker / scrubbing widgets: `NumericScrubberSpinBox`, `GradientScrubberWidget`, `SwatchGridWidget`, `RecentValuesStrip`, `InlineColorPickerPopover`, and `ColorHistoryService` singleton.
- *(2026-04-21)* **Raster / GUI**: Added icon-only buttons (new group, new raster layer) to the map layer panel header using theme-aware SVG icons; added `get_icon_raster_tool_button_style()` to `StyleHelper`.
- *(2026-04-21)* **Assets**: Added 17 new SVG icons to `default_assets/icons/ui_icons/` (camera, chart-bar, drop, eraser, eye, eye-slash, eyedropper, funnel, funnel-x, gradient, note-pencil, paint-brush, paint-brush-broad, paint-bucket, pencil-simple, sliders, trash).
- *(2026-04-19)* **Map**: Enhanced layer management and synchronization in `MapHandler` and related components.
- *(2026-04-17)* **Web**: Overhauled embedded FastAPI longform viewer with redesigned theme-matched UI, include/exclude tag chip filters (ANY/ALL modes), Ctrl+F text search, active TOC highlighting, WikiLink resolution, and `/api/theme` endpoint.

### Fixed

- *(2026-04-21)* **Raster / UX**: Replaced modal `QColorDialog` with non-modal `InlineColorPickerPopover` in the palette editor; synced all paint-value peers to prevent UI feedback loops.
- *(2026-04-19)* **Raster / UX**: Fixed keyboard focus not transferring to the map view on edit start, causing Space key to toggle edit mode off instead of activating hold-to-pan.
- *(2026-04-19)* **Raster / UX**: Fixed edit toggle, passive sample, gradient sub-mode sync, cursor overlay refresh after zoom, and Ctrl+scroll brush resize; fixed Escape key stopping raster editing and resetting the toggle.

### Changed

- *(2026-04-21)* **Raster / Performance**: Cached brush kernels via `@lru_cache(32)` and pre-built colorization LUTs (`_lut` field on `RasterLayerItem`), yielding ~40% speedup on stroke rendering.
- *(2026-04-21)* **Raster / Painting**: Improved brush stroke quality with evenly-spaced dab interpolation (`RASTER_DAB_SPACING_FACTOR`), cosine/gaussian/linear falloff curve options, and per-stroke strength-map blending to eliminate luminosity banding.
- *(2026-04-18)* **Map / Architecture**: Consolidated layer update flow in `MapGraphicsView`, `MapHandler`, and related mixins/models; reduced duplicated state and race conditions during layer add/remove/visibility changes.
- *(2026-04-18)* **Analysis**: Enhanced image analysis to handle unsupported PIL modes with automatic conversion fallback.

## [0.16.0]

### Added

- *(2026-04-14)* **Analysis**: Added Tier 1 Analysis Suite — `WorldValidator`, `TemporalAnalyzer`, and `IntelligenceAnalyzer` services with a tabbed `MainAnalysisPanel` hosting validation, temporal, and intelligence sub-panels; `birth` and `death` relation types added.
- *(2026-04-14)* **Analysis**: Structured lore gap suggestions as typed `ParsedLoreSuggestion` cards with HTML-escaped rendering in a `QTextBrowser`.
- *(2026-04-15)* **Analysis**: Direction-aware SPO notation in prompts, relation list, and RAG context; live direction preview in `RelationEditDialog`; confidence value now extracted from LLM responses instead of hardcoded.
- *(2026-04-11)* **GUI**: Added `EmptyStateWidget` to Event and Entity inspectors with "New Event" / "New Entity" actions wired to the editor coordinator.

### Fixed

- *(2026-04-15)* **Analysis**: Fixed DB connection leak in `RAGService._fetch_relations_for_results`; corrected direction-swap handling and confidence hardcoding in relation inference.
- *(2026-04-16)* **CI**: Resolved ruff lint failures; added Qt system libraries (`libegl1`) to CI test jobs to fix `ImportError: libEGL.so.1` on Ubuntu runners.

### Changed

- *(2026-04-16)* **Analysis / GUI**: Analysis table cells replaced with selectable `AutoHeightTextEdit` widgets; row heights auto-adjust to content; shared `make_text_cell` / `make_html_cell` factories added to `_analysis_utils`.
- *(2026-04-16)* **Architecture**: Moved analysis widgets into a dedicated `src/gui/widgets/analysis/` package for improved modularity.
- *(2026-04-12)* **GUI**: Simplified empty-state handling in entity/event editors; removed redundant `_is_loading` guards and silent exception suppression; worker now signals when a requested item has been deleted.

### Refactor

- *(2026-04-12)* **Commands**: Improved type hints (modern `dict[str, str]` syntax) and docstrings in `BaseCommand`.

### Testing

- *(2026-04-14)* **Tests**: Fixed integration test fixture drift; added `smoke`, `req`, and `bug` markers to `pytest.ini`; added `.github/workflows/tests.yml` with smoke and parallel fast-regression jobs (pytest-xdist); updated `docs/TESTING.md`.

## [0.15.0]

### Added

- **Raster / Map**: Added foundational raster layer support (Phase 1) including 16-bit PNG storage, `MapDataBuffer`, and map-layer node persistence.
- **Raster / Map**: Phase 2 raster editing tools: brush/gradient edits, stroke/paint commands with undo/redo, and a palette editor for discrete layers.
- **Raster / UX**: Probe feedback (floating probe popup), entity palette column, gradient preview, and paint-from-entity picker in the legend.
- **Raster / Features**: Coverage statistics, layer blending, orphan snapshot detection, and playhead-driven temporal snapshot system (temporal rasters).
- **Raster / Analysis**: Cross-layer spatial queries, histogram stretch, auto-colour, and brush presets.
- **Raster / Import**: K-means RGB→gradient recolour and improved import wiring; palette import/export and layer annotations (advanced gradients).

### Fixed

- **Raster / Display**: Preserve passthrough for colour (RGBA) rasters to avoid black tiles and ensure original colours are shown.
- **Raster / UX**: Make brush defaults usable for continuous mode (bump default paint value) and fix visibility/opacity/falloff issues.
- **Raster / Blend**: Resolve broken raster layer blending modes and ensure correct blend-mode persistence and undo handling.
- **Raster / Import**: Fix resampling, colour-map handling, and import-related dialog issues; add integration and GUI tests to prevent regressions.
- **Map**: Behavioral fixes for map widget and raster import, including flood-fill BFS correctness and related test coverage.
- **Raster / Labels**: Correct label precedence and pixel mapping for accurate legend and probe displays.
- **IO**: Restore raster save-to-disk path handling and correct map ID accessor for persisted layers.

### Changed

- **GUI**: Refactor raster legend into a floating overlay with smooth collapse and proper height management; improve legend and layer-panel UX.
- **Map / Query**: Use layer display names in the cross-layer spatial query UI and normalize value→entity mapping handling.
- **Code**: Move inline QSS into `StyleHelper` helpers and refactor `MapLayerPanel` construction to reduce duplication.

### Deprecated

### Added

- *(2026-03-28)* **AI**: Per-world AI audit logging — added per-world `ai_audit_log.txt` support, rating and optional comment fields in generation review dialog, and logging utilities to route audit entries to world-specific audit files.

### Fixed

- *(2026-03-28)* **Map / UI**: Reworked map toolbar and layer panel spacing; fixed destructive button styling and hover states for clearer visual hierarchy.
- *(2026-03-14 → 2026-03-12)* **Raster / Map**: Multiple raster import and map behavior fixes — improved flood-fill, marker deletion validation, non-blocking raster image analysis, resampling defaults, and passthrough handling for color rasters.

### Changed

- *(2026-03-28)* **UI**: Reorganized map toolbar into grouped button sets and moved less-frequent actions into an overflow menu to reduce clutter.
- *(2026-03-12)* **Map**: Centralized inline QSS into `StyleHelper` and refactored `MapLayerPanel` for maintainability and better theme integration.

### Refactor

- *(2026-03-14)* **Map**: Extracted heavy image-processing into `raster_import_helpers.py` and `raster_image_analysis.py` to keep UI threads responsive and improve testability.

### Testing

- *(2026-03-12 → 2026-03-14)* **Tests**: Added and expanded unit tests for raster import helpers, marker deletion validation, map layer visibility caching, animation cleanup, and editor behaviors.

### Documentation / Chore

- *(2026-03-27)* **Chore**: Recorded workspace changes and updated various local settings and test fixtures; several commits updated linting and formatting across the codebase.

## [0.14.1]
- *(2026-03-03)* **Architecture**: Implemented per-world theme persistence and GUI database initialization logic.
- *(2026-03-03)* **Architecture**: Implemented `SummaryService` injection into Event and Entity editors for status management.

### Fixed
- *(2026-03-03)* **Stability**: Hardened `SheetBuilder` with `RuntimeError` guards for height adjustments during layout reloads.
- *(2026-03-03)* **Stability**: Integrated `shiboken6.isValid` checks in `WikiTextEdit` to prevent C++ destruction crashes.
- *(2026-03-01)* **Bug**: Resolved cursor jumping issues in WikiTextEdit and inspectors by normalizing newline handling and suppressing redundant change signals.
- *(2026-03-03)* **UI**: Fixed wiki editor not rerendering on undo when the selected entity or event remains the same.

### Documentation
- *(2026-03-03)* **Docs**: Updated Copilot instructions with destruction safety patterns and Wiki Link relation settings.

## [0.14.0]

### Added
- *(2026-03-01)* **UI**: Added "Clear Formatting" (Body) button to the editor toolbar to reset block and character styles.
- *(2026-03-01)* **Architecture**: Implemented Command-Mediated Cascading Delete to prevent orphaned relations when events or entities are deleted.
- *(2026-03-01)* **UI**: Added descriptive, dynamic tooltips to the Markdown (MD) and TOC editor buttons.
- *(2026-02-28)* **UI**: Implemented editor toolbar in `WikiTextEdit` with formatting actions and view toggles.
- *(2026-02-28)* **UI**: Implemented deterministic hashed section coloring in `WikiTextEdit` to visually differentiate document sections.
- *(2026-02-28)* **UI**: Added Table of Contents (TOC) parsing and navigation to the longform editor.
- *(2026-02-27)* **UI**: Implemented type-based hashed colors in Project Explorer.
- *(2026-02-27)* **UI**: Added 'Type' as a sorting option to the Project Explorer.
- *(2026-02-27)* **Timeline**: Improved playhead stability and UX with ruler scrubbing and enhanced visual feedback.
- *(2026-02-26)* **UI**: Implemented layout saving and merging for Fast Inject templates.
- *(2026-02-25)* **UI**: Enhanced Sheet Builder with WYSIWYG drag-and-drop: semi-transparent ghost widgets, colored insertion lines, and live weight percentage overlays.
- *(2026-02-25)* **UI**: Implemented focus, scroll, and cursor position preservation across autosave reloads in all major editors.
- *(2026-02-25)* **UI**: Added drag-and-drop constraints to prevent invalid drops into Text and Divider rows in Sheet Builder.
- *(2026-02-24)* **UI**: Implemented initial Sheet Builder widget featuring layout serialization, bi-directional dirty signaling, and [!stat] callout support for Obsidian exports.
- *(2026-02-24)* **UI**: Introduced subtle visual indicators (dashed borders) for spacers within the Sheet Builder.
- *(2026-02-23)* **Map**: Implemented dynamic collision-aware label engine for label engine for both map marker labels and keyframe labels.
- *(2026-02-22)* **UI**: Implemented high-fidelity, anti-aliased pill system for `TagPill` and `DragPill` components.
- *(2026-02-22)* **Map**: Implemented themed pill backgrounds with dynamic scaling for map marker and keyframe labels.

### Changed
- *(2026-03-01)* **UI**: Improved TOC navigation to align selected headers at the top of the editor window.
- *(2026-03-01)* **UI**: Increased editor left margin and gutter spacing for improved readability.
- *(2026-02-27)* **UI**: Centralized and customized tooltip timings (1500ms delay, 5s duration) using a global `QProxyStyle`.
- *(2026-02-27)* **UI**: Renamed 'Attribute Key' to 'Attribute Name' for improved user clarity.
- *(2026-02-27)* **UI**: Refined Project Explorer tooltips and updated sort direction buttons with Phosphor icons.
- *(2026-02-25)* **UI**: Standardized Sheet Builder styling and theme adherence using project-standard `StyleHelper` utilities.
- *(2026-02-25)* **Refactor**: Extracted cursor state management into `BaseEditorMixin` to reduce redundancy across Entity and Event editors.
- *(2026-02-24)* **Architecture**: Refactored `AISearchManager` to improve separation of concerns and extracted shared tag synchronization utilities.
- *(2026-02-24)* **Docs**: Enhanced Google-style docstring coverage for `MainWindow`, `DatabaseService`, and `UIManager`.
- *(2026-02-23)* **Map**: Standardized map z-layers to ensure markers always appear above trajectory lines, regardless of layer hierarchy.
- *(2026-02-22)* **UI**: Refined UI based on review recommendations, standardizing component behavior.

### Fixed
- *(2026-03-01)* **Bug**: Fixed tag restoration in delete commands during undo operations.
- *(2026-03-01)* **Bug**: Implemented automatic wiki link validation refresh that updates link colors (red/blue) immediately upon loading entity data.
- *(2026-02-28)* **Stability**: Fixed "deleted C++ object" crash in Tag Editor.
- *(2026-02-26)* **Stability**: Resolved project-wide Ruff linting errors and implemented CI lint workflow.
- *(2026-02-26)* **UI**: Resolved accumulating vertical space issue in Fast Inject template configuration dialog.
- *(2026-02-26)* **Stability**: Added `shiboken6.isValid()` guards to prevent C++ object crashes during theme transitions.
- *(2026-02-26)* **Testing**: Resolved hangs and theme contamination in unit tests.
- *(2026-02-25)* **Stability**: Hardened History Panel with thread-safe snapshot-based signals and deferred database saves to prevent GUI crashes.
- *(2026-02-25)* **Bug**: Fixed multi-attribute resize math and resolved `AttributeError` in Sheet Builder layout logic.
- *(2026-02-25)* **Stability**: Prevented access violations by deferring reloads during active drag-and-drop operations.
- *(2026-02-25)* **Testing**: Updated stale internal tests to align with new coordinator and FACADE patterns.
- *(2026-02-24)* **Stability**: Resolved critical cross-thread segfaults during undo/redo operations and fixed `CompositeCommand` logic to prevent crashes.
- *(2026-02-24)* **Stability**: Resolved "Internal C++ object already deleted" layout crashes by removing dangerous manual item cleanup in `FlowLayout` and adding `RuntimeError` guards to editor event filters.
- *(2026-02-24)* **Bug**: Fixed `SheetBuilderWidget` attribute synchronization bugs and corrected typo in signal blocking logic.
- *(2026-02-24)* **Stability**: Suppressed persistent `QFont::setPointSize` terminal warnings.
- *(2026-02-24)* **Bug**: Corrected drag-to-resize math and suppressed aggressive autosaves during resize operations in Sheet Builder.
- *(2026-02-23)* **Bug**: Fixed ESC key not correctly cancelling Clock Mode or Draft Mode when the map view has focus.
- *(2026-02-23)* **Bug**: Repaired keyframe label collision logic, ensuring labels smoothly dodge obstacles without geometry artifacts.
- *(2026-02-22)* **Bug**: Fixed `DragPill` text eliding issues by calculating constraints dynamically on resize.
- *(2026-02-22)* **Map**: Fixed Z-order overlap where keyframe dots and labels appeared above markers. Implemented dynamic Z-inheritance so trajectory components always sit exactly underneath their parent marker.

### Refactor
- *(2026-02-24)* **Refactor**: Repaired `ProcessWikiLinksCommand` serialization to ensure undo state persistence across sessions.
- *(2026-02-23)* **Refactor**: Hardened Gizmo hit-testing and centralized ThemeManager usage within `MapGraphicsView`.
- *(2026-02-23)* **Refactor**: Removed high-frequency performance debug logging from `TimelineView`.
- *(2026-02-23)* **Docs**: Added comprehensive Google-style docstrings to pill UI components for consistency.
- *(2026-02-24)* **Testing**: Added specialized reproduction stress tests to guard against layout-related object deletion regressions.

## [0.13.5]

### Security
- *(2026-02-19)* **Security**: Updated `Pillow` to `12.1.1` to address CVE-2026-25990 (high-severity vulnerability).

### Added
- *(2026-02-19)* **UI**: Implemented actionable empty states across editors (Longform Editor, MapWidget, Timeline, Unified List).
  - Added primary action buttons (e.g., "Create Document", "New Entity") to empty states for improved onboarding.
  - Ensured consistent button styling and states across all empty state views.

### UI
- *(2026-02-19)* **UI**: Implemented MainWindow with dockable panes and layout persistence.
  - Replaced placeholder widgets with real Explorer, Timeline, Relations, and Editor widgets.
  - Enabled dock nesting, resizing, redocking, and robust splitter configuration.

### Fixed
- *(2026-02-22)* **Stability**: Fixed dock collapse regression by ensuring `reset_layout` consistently positions all docks.
- *(2026-02-21)* **Stability**: Fixed `FastInjectCoordinator` startup crash by deferring manager access.
- *(2026-02-21)* **Bug**: Enforced `DragPill` max width constraint to fix UI layout issues.
- *(2026-02-19)* **Stability**: Fixed widget resize/collapse stability and dock collapse on startup using size policies and validation delays.

### Architecture
- *(2026-02-22)* **Architecture**: Addressed code review feedback, improved comment clarity, and updated `TECHNICAL_AUDIT_REPORT.md` regarding dock collapse fix.
- *(2026-02-21)* **Architecture**: Decomposed `DatabaseService` God Object into `TagRepository` and `MetaRepository`, reducing LOC from 2509 to 1389.
- *(2026-02-21)* **Architecture**: Introduced Dependency Injection (DI) for database repositories with a backward-compatible constructor.
- *(2026-02-21)* **Architecture**: Introduced `AppCoordinator` facade to dramatically reduce `MainWindow` dependencies.

### Refactor
- *(2026-02-21)* **Refactor**: Refactored `ConnectionManager` to use declarative `_connect_batch` registry (1061 to 353 LOC).
- *(2026-02-21)* **Refactor**: Decomposed `MapWidget` into 5 focused mixins (MapDialog, Calibration, Drawing, Trajectory, Layer), reducing LOC by 48%.
- *(2026-02-21)* **Refactor**: Extracted dialog and user-input methods from `MapWidget` into a dedicated `MapDialogMixin`.
- *(2026-02-21)* **Refactor**: Extracted shared editor logic (`set_dirty`, drag-drop) into `BaseEditorMixin` and simplified data loading in editor widgets.
- *(2026-02-21)* **Refactor**: Extracted complex core methods from `GraphBuilder` and `TimelineView`.

### Testing
- *(2026-02-21)* **Testing**: Added 14 new integration tests for decomposed components (`TagRepo`, `MetaRepo`, `DI`, `AppCoordinator`).
- *(2026-02-21)* **Testing**: Fixed graph engine teardown segfaults by mocking `QWebEngineView`, resolving 16 pre-existing test failures.
- *(2026-02-21)* **Testing**: Fixed test teardown errors by adding `QTimer` mock and fixing `QMessageBox` patch targets.
- *(2026-02-21)* **Testing**: Added McCabe complexity lint rule (C901 max-complexity=15) to `pyproject.toml`.
- *(2026-02-19)* **Testing**: Standardized variable naming conventions in UI test files to address review feedback.

### Documentation
- *(2026-02-21)* **Docs**: Introduced comprehensive `TECHNICAL_AUDIT_REPORT.md` and updated it continuously alongside structural improvements.
- *(2026-02-21)* **Docs**: Enhanced docstrings for signals, `MainWindow`, and documented `MapWidget` responsibility groups.

## [0.13.0]

### Added
- *(2026-02-18)* **Map**: Added "No Fill (Transparent)" and "No Border" options to the marker right-click Visual Styling sub-menu.
  - Markers can now have a fully transparent background or no border, persisted via the undo/redo command stack.
- *(2026-02-17)* **Graph**: Added Border Color, Border Width, and Size Scale columns to Lexicon Editor node rows.
- *(2026-02-17)* **Graph**: Extended `_ColorButton` in Lexicon Editor with a "none" state (right-click to clear); displays ∅ symbol with gradient hatching.
- *(2026-02-17)* **Architecture**: Introduced `src/gui/utils/svg_utils.py` with shared SVG inline-style injection utilities (`apply_svg_inline_styles`, `apply_svg_styling_to_data_uri`, `svg_file_to_string`).
- *(2026-02-17)* **Architecture**: Introduced `VisualResolver` service and `style_constants.py` for centralized, cascading visual property resolution across map markers and graph nodes.
- *(2026-02-17)* **Map**: Map markers now respect `_v_border`, `_v_border_width`, and `_v_size_scale` visual attributes; SVG icons are re-styled on attribute change.
- *(2026-02-17)* **UI**: Added unified `IconPickerDialog` shared between Lexicon Editor and Map Editor with Default Icons, Project Icons, and Import from Disk tabs.
- *(2026-02-17)* **UI**: Added "Clear Icon" button in Lexicon Editor to remove an icon and reset entity-type shape.
- *(2026-02-17)* **Assets**: Added `AssetStore.import_icon()` for importing SVG/PNG/JPG icons while preserving the original file extension.
- *(2026-02-17)* **Graph**: Implemented immediate visual feedback in Lexicon Editor; changes to colors, shapes, and icons now update the graph in real-time.
- *(2026-02-17)* **Graph**: Implemented "Cancel" logic for Lexicon Editor to revert changes if the dialog is rejected.
- *(2026-02-17)* **Graph**: Implemented flicker-free incremental graph updates for smoother visualization changes.
- *(2026-02-17)* **Graph**: Implemented view state preservation (zoom/pan) across data reloads.
- *(2026-02-17)* **UI**: Implemented `ProjectIconCard` widget for a modern, card-based interface in the Project Icons tab.
- *(2026-02-17)* **UI**: Added theme-aware icon management with support for removing project icons and clearing lexicon icons.

### Changed
- *(2026-02-18)* **Map**: Removed redundant top-level "Change Color..." marker context menu item (superseded by "Set Fill Color..." in Visual Styling sub-menu).
- *(2026-02-17)* **Graph**: Renamed "Save" button to "OK" in Lexicon Editor to better reflect the immediate nature of the changes.
- *(2026-02-16)* **Map**: Added visual keyframe indicator (8px dot) to markers with trajectories to improve discoverability of temporal data.
- *(2026-02-16)* **UI**: Extended theme-aware `StandardCheckbox` styling to Map Hierarchy (QTreeView).
- *(2026-02-16)* **Assets**: Updated polyline icon to Phosphor 'bezier-curve' variant for better "Path" visualization.
- *(2026-02-16)* **UI**: Implemented `StandardCheckbox` widget for consistent, theme-aware checkbox styling across the application.
- *(2026-02-15)* **Import**: Implemented Markdown import defaults.
  - Automatically uses filename (without extension) as title if YAML title is missing.
  - Defaults type to `generic` (Entity) for valid Markdown files without a specified type.
  - Populates entity description with the body of the Markdown file.

### Fixed
- *(2026-02-17)* **Graph**: Fixed "Image file not found" warnings in Relationship Graph by supporting bundled default icon resolution.
- *(2026-02-17)* **Graph**: Fixed shape revert bug in Lexicon Editor where user-selected shapes were overridden by images.
- *(2026-02-17)* **Graph**: Fixed `AttributeError` in `DataCoordinator` occurring during graph lexicon handling.
- *(2026-02-17)* **Graph**: Fixed regression where edges disappeared during incremental updates by enforcing stable relationship IDs.
- *(2026-02-17)* **Graph**: Fixed entity renames not updating in the graph view by mapping internal properties to presentation layer.
- *(2026-02-16)* **UI**: Removed background color from checked checkbox indicators for cleaner look.
- *(2026-02-16)* **UI**: Fixed checkbox icon visibility issue on Windows by using robust absolute resource paths (`get_resource_path`).
- *(2026-02-15)* **Bug**: Fixed `TypeError` in Markdown import refresh caused by missing `doc_id` in `load_longform_sequence`.

### Refactor
- *(2026-02-18)* **Map**: Removed dead code from `MarkerItem` (`_render_svg_to_pixmap`, `_tint_pixmap`) and cleaned up unused imports.
- *(2026-02-17)* **Graph**: `GraphBuilder.apply_svg_styling` now delegates to shared `svg_utils` module (DRY).
- *(2026-02-16)* **Docs**: Updated `MarkerItem` docstrings to Google style guide.
- *(2026-02-16)* **UI**: Refactored `OnboardingDialog` to use `StyleHelper` and fully support application themes.
- *(2026-02-16)* **UI**: Refactored `EventEditor` and `EntityEditor` to use `StandardCheckbox`, removing redundant manual stylesheet updates.

### Changed
- *(2026-02-16)* **GUI**: Implemented "click empty space to deselect" in Project Explorer, matching behavior of Entity/Event Editor relation lists.

### Deprecated

### Cleanup

## [0.12.0]

### Added
- *(2026-02-14)* **AI**: Added "Summary Temperature" setting (0.0 - 1.0) to control generation determinism.
  - Defaults to `0.3` for consistent, factual summaries.
  - Lower values produce more deterministic output; higher values allow for more creativity.
- *(2026-02-14)* **AI**: Implemented robust settings refresh system; changes to models, providers, and prompt templates now apply immediately without requiring an application restart.
  - `SummaryService` and `LLMGenerationWidget` now listen for `ai_settings_changed` signal.
  - Automatically re-initializes provider connections when API keys or URLs change.

### Fixed
- *(2026-02-14)* **AI**: Fixed "Prompt Editor" autosave not triggering correctly in Settings Dialog.
  - Ensures custom prompt templates are persisted reliably when switching tabs or closing the dialog.
- *(2026-02-14)* **Bug**: Fixed AI summaries not loading on restart by removing `summary_service` guard in `EventEditor`.
- *(2026-02-13)* **Docs**: Corrected opacity slider docstring.

### Cleanup
- *(2026-02-14)* **Architecture**: Removed deprecated `_perform_rag_search` method and unused AI constants from `AISearchManager` to simplify codebase.

### Architecture
- *(2026-02-14)* **Refactor**: Removed backward compatibility hacks in coordinators and standardized usage of `DataCoordinator`.
- *(2026-02-14)* **Architecture**: Continued `MainWindow` decomposition (Phase 1 & 2) by removing passthrough methods and rewiring `ConnectionManager` to access `LongformManager` directly.
- *(2026-02-13)* **Architecture**: Split `map_commands.py` (1,648 lines) into focused functional modules and decomposed `MapGraphicsView` into 5 sub-components for better maintainability.
- *(2026-02-13)* **Architecture**: Decoupled `MapHandler` from dialog management and implemented service locator pattern for `MainWindow` access.
- *(2026-02-11)* **Architecture**: Completed core Hierarchical Layer System (HLS) including themed layer management panel and database persistence.

### Stability
- *(2026-02-14)* **Stability**: Forced full map marker reload on undo/redo operations to ensure visual consistency.
- *(2026-02-14)* **Testing**: Added integration tests verifying undo/redo triggers proper reload signals.
- *(2026-02-13)* **Stability**: Resolved "Layer node not found" race condition via signal-based UI snapshots in database commands.
- *(2026-02-12)* **Stability**: Fixed map visibility overwrite issues by suppressing reloads for background sync and implementing selection persistence.
- *(2026-02-12)* **Stability**: Resolved opacity slider flicker and ensured correct persistence of slider-triggered changes.
- *(2026-02-11)* **Stability**: Integrated global undo/redo support for all layer operations with automatic persistence.

### Map
- *(2026-02-12)* **Map**: Implemented "Triple-Sync" rename logic ensuring bidirectional synchronization between Map Hierarchy and Unified List.
- *(2026-02-10)* **Map**: Constrained map hovertips to a 150px maximum width for improved readability of long descriptions.

### UX
- *(2026-02-12)* **UX**: Improved map interaction by preserving viewport transform across marker and layer reload cycles.


### Added
- *(2026-02-10)* **Map**: Implemented `SnappingManager` for robust map editing.
  - Supports "Vertex Snapping" (nearest point) and "Edge Snapping" (nearest segment) using efficient BSP spatial indexing.
  - Added visual indicators for snap targets (yellow circle for vertices, blue cross for edges).
  - Added toolbar toggle button for snapping.
- *(2026-02-10)* **Map**: Implemented In-Place Entity/Event Creation from Map Selection Dialog.
  - Added `<New Entity...>` and `<New Event...>` options to `UnifiedList` dialogs.
  - Allows creating and linking new items entirely within the map workflow without leaving the context.
- *(2026-02-09)* **Map**: Implemented Line (Path) and Polygon (Region) Features.
  - Added drawing tools for creating multi-point paths (roads, rivers) and closed regions (territories).
  - Features support custom colors, hover tooltips showing area/length, and vertex editing.
  - Integrated with `MapGraphicsView` for seamless creation and manipulation.

### Fixed
- *(2026-02-10)* **UI**: Fixed visual state of toolbar toggle buttons (Snap, Draw Path).
  - Updated `StyleHelper` to correctly target `QPushButton` in toolbar styles.
  - Added specific `:checked` pseudo-state styling to clearly indicate active tools.

### Documentation
- *(2026-02-10)* **Docs**: Added comprehensive research and design notes for mapping enhancements (`docs/design_notes/mapping_enhancements/`).
  - Covered Road Network Strategy, Network Analysis (NetworkX vs QGIS), and Snapping implementation.
- *(2026-02-10)* **Docs**: Added detailed `SNAPPING_MANAGER.md` documentation explaining the spatial indexing and math.



### Added
- *(2026-02-08)* **UI**: Updated `ShortcutManager` and "Keyboard Shortcuts" dialog with new hotkeys (Navigate Link, Choose Relation Type, Deselect) and improved categorization.

### Fixed
- *(2026-02-08)* **Bug**: Fixed duplicate End Date field appearing in the Event Inspector.

### Documentation
- *(2026-02-08)* **Docs**: Completed major documentation overhaul, consolidating 62 legacy files into structured User and Technical guides (API Reference, Testing, Contributing, Architecture).

### Cleanup
- *(2026-02-08)* **Cleanup**: Removed temporary test output files and development-only documentation.

## [0.11.0]

### Added
- *(2026-02-07)* **UI**: Implemented "Drag-and-Drop Relations" from Project Explorer to Editors with visual "Drag Pill" cursor and "Relation Type Picker".
- *(2026-02-07)* **UI**: Added generic "Toast Notification" system using themed Auto-Closing Message Box for non-intrusive feedback.
- *(2026-02-07)* **Map**: Implemented "Drag Overlay" on Map Widget for improved visual feedback during drop operations.
- *(2026-02-05)* **Core**: Implemented comprehensive Global Undo/Redo System with persistence across restarts and specialized "History Panel" dock.
- *(2026-02-05)* **UI**: Added Global Keyboard Shortcuts handler via application event filter for consistent hotkey behavior.
- *(2026-02-03)* **UI**: Implemented "Virtualized List Model" (`QAbstractListModel`) for Unified List, significantly improving performance with large datasets.
- *(2026-02-03)* **UI**: Implemented Async Gallery Loading and Smart Attribute Editing for better responsiveness.

### Fixed
- *(2026-02-07)* **UI**: multiple drag-and-drop regression fixes covering selection state preservation and delayed inspection logic.
- *(2026-02-05)* **UI**: Fixed Project Explorer multi-select checkboxes not persisting correct state during filtering.
- *(2026-02-04)* **Timeline**: Prevented playhead from accidentally moving selected events during scrub operations.
- *(2026-02-03)* **Testing**: Resolved test failures by introducing compatibility layers and ensuring proper Qt library installation.

### Refactor
- *(2026-02-07)* **Refactor**: Refactored UI "Magic Numbers" into constants and fixed duplicate relation creation logic.
- *(2026-02-05)* **Architecture**: Major refactor of Command System to support serialization, timestamps, and composite commands.
- *(2026-02-03)* **Architecture**: Completed comprehensive "UX Audit" refactor including Model/View separation and async timeline layout.

### Documentation
- *(2026-02-07)* **Docs**: Added comprehensive documentation for Drag & Drop and Toast Notifications.
- *(2026-02-05)* **Docs**: Added extensive documentation and research for Undo/Redo system and Code Review reports.


## [0.10.3]

### Added
- *(2026-02-03)* **UI**: Added "Help" menu with "Keyboard Shortcuts" dialog showing all available application shortcuts.
- *(2026-02-03)* **UI**: Implemented progress dialog for JSON import operations providing real-time status feedback.
- *(2026-02-03)* **Scripts**: Added `setup_env.sh` and `validate_env.sh` for automated test environment creation and verification.

### Changed
- *(2026-02-03)* **UI**: Implemented theme-aware styling for timeline elements and "Return to Present" button.
  - Timeline active event borders now use `theme['primary']` instead of hardcoded green (#4CAF50).
  - PLAYHEAD separator uses `theme['primary']`, NOW line uses `theme['accent_secondary']`.
  - "Return to Present" button uses `theme['accent_secondary']` instead of hardcoded blue (#2196F3).
  - Timeline display automatically refreshes when theme changes.

### Fixed
- *(2026-02-03)* **Bug**: Fixed `GenerationContextProvider` reference error in `LLMGenerationWidget`.
- *(2026-02-03)* **Testing**: Resolved theme-related test failures by ensuring complete theme dictionaries in mocks.

### Documentation
- *(2026-02-03)* **Testing**: Added comprehensive test environment setup guide (`docs/TESTING_SETUP.md`) and summary (`docs/TEST_ENVIRONMENT_SUMMARY.md`).
- *(2026-02-03)* **Maintenance**: Created `docs/TODO_TRACKING.md` for technical debt management and tracking.

### Refactor
- *(2026-02-03)* **Code Quality**: Replaced magic numbers with named constants throughout the codebase.
- *(2026-02-03)* **Code Quality**: Completed extensive docstring and type hint improvements (Phase 2).
- *(2026-02-03)* **Cleanup**: Resolved pending TODO comments in `main_window.py` and `unified_list.py`.

## [0.10.2]

### Changed
- *(2026-02-02)* **Core**: Added application version number (v0.10.1) to startup log message.
- *(2026-02-02)* **GUI**: Improved relation list behavior - clicking empty space or an already-selected item now deselects it.
- *(2026-02-02)* **UI**: Added Edit and Remove buttons to Event Editor relation sections (Participants, Locations, Custom Relations) for consistency with Entity Editor.
- *(2026-02-02)* **UI**: Unified destructive button behavior across all editors - Remove buttons now disable when nothing is selected and show warning color when enabled.

### Fixed
- *(2026-02-02)* **Core**: Fixed triplicate startup logging by centralized logging initialization.
- *(2026-02-02)* **GUI**: Fixed relation reselection bug where items could not be reselected after deselection.

### Refactor
- *(2026-02-02)* **UI**: Added explicit `:disabled` state styling for destructive buttons with greyed-out appearance.
- *(2026-02-02)* **UI**: Updated `PrimaryButton` and `DestructiveButton` to dynamically update styles on theme changes.
- *(2026-02-02)* **Refactor**: Applied Sourcery suggestions to widget code - simplified conditionals, used walrus operator, and improved error handling.

## [0.10.1]

### Added
- *(2026-01-29)* **UI**: Implemented global selection sync between Timeline, List, and Inspectors.
- *(2026-01-27)* **UI**: Added "Save as Default Layout" menu action for easier workspace configuration.

### Fixed
- *(2026-02-02)* **UI**: Fixed infinite resize loop and separator rendering issues in Map Dock to prevent layout instability.
- *(2026-01-29)* **Timeline**: Fixed duration bars scaling correctly with zoom level.
- *(2026-01-29)* **Timeline**: Fixed Fit View to include full event durations and respect actual viewport size.
- *(2026-01-29)* **Timeline**: Lowered MIN_ZOOM from 0.0001 to 0.000001 to support massive timelines (up to 40M lore days).
- *(2026-01-29)* **Timeline**: Enforced single event selection (disabled Ctrl+Click multi-select).
- *(2026-01-28)* **UI**: Fixed spinbox up/down arrow visibility in Event Inspector.
- *(2026-01-27)* **Performance**: Optimized calendar calculations with year caching for >50x speedup.
- *(2026-01-27)* **Build**: Fixed gallery image path resolution in portable builds.
- *(2026-01-27)* **Build**: Resolved missing calendar icon in frozen build.

### Changed
- *(2026-01-29)* **UI**: Moved "Reset Layouts" option from "Views" menu to "Layouts" menu for better logical organization.
- *(2026-01-27)* **UI**: Renamed "Imperial Mode" theme and improved theme color control across widgets.

### Refactor
- *(2026-02-02)* **Editor**: Applied Sourcery refactoring suggestions to `LongformEditor`, including walrus operator usage and conditional logic simplifications.
- *(2026-02-02)* **Testing**: Cleaned up code review findings and fixed unit tests to ensure stability after refactoring.

## [0.10.0]

### Added
- *(2026-01-27)* **UI**: Added "Cyberpunk Mode" theme with high-contrast tech-noir neon palette.
- *(2026-01-27)* **UI**: Added "Imperial Mode" with a Grimdark crimson aesthetic.
- *(2026-01-27)* **UI**: Centralized event and entity color control in `themes.json` for all themes.
- *(2026-01-26)* **UI**: Overhauled Longform Search with Ctrl+F support, results highlighting, and dedicated search buttons.

### Changed
- *(2026-01-27)* **UI**: Refined theme-aware color retrieval logic in `StyleHelper`, `EventItem`, and `GraphWidget` to ensure 100% theme adherence.
- *(2026-01-26)* **UI**: Improved consistency of `CompactDateWidget` and `DescriptionEditor` across all themes.
- *(2026-01-26)* **Refactor**: Moved `sqlite3` import to `DatabaseWorker` to ensure proper thread affinity for SQLite objects.

### Fixed
- *(2026-01-26)* **Bug**: Fixed regression where Longform Search bar failed to toggle visibility correctly on Escape or Ctrl+F.
- *(2026-01-26)* **Stability**: Fixed theme compliance for `CompactDateWidget`, `CompactDurationWidget`, and `DescriptionEditor`.
- *(2026-01-26)* **Testing**: Mocked `QMessageBox` in `UnifiedListWidget` tests to prevent hanging in headless environments.

- *(2026-01-24)* **AI**: Implemented `RAGService` with Hybrid Search (Lexical + Semantic) for robust context retrieval.
- *(2026-01-24)* **AI**: Overhauled `LLMGenerationWidget` with RAG context preview and detailed logging.
- *(2026-01-24)* **AI**: Refactored prompt generation to 'Trinity' architecture (Persona-Task-Data).
  - Enforced strict separation and standardized ordering (System Persona + User Task + Data).
  - Renamed 'Templates' to 'Task Templates' and 'Basic Assistant Prompt' to 'Persona'.
  - Added 'Free Text / Custom' and 'Basic Assistant' options for flexible prompt construction.

### Changed
- *(2026-01-23)* **AI**: Standardized template selection logic; all templates are now globally visible across widgets.

### Refactor
- *(2026-01-25)* **Refactor**: Optimized `AISearchManager` and `LLMGenerationWidget` code quality.
  - Applied Sourcery suggestions (walrus operator, optimized if-expressions).
  - Cleaned up unused imports and variables (`rag_content`, `sqlite3`).
- *(2026-01-25)* **Refactor**: Fixed 88-char line length violations and updated docstrings in `AISearchManager`.

### Testing
- *(2026-01-24)* **Testing**: Added verification tests for RAG preview and LLM generation architectures.

## [0.9.0]

### Added
- *(2026-01-21)* **UI**: Implemented multi-selection with checkboxes in `UnifiedListWidget`.
  - Enabled ExtendedSelection mode for Ctrl+Click and Shift+Click support.
  - Checkboxes sync bidirectionally with selection state.
  - Added `items_selected` signal emitting list of `(type, id)` tuples.
  - Confirmation dialog now adapts for bulk deletion (e.g., "Delete 5 items?").
- *(2026-01-21)* **UI**: Added compact date formatting (dd.mm.yyyy - hh:mm) and sorting options to `UnifiedListWidget`.
  - Added `set_calendar_converter()` method for project-aware date display.
  - Entities sort to end when using "Lore Date" sorting (since they have no date).
- *(2026-01-20)* **Core**: Integrated fully functional `DateParser` into `src.core` (migrated from standalone module).
  - Supports natural language dates (e.g., "1st of January"), ISO formats, and relative terms.
  - Implemented `calculate_timestamp` for precise float conversions using the active `CalendarConfig`.
  - Added support for 12-hour AM/PM time parsing (e.g., "12:30 PM") and natural language backtracking.
- *(2026-01-20)* **Import**: Implemented automatic fallback to default Gregorian calendar if no active calendar config exists in DB.
- *(2026-01-20)* **Import**: Added Import Configuration UI with Source Name, Import Mode (Update, Overwrite, Skip), and Dry Run options.
- *(2026-01-20)* **Import**: Implemented robust deduplication logic using `external_id` and `source_name` metadata to prevent ambiguity.

### Fixed
- *(2026-01-21)* **UI**: Fixed stale/ghost selections persisting in `UnifiedListWidget` when items are filtered out or list is repopulated.
- *(2026-01-20)* **Import**: Prevented duplicate relations from being created on JSON re-import by checking for existing relations before creation.
- *(2026-01-20)* **Import**: Resolved "Ambiguous Entity" errors by ensuring import logic checks source metadata before name matching.

### Changed
- *(2026-01-20)* **Cleanup**: Removed temporary debug scripts (`debug_duplicates.py`, `fix_duplicates.py`).
- *(2026-01-20)* **Cleanup**: Removed legacy `src/date_parser_module` in favor of integrated `src.core.date_parser`.

### Refactor
- *(2026-01-20)* **Linting**: Fixed 31+ Ruff linting errors (type hints, unused variables) across 10 files.
- *(2026-01-20)* **Import**: Implemented Two-Pass Import Strategy (Creation -> Linking) to resolve cyclic dependencies and forward references in JSON imports.

### Documentation
- *(2026-01-20)* **Import**: Updated `docs/imports.md` with explicit instructions for LLMs to include time in date strings.

### Testing
- *(2026-01-21)* **UI**: Added `test_unified_list_features.py` with 14 tests covering multi-selection, sorting, and date formatting.
- *(2026-01-20)* **Import**: Added `test_import_forward_refs.py` and `test_import_feedback.py` covering cyclic deps and parsing warnings.

## [0.8.3]

### Added
- *(2026-01-19)* **Import**: Implemented comprehensive JSON import system with GUI and CLI support.
  - `ImportService` for parsing and persisting entities, events, and relations with transaction support.
  - `ImportPreviewDialog` for reviewing import data before committing.
  - "Import Item..." menu action in File menu.
  - CLI import command: `python -m src.app.main import --file <path>`.
  - Comprehensive documentation with JSON schemas (`docs/imports.md`).
  - Unit and integration tests for import functionality.

### Architecture
- *(2026-01-19)* **Import**: Refactored import to run entirely on worker thread.
  - Eliminates multi-connection WAL isolation issues.
  - Single DB connection architecture (worker's db_service).
  - JSON serialization for thread-safe cross-thread data transfer.
  - Auto-refresh events/entities after successful import.
- *(2026-01-19)* **Database**: Added `ensure_fresh_view()` method with WAL checkpoint for visibility guarantees.

### Performance
- *(2026-01-19)* **Timeline**: Optimized `CalendarConverter` with year caching for >50x speedup on high-year date conversions (from >5ms to <0.1ms).
- *(2026-01-19)* **Timeline**: Added performance logging to `drawForeground`, `repack_events`, `fit_all`, and `wheelEvent` for diagnostic monitoring.

### Fixed
- *(2026-01-19)* **AI Search**: Fixed entity/event selection from search results by correcting signal emission in click handlers and replacing non-existent method call with proper `UnifiedListWidget.select_item()` access.
- *(2026-01-19)* **Timeline**: Fixed Fit View to include Playhead and Current Time in the visible range.
- *(2026-01-19)* **Timeline**: Fixed panning clipping by updating Scene Rect calculation to include Playhead/Current Time positions.
- *(2026-01-19)* **Timeline**: Restored large Scene Rect buffer (50M px) for smooth infinite-feeling panning after performance bottleneck was resolved.

### Testing
- *(2026-01-19)* **Timeline**: Added `test_timeline_fit.py` with comprehensive tests for Fit View logic across different scenarios.
- *(2026-01-19)* **Import**: Added `test_import_service.py` and `test_db_isolation.py` for import validation.

## [0.8.2]

### Refactor
- *(2026-01-19)* **Coordinators**: Major architectural refactor extracting logic from `MainWindow` into dedicated coordinators: `NavigationCoordinator`, `TimeCoordinator`, and `FastInjectCoordinator`.
  - Reduced `MainWindow` size by ~1000 lines, improving maintainability.
  - Enforced public API surface (properties/methods) for better encapsulation and testability.

## [0.8.1]

### Stability
- *(2026-01-18)* **Review**: Completed extended code review of 162 files, covering Service, App, and Repository layers.
- *(2026-01-18)* **Exceptions**: Resolved 34 bare exception handlers across critical service and GUI modules to improve error visibility.
- *(2026-01-18)* **Signals**: Fixed duplicate signal definitions in `EntityEditorWidget` that could cause connection ambiguity.

### Testing
- *(2026-01-18)* **Coverage**: Increased overall test coverage from 61.2% to 70.5% (+9.3% improvement).
  - Added 9 new test files covering Core, Services, and App modules.
  - Achieved 94.7% coverage for core business logic.
- *(2026-01-18)* **Bug**: Fixed `test_shutdown.py` to properly mock `QSettings` during application termination.

### Refactor
- *(2026-01-18)* **Logging**: Replaced direct `print()` statements in `entry.py` with standard library `logging`.

### Architecture
- *(2026-01-18)* **Audit**: Validated threading (DatabaseWorker), Command patterns, and Repository abstraction layers.

## [0.8.0]

### Added
- *(2026-01-18)* **Fast Inject**: Implemented comprehensive "Fast Inject" system for rapid entity/event creation with template support.
  - Hybrid UI with dynamic sub-rows for mixed-content variables and real-time preview.
  - Core command system for undo/redo support of bulk injections.
  - Support for custom template injection and variable resolution.
- *(2026-01-18)* **Calendar**: Implemented Gregorian defaults and algorithmic leap year rules.
  - Added "Leap Rules" configuration to `CalendarConfigDialog`.
  - Updated `CalendarConverter` with weekday name calculation and 1-based month indexing.

### Refactor
- *(2026-01-18)* **Style**: Standardized docstrings across the entire codebase using `docformatter` (88 char wrap).

### Documentation
- *(2026-01-18)* **Fast Inject**: Added `docs/FAST_INJECT.md` with system architecture and usage guide.

## [0.7.0]

### Added
- *(2026-01-18)* **CLI**: Implemented comprehensive tool suite (`src.cli`) for Backups, Graph management, Obsidian export, and Trajectories.
- *(2026-01-18)* **Feature**: Implemented auto-refresh for Longform Editor to sync with external data changes.
- *(2026-01-16)* **Feature**: Implemented `GenerationReviewDialog` for reviewing and editing LLM output before acceptance.
- *(2026-01-16)* **Feature**: Enhanced `LMStudioProvider` to handle reasoning tags (e.g., `<think>`, `<scratchpad>`) and improve response parsing.
- *(2026-01-16)* **Feature**: Added template-based prompt system with few-shot examples for LLM generation.
- *(2026-01-15)* **Feature**: Implemented AST-based cursor synchronization for `WikiTextEdit` to preserve cursor position between views.
- *(2026-01-13)* **Feature**: Implemented Autocompletion for Tags, Attribute Keys, Relation Types, and Entity Types.
- *(2026-01-13)* **Feature**: Implemented Robust Autosave system with "Smart Updates" to prevent cursor jumps.

### Stability
- *(2026-01-18)* **Layout**: Hardened layout restoration to prevent crashes from off-screen windows and corrupted state.
- *(2026-01-18)* **Logging**: Added diagnostic logging to `UIManager` and `GraphWidget` for visibility troubleshooting.
- *(2026-01-15)* **Qt**: Implemented comprehensive Qt layout hardening with signal connection validation.

### Architecture
- *(2026-01-16)* **Prompts**: Implemented versioned prompt template system with YAML metadata and Jinja2-style syntax.
- *(2026-01-15)* **Initialization**: Refactored `MainWindow` initialization to three-phase pattern to eliminate race conditions.
- *(2026-01-15)* **Layout**: Implemented deferred layout restoration with three stages for improved startup performance.
- *(2026-01-15)* **Management**: Created `WidgetRegistry` class for centralized widget lifecycle management.

### Testing
- *(2026-01-18)* **CI**: Configured offscreen Qt platform for reliable headless CI testing.
- *(2026-01-17)* **Coverage**: Increased test coverage from 61% to 70% with comprehensive unit tests for core modules and services.

### UX
- *(2026-01-13)* **Graph**: Stabilized Graph View layout by enforcing a deterministic physics seed.

### Fixed
- *(2026-01-18)* **Graph**: Restored "Close" capability for Graph Dock and improved widget stability.
- *(2026-01-17)* **Testing**: Fixed Windows platform-specific test failures in `test_backup_config.py`, `test_asset_store.py`, and `test_paths.py`.
- *(2026-01-17)* **Bug**: Fixed asset store entity→entities pluralization and added `img_`/`thumb_` prefixes.
- *(2026-01-16)* **Bug**: Fixed dirty state loop in Entity Editor where editor became marked as modified immediately after loading.
- *(2026-01-15)* **Bug**: Fixed `WikiTextEdit` formatting issue where `Ctrl+4` did not reliably revert text.
- *(2026-01-14)* **Bug**: Fixed cursor jumping to start of document on autosave in `WikiTextEdit`.
- *(2026-01-13)* **Bug**: Fixed `AttributeError` in `MainWindow` when opening AI Settings dialog.
- *(2026-01-13)* **Graph**: Fixed offline graph rendering by bundling PyVis templates and local assets.

### Refactor
- *(2026-01-18)* **Linting**: Resolved project-wide Ruff linting errors and formatting issues.

### Documentation
- *(2026-01-18)* **CLI**: Added `docs/cli.rst` with auto-generated API reference.
- *(2026-01-18)* **Graph**: Added comprehensive Google-style docstrings to `GraphWidget`.
- *(2026-01-16)* **Docs**: Added comprehensive LLM integration review document (`docs/LLM_REVIEW_SUMMARY.md`).
- *(2026-01-13)* **Design**: Updated `Design.md` to reflect v0.7.0 changes and portable world model.
- *(2026-01-12)* **Docs**: Updated `README.md` for latest features.


## [0.6.0]

### Added
- *(2026-01-12)* **Feature**: Implemented complete Backup System with auto-save, retention policies, and integrity verification.
  - Added `BackupSettingsDialog` for runtime configuration of intervals and locations.
  - Integrated "Backup & Restore" menu with options for manual creation and folder access.
  - Implemented `BackupService` with automated background processing and robust error handling.
- *(2026-01-11)* **Docs**: Added comprehensive internal documentation for the Backup system.
- *(2026-01-11)* **Docs**: Standardized schema documentation and fixed missing title in `LICENSE.md`.
- *(2026-01-11)* **Feature**: Introduced Interactive Graph Visualization system.
  - Added `GraphWidget` and `GraphWebView` for PyVis/vis.js integration.
  - Added `GraphDataService` for efficient relationship graph calculation.
  - Features: Fluid zoom/pan, node dragging, and double-click navigation.
  - Integrated filtering via `GraphFilterBar` for Tags and Relationship types.
- *(2026-01-11)* **Feature**: Implemented Graph View Auto-Update. The graph now automatically refreshes relationships and nodes when data changes in the application.
- *(2026-01-11)* **Feature**: Implemented Graph Filtering Logic. The filter panel now correctly populates with available Tags and Relation Types fetched from the database.
- *(2026-01-11)* **Architecture**: Decoupled `DataHandler` from UI focus control to prevent background data refreshes from stealing user focus.
- *(2026-01-11)* **Feature**: Implemented full Theme Integration for Graph View, enabling dynamic color updates and background synchronization with the application theme.
- *(2026-01-10)* **Feature**: Implemented "Dulling Future Markers" for temporal visualization. Markers in the future relative to the playhead are now rendered with reduced opacity (0.7) and desaturated colors (80% saturation), while past/present markers remain vivid.
- *(2026-01-10)* **Architecture**: Migrated trajectory storage to OGC MF-JSON format for geospatial interoperability.
  - Added `geojson>=3.0.0` dependency.
  - Added `keyframes_to_mfjson()` and `mfjson_to_keyframes()` serialization helpers.
  - Added `_migrate_trajectories_to_mfjson()` for automatic one-time data migration on DB connect.
  - Structure: `{"type": "MovingPoint", "coordinates": [[x,y],...], "datetimes": [t,...]}`.
- *(2026-01-10)* **Feature**: Implemented persistent "Clock Mode" indicator with a toolbar status label and an interactive map overlay banner.
  - Added keyboard shortcuts: `Esc` for cancel and `Enter`/`Return` for commit.
  - Added `WaitCursor` feedback when entering Clock Mode.
- *(2026-01-10)* **Feature**: Integrated a comprehensive progressive disclosure system for map UX.
  - Added `OnboardingDialog` for first-time keyframe creation guidance.
  - Added a subtle pulsing animation (1.1x scale, 3 loops) for trajectories on first load to improve discoverability.
  - Added one-time 💡 hover hint tooltips for keyframes.
- *(2026-01-10)* **Feature**: Implemented Playhead Persistence, saving state on drag release, stop, and exit.
- *(2026-01-10)* **Feature**: Implemented "Draft Mode" (Amber) for transient marker states with visual snap-back on selection change or scrubbing.
- *(2026-01-10)* **UX**: Enhanced keyframe interaction with `SizeAllCursor` in spatial mode and optimized gizmo icon spacing for better click precision.
- *(2026-01-09)* **Feature**: Implemented keyframe deletion support and hardened trajectory precision.
  - Added context menu for keyframes with "Edit Keyframe..." and "Delete Keyframe" options.
  - Hardened trajectory calculation by rounding to 4 decimal places to prevent float precision drift.
  - Added description/tooltip support for markers, pulling from cached entity/event data.
- *(2026-01-09)* **Refactor**: Improved TimelineView code quality with 10 helper extractions and 18 new tests.
- *(2026-01-06)* **Feature**: Implemented live mouse coordinate display showing Normalized (0-1) and Real-World (Kilometers) values.
- *(2026-01-06)* **Feature**: Added GIS-style `ScaleBarPainter` with automatic unit selection and configurable map width via settings dialog.
- *(2026-01-06)* **Feature**: Added `moving_features` table for temporal map data with `ON DELETE CASCADE` on marker FK.
- *(2026-01-06)* **Architecture**: Introduced `MapCoordinateSystem` class for bidirectional normalized/scene coordinate handling.
- *(2026-01-06)* **Architecture**: Added OpenGL viewport support (`KRAKEN_NO_OPENGL` env var for software fallback).
- *(2026-01-06)* **Testing**: Added `test_map_graphics_view.py` covering coordinate signal behavior and bounds checking.
- *(2026-01-06)* **Testing**: Added ON DELETE CASCADE test for `moving_features.marker_id` FK.

### Fixed
- *(2026-01-12)* **Bug**: Fixed persistent bug where Project Explorer filter state (tags) was lost upon item save/reload.
- *(2026-01-12)* **Bug**: Fixed Project Explorer selection incorrectly jumping to random items when the selected item becomes filtered out.
- *(2026-01-12)* **Stability**: Fixed Windows-specific AppData path virtualization issues for Microsoft Store Python installations.
- *(2026-01-12)* **Stability**: Implemented `SafeRotatingFileHandler` to resolve "file in use" errors during log rotation on Windows.
- *(2026-01-11)* **Bug**: Fixed editor focus jumping to Entity Inspector when saving an Event.
- *(2026-01-11)* **Bug**: Fixed stale graph selection and camera reset issues on data reload.
- *(2026-01-11)* **Bug**: Improved Graph View focus restoration reliability after stabilization.
- *(2026-01-10)* **Bug**: Fixed onboarding dialog triggering incorrectly during keyframe movement.

### Changed
- *(2026-01-12)* **Refactor**: Encapsulated advanced filtering logic within `UnifiedListWidget`, removing dependency on `MainWindow` logic.
- *(2026-01-11)* **Refactor**: Centralized global selection logic in `MainWindow` to synchronize Project Explorer, Graph, and Editors.
- *(2026-01-10)* **UX**: Removed legacy background circle from map markers for a cleaner aesthetic.
- *(2026-01-10)* **Refactor**: Refactored `MapWidget` mode indicator to support Normal, Clock, and Draft modes.
- *(2026-01-10)* **Refactor**: Refactored `KeyframeItem` to `QGraphicsObject` for `QPropertyAnimation` support.
- *(2026-01-06)* **Refactor**: Refactored `MapWidget` toolbar to use styled `QPushButton`s for theme consistency.
- *(2026-01-06)* **Refactor**: Extracted drop handling and context menu logic in `MapGraphicsView`.
- *(2026-01-04)* **Tooling**: Improved changelog workflow to analyze full commit messages, not just headers.

## [0.5.0]

### Added
- *(2026-01-01)* **CLI**: Added `--reset-settings` flag to `launcher.py` to clear persistent application settings.
- *(2026-01-02)* **CLI**: Added `--set-default-layout` flag to save current layout as default on exit.
- *(2026-01-01)* **Architecture**: Introduced `TimelineDataProvider` protocol for decoupling `TimelineView`.
- *(2026-01-01)* **Architecture**: Added `DataHandler` signals for all data events.
- *(2026-01-02)* **Architecture**: Added `reload_markers_for_current_map` signal for auto-reloading markers.
- *(2026-01-02)* **Testing**: Added integration tests for signal wiring, timeline provider, and map/longform wiring.
- *(2026-01-04)* **Feature**: Implemented "Return to Present" button in Timeline and Entity Editor.
- *(2026-01-04)* **Feature**: Implemented text-based, card-style timeline rendering (`TimelineDisplayWidget`).
- *(2026-01-04)* **Feature**: Added collapsible LLM sections to Event/Entity editors.
- *(2026-01-03)* **Feature**: Implemented "Timeline Logic" for Temporal Relations (Staging and dynamic overrides).
- *(2026-01-03)* **UX**: Added collapsible timeline section to Entity Inspector.
- *(2026-01-04)* **Docs**: Added `docs/TEMPORAL_RELATIONS.md` guide.
- *(2026-01-04)* **Docs**: Established formal release policy and added status checking tools.

### Fixed
- *(2026-01-01)* **Stability**: Resolved startup crash caused by corrupted `QSettings`.
- *(2026-01-02)* **Stability**: Fixed startup crash caused by manager classes not inheriting from `QObject`.
- *(2026-01-02)* **Stability**: Fixed "QThread: Destroyed while thread is still running" warning on exit.
- *(2026-01-02)* **Bug**: Fixed map markers not appearing immediately after creation.
- *(2026-01-04)* **Quality**: Achieved 100% docstring coverage for timeline module.
- *(2026-01-04)* **Quality**: Resolved all ruff linting errors in timeline components.
- *(2026-01-04)* **Bug**: Fixed `check_docstrings.py` crash on single file arguments.
- *(2026-01-04)* **Testing**: Fixed integration test isolation issues (QTimer leak in MainWindow).

### Changed
- *(2026-01-02)* **Refactor**: Split `main.py` into `main_window.py` and `entry.py`.
- *(2026-01-02)* **Refactor**: Extracted `MapHandler` from MainWindow (~226 lines).
- *(2026-01-02)* **Refactor**: Extracted `TimelineGroupingManager` from MainWindow (~60 lines).
- *(2026-01-02)* **Refactor**: Extracted `AISearchManager` from MainWindow (~133 lines).
- *(2026-01-02)* **Refactor**: Extracted `LongformManager` and `WorkerManager` from MainWindow (~159 lines).
- *(2026-01-02)* **Refactor**: All manager classes now inherit from `QObject` for proper thread affinity.
- *(2026-01-01)* **Refactor**: `TimelineView` no longer accepts `DatabaseService` directly.
- *(2026-01-01)* **Refactor**: `TimelineWidget.set_db_service` removed.
- *(2026-01-01)* **Refactor**: UI components now receive data via `DataHandler` signals.
- *(2026-01-02)* **Cleanup**: Removed 20+ unused imports from `main_window.py`.

### Deprecated
- *(2026-01-01)* Direct access to `mainwindow.data_handler` from child widgets (use signals).
- *(2026-01-01)* Direct access to `mainwindow.timeline` from other widgets (use signals/ConnectionManager).
