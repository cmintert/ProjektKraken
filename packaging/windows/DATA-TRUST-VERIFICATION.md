# KRT-17 data-trust verification

Source verification: **2026-10-03**, Windows, Python 3.13.14, PySide6 6.10.1.
These results cover the modified source working tree, not a packaged release.
No package was rebuilt or exercised. KRT-17 remains In Progress.

## Guided source-app walkthrough — 2026-10-03

In progress with user confirmations in the source application. This does not
complete the packaged checklist below.

- Disposable world `KRT-17 Trust Check` opened (user confirmation).
- Created `Étoile` (Character) and `Harbour` (Location), and a directed `visits`
  relation from Étoile to Harbour. The user supplied a screenshot showing both
  records/types and the graph edge with its label and direction.
- Screenshot title: `Project Kraken - v0.19.7 (Beta) - 26635540 - KRT-17 Trust Check`.
  This records the displayed build identifier; it does not establish a package
  checksum or verify the modified source contents.
- The user confirmed completing the requested descriptions and saves; description
  contents and persistence after restart have not yet been visually verified.
- A subsequent Entity Gallery screenshot visually confirms an attached image
  thumbnail and the caption `KRT-17 portrait — Étoile`. Persistence after saving
  and restarting has not yet been verified.
- Longform screenshot visually confirms two entries, Harbour before Étoile,
  with matching rendered headings. Descriptions read `A safe port. KRT-17
  baseline.` and `KRT-17 baseline — 世界. Étoile visits Harbour.`; Unicode is
  visibly intact. Exported files and restart persistence remain unverified in
  this walkthrough.
- Manual backup dialog reports success, size `260.0 KB`, filename
  `KRT-17 Trust Check_manual_20261003_184843_KRT-17 baseline before restore.kraken`,
  under the application's configured `ProjektKraken/backups/manual` directory.
  This is visual evidence of the reported outcome; backup contents have not yet
  been verified through restoration in this walkthrough.
- Next checkpoint: save a distinct newer description, then exercise restore
  cancellation before the actual restore/restart check.
- User confirms saving the newer Étoile description. A refreshed Longform
  screenshot displays `KRT-17 newer saved state — safety snapshot must preserve
  this.` while Harbour remains `A safe port. KRT-17 baseline.` and the authored
  order remains Harbour before Étoile. Restart persistence is still unverified.
- User reports restoration was applied and the app required restart. The
  post-restart Entity screenshot confirms Étoile's baseline description
  `KRT-17 baseline — 世界. Étoile visits Harbour.` is restored. This passes the
  selected record's restore/restart check. The confirmation button clicked has
  not been established, so restore cancellation remains NOT VERIFIED. Safety
  snapshot location and newer saved contents also remain NOT VERIFIED.
- User clarified clicking **Yes** in the restore confirmation. This was an
  intentional restore; cancellation remains NOT VERIFIED. User supplied the
  configured backup directory:
  `C:\Users\chris\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\Roaming\ProjektKraken\backups`.
  The safety snapshot's exact filename and contents are still unverified.
- Safety snapshot identified as
  `worlds/KRT-17 Trust Check/pre_restore_k9y_h8t9.kraken`. Read-only SQLite
  inspection through the project interpreter returned `PRAGMA integrity_check`
  = `ok`. Querying `entities` and asserting the exact Unicode name/description
  verified Étoile retains `KRT-17 newer saved state — safety snapshot must
  preserve this.`; Harbour retains its baseline description. Safety snapshot
  preservation PASSED. This inspection did not restore or modify the snapshot.
- Restore cancellation PASSED by user confirmation: selected the original
  baseline backup, clicked **No** at confirmation, and the application remained
  open and usable without a restart request.
- Next checkpoint: export Longform Markdown outside the world and inspect the
  generated document and referenced assets.
- Manual Markdown export FAILED: clicking **Create output** left the review
  visible with the literal error `'options'`. The coordinator omitted document
  options from its export request. Added two real dialog/coordinator/queued
  worker regressions (images enabled/disabled), reproduced the same error, and
  fixed request forwarding. Affected suites: 34 passed; `ci_fast`: 1,158 passed,
  2 skipped, 4,362 deselected. Ruff and the changed-coordinator mypy ratchet
  passed. Manual retest awaits an app restart.
- Manual Markdown retest PASSED: user supplied the Results screenshot reporting
  `Export complete.` at `tmp/KRT-17-exports/krt17-longform-test.md`. Read-only
  inspection confirms Harbour precedes Étoile, both headings and baseline
  descriptions are present, Unicode is intact, and both record anchors exist.
  This export contains no authored link or image reference, and no adjacent
  asset folder was observed. Link navigation, image export and external rendered
  appearance remain NOT VERIFIED by this manual sample.
- User supplied a VS Code Markdown Preview screenshot of the exported document.
  Rendered title, Harbour-before-Étoile order, both headings/descriptions and
  Unicode are visually confirmed. External Markdown viewer rendering PASSED for
  this sample; authored link navigation and inline images remain NOT VERIFIED.
- During inline-image authoring, user reports HTML mode cannot be re-entered.
  Source inspection confirms this is the existing preservation guard:
  `requires_source_mode()` matches Markdown images, and `toggle_view_mode()`
  refuses rich conversion for unsupported serializer syntax. Continue this
  export check in Markdown mode to preserve the authored image reference.
- User's Longform screenshot shows the authored Harbour link and a broken image
  icon; the source screenshot retains the expected image reference. File
  existence confirmed. Reproduced missing relative image resources because the
  browser had no world search path. Longform now sets its image search path from
  the active database directory before loading content. PNG decoded pixels and
  exact WebP resource bytes pass in a path containing spaces; the offscreen
  WebP resource remained encoded, so live WebP rendering awaits visual retest.
  Affected suites: 46 passed. Ruff and changed-module mypy passed.
  Latest `ci_fast`: 1,160 passed, 2 skipped, 4,362 deselected.
- Live Longform retest PASSED: user's subsequent screenshot displays the WebP
  image beneath Étoile's description and the Harbour link. The image displays
  at its original size, extending beyond the pane with horizontal scrolling;
  responsive image sizing has not been assessed or changed. Exported image
  copying and external link navigation remain awaiting manual verification.
- Refreshed Markdown export PASSED file inspection: authored Harbour link
  targets its existing `#item-94951e35-fb2a-45c2-bb44-bae015f4ff2a` anchor; image
  references the adjacent `krt17-longform-test.md.assets` folder. Exported WebP
  is 155,098 bytes and its SHA-256 matches the original:
  `ccac42149b3025e6a3bc5c231d83e8fde3612fc974e9bb1816fc5b86c122a31e`.
  User confirms the requested preview/link-navigation check, without a new
  preview screenshot. External image rendering is user-confirmed; copied
  bytes and paths are independently verified. Next checkpoint: Obsidian notes.
- Notes exported to `tmp/KRT-17-exports/krt-17-obsidian/lore-notes`. Read-only
  inspection confirms `Étoile.md` and `Harbour.md`, intact Unicode and baseline
  descriptions, preserved record IDs, an authored `[[Harbour]]` link and a
  `visits: [[Harbour]]` relation whose target note exists. The image uses a
  vault-relative `assets/…webp` path. External Obsidian navigation/rendering and
  sanitized/colliding names remain awaiting verification.
- User confirms notes render correctly in Obsidian and links work. External
  Obsidian rendering and navigation PASSED by user confirmation. Vault image
  SHA-256 independently matches the original
  `ccac42149b3025e6a3bc5c231d83e8fde3612fc974e9bb1816fc5b86c122a31e`.
  Next checkpoint: sanitized/colliding note names.
- Sanitized/colliding note names PASSED by user confirmation and Obsidian
  screenshot: both `Port Gate` and `Port Gate (2)` exist. The selected
  `Port Gate (2)` retains original title `Port: Gate`, description
  `KRT-17 collision A`, and `connects: Port Gate` as a clickable relation.
  User reports this works; the target's distinct collision B content is
  user-confirmed, not visible in this screenshot.
- Disposable map setup: user's screenshot shows a map background and an
  Étoile point marker, with both visible in the layer panel. Map name is outside
  the screenshot crop. Next checkpoint: create representative base and dated
  geometry, then base and dated raster states before destructive checks.
- User supplied a screenshot showing the Harbour region's base polygon beside
  the river and the Étoile point marker. This records the visible baseline shape;
  dated-state switching and deletion/undo remain awaiting verification.
- Dated geometry creation PASSED: screenshot identifies `KRT-17 Test Map` and
  Harbour's Manage Geometry States list containing `Base Geometry` and
  `Year 1, January 10, Wednesday`. The dated polygon visibly extends eastward
  compared with the recorded base shape. Switching before/at the date remains
  awaiting manual verification.
- User confirms geometry switching PASSED at `5 JAN 1` (original/base shape),
  `10 JAN 1` (altered dated shape), and `15 JAN 1` (altered shape retained).
  Next checkpoint: base raster and two visibly distinct dated raster states.
- User confirms creating `KRT-17 Trust Raster` using the requested classified
  mode, 256 × 256 resolution and default value 1, without an imported image.
  No raster screenshot or persisted metadata inspection yet; palette, entity
  references and dated states remain to be configured.
- Base raster appearance PASSED visually: screenshot shows `KRT-17 Trust
  Raster`, discrete mode, `Target: Base`, a green raster, and swatches 1
  (Étoile), 2 (Early, blue), 3 (Late, red). Value 1's entity association is
  visible through its Étoile label. Dated-state creation and fresh-restart
  persistence remain awaiting verification.
- User requests text-only confirmations for the remaining walkthrough; no
  further screenshots will be requested.
- User confirms raster states persist after restarting the source application.
  Restart persistence PASSED by user confirmation. The two exact snapshot dates
  and before/at/between/after value-selection results have not yet been recorded;
  this confirmation does not establish those boundary checks.
- User subsequently confirms post-restart temporal selection: green before the
  first state, blue at the first and between states, red at and after the second.
  Boundary selection PASSED by user confirmation. The second state's exact date
  was not supplied; first-state setup used `10 JAN 1`.
- Entity cancellation PASSED by user confirmation. Entity delete/undo FAILED:
  user reports the palette connection is lost after undo. Investigation started;
  deletion option and database versus UI outcome remain to be established.
- Source reproduction established `Delete + Remove refs` as a failing path:
  one undo restored the entity while the saved raster mapping remained empty,
  because cleanup and deletion were separate history entries. Grouped both in
  the existing CompositeCommand and added a serializable map-refresh hint so
  palette metadata reloads. Regression verifies cancellation, both deletion
  choices, one-step undo, redo and subsequent undo against saved map contents.
  Affected suites: 92 passed. Latest `ci_fast`: 1,162 passed, 2 skipped,
  4,362 deselected. Ruff and mypy for all three changed modules passed.
  Manual retest awaits restart and repair of the
  palette mapping removed by the earlier ungrouped operation.
- Live entity deletion retest PASSED by user confirmation: after restarting,
  relinking Palette value 1 to Étoile and saving, `Delete + Remove refs`
  followed by one Undo restores both Étoile and its palette connection.
  No screenshot requested. Next source checkpoints: map cancellation and
  deletion/undo, then dated raster snapshot deletion/undo.

- Live map cancellation and deletion/undo PASSED by user confirmation:
  cancelling `Delete Map...` leaves `KRT-17 Test Map` usable; confirming
  deletion followed by one Undo restores its background, Étoile marker,
  Harbour base/dated geometry, and raster states. No screenshot requested.
  Next source checkpoint: dated raster snapshot deletion/undo.

- Live dated raster snapshot deletion/undo refresh FAILED after the user's
  clarification: deleting the later red snapshot initially displays green;
  the correct temporal appearance updates only after moving the playhead.
  The earlier pass confirmation is superseded. Immediate refresh after
  deletion and undo requires a live retest; the source walkthrough is
  not complete. No screenshot requested. Packaged Windows verification and
  a commit of the intended implementation also remain closure gates.
- Source correction verified: raster metadata reloads resolve the snapshot at
  the existing playhead instead of loading the base image. File-backed regression
  checks the displayed raster buffer after late snapshot deletion, undo, redo
  and another undo, without moving the playhead. 58 focused tests passed; Ruff
  and raster-controller mypy passed. Restart the source app before the live
  retest; keep the playhead at/after the later snapshot throughout.

- Live raster snapshot deletion/undo exposed a display refresh FAILED result:
  user confirms deletion/undo works, but deleting the later red state initially
  displays green; moving the playhead then displays the correct blue fallback.
  Raster reloads always loaded the base file. Reloads now resolve the saved
  state at the existing playhead. The file-backed regression checks initial
  loading, deletion, undo, redo and subsequent undo at a fixed day 25 using
  actual raster buffer values. Focused suites: 58 passed; Ruff and changed-module
  mypy passed. Fast suite: 1,162 passed, 2 skipped, 4,362 deselected.
  Live immediate-refresh retest PASSED by user confirmation after restarting
  the source app: deleting red displays blue immediately, and one Undo displays
  red immediately, without moving the playhead. The source walkthrough is
  complete; packaged-candidate verification and the implementation commit
  remain outstanding.

## Reproduced defects and fixes

- Manual backup reported success while omitting committed WAL data. Backups
  and pre-restore safety copies now use verified SQLite snapshots.
- GUI restore replaced the database before closing the worker. Restore now
  resolves drafts, guards unfinished map edits, suspends mutations and backups,
  drains queued work, waits for cleanup acknowledgement and thread termination,
  and performs offline replacement in a separate restore task.
- Longform Markdown and note exports referenced world-local images without
  exporting them. Supported local images now travel beside the document or
  inside the vault. Failed publication preserves the previous output and assets.
- Relation links used authored names rather than sanitized export filenames.
  Filename allocation now precedes link resolution. Case-only differences and
  collisions with generated suffixes cannot overwrite another exported note.

## Source evidence

| KRT-17 scenario | Source result | Evidence |
|---|---|---|
| Backup/restore | PASS | `tests/unit/services/test_backup_wal_trust.py`: committed WAL contents, offline WAL safety snapshot, corrupt input, staging failure and replacement failure; original data and verified safety contents asserted. |
| Restore lifecycle/cancellation | PASS | `tests/unit/test_backup_restore_coordinator.py`: queued work finishes before shutdown and replacement; drafts, raster saves, trajectory/geometry sessions and invalid/unauthorized input leave the active session intact; shutdown failure never replaces the database. |
| Longform Markdown | PASS | `tests/integration/test_world_data_trust.py`: actual transfer-worker output retains authored order, headings, Unicode, internal links and image bytes outside the world; failed publish restores previous document and image folder. |
| Obsidian notes | PASS | Same integration module: readable UTF-8 files, relation targets match actual filenames, images are copied, colliding names retain every record, failed export preserves the previous vault. |
| Destructive operations | PASS | Same integration module: serialized coordinator/worker entity and map deletion with canonical undo; relations, image references/bytes, layers, markers, dated geometry and raster files restored. Real entity/map cancellation boundaries leave saved state unchanged. |
| Dated raster restart | PASS | Same integration module: close a file-backed database, reopen with fresh service and raster controller; base and two distinct dated states resolve before/at/between/after their dates; snapshot deletion undo restores metadata and exact PNG bytes. |
| Packaged Windows behavior | NOT VERIFIED | Requires the exact rebuilt candidate; source tests do not prove frozen resources, installation behavior or runtime packaging. |
| External Markdown viewer and Obsidian | PASS for the source walkthrough | Markdown Preview screenshot and subsequent user confirmation cover links/images; user confirms Obsidian rendering/navigation and colliding names. Exported image bytes independently match the original. Exact packaged-candidate exports remain unverified. |

Latest follow-up validation (entity reference deletion fix): 92 focused tests
passed; `ci_fast`: **1,162 passed, 2 skipped**, 4,362 deselected. Ruff and mypy
for the three changed modules passed. The user confirmed the live retest above.

Initial source validation completed:

- Focused suites: 182 passed before the final WAL/filename collision additions;
  the final fast suite includes all 24 new regression cases.
- `pytest -m ci_fast -q`: **1,149 passed, 2 skipped**, 4,362 deselected.
  The skipped cases are existing asset-store tests. One existing third-party
  Starlette/httpx deprecation warning was reported.
- `ruff check src/ tests/`: passed.
- `mypy src/`: passed, 420 source files. Final changed-module recheck: passed,
  12 modules.
- `scripts/check_test_policy.py`: passed; new tests retain `ci_fast` membership.

## Remaining packaged checklist

Pre-commit verification on 2026-10-03: all 76 tests across the migration,
world-data-trust, WAL backup and restore-coordinator modules passed. Repository
Ruff passed; full mypy passed for 420 source files. The complete source batch,
walkthrough record and exported samples are included in the implementation
commit; its hash is recorded in Linear. Packaged verification remains open.

Use an exact identified candidate ZIP and a disposable world. Record candidate
tag/commit, checksum, Windows build, world path, logs and screenshots alongside
the clean-VM checklist. Do not use a production world for destructive checks.

1. Create a world containing two linked lore records, an attached image, a
   Longform sequence, a map with dated geometry, and a raster with base plus two
   distinct dated states. Record its saved contents.
2. Create a manual `.kraken` backup. Change a saved record, restore the backup,
   restart, and confirm the prior record is restored. Check the safety snapshot
   location and confirm it contains the newer saved state. Remember that ordinary
   backups do not contain asset files.
3. Export Longform Markdown to a folder outside the world; open it in an external
   viewer and verify order, formatting, Unicode, internal links and images. Keep
   the neighboring `.md.assets` folder with the document.
4. Export notes to an external vault and open it in Obsidian. Follow a relation,
   inspect local images, and include sanitized/colliding note names.
5. Cancel a map deletion and an entity deletion with raster references. Then
   delete and undo representative entity/map/snapshot operations; inspect all
   restored relations, geometry, attachments and files.
6. Close and restart the package. Inspect raster values before, at, between and
   after the two snapshot dates; record visible differences.
7. Record discrepancies and retest their fixes against a rebuilt candidate.
   Close KRT-17 only after the packaged and external-viewer checks pass and the
   intended implementation is committed.
