# KRT-48 verification — 2026-10-09

Implementation exposes **Feature actions** beside **Open in inspector** in the
native Map toolbar/overflow, and in a compact row below the Layers header.
Canvas and Layers context menus share action descriptors and existing handlers.
No new command, schema, selection persistence or global shortcut is introduced.

Final verification: **1834 passed, 2 skipped** in `ci_fast` (112.13 seconds),
with `QT_QPA_PLATFORM=offscreen` and `KRAKEN_NO_OPENGL=1`. All 43 new cases are
included; twelve production-QSS render cases own independent Qt processes.
[The successful run log](ci-fast-verified.log) is retained alongside native-crash
diagnostics. Ruff, mypy on 452 source files, visual/complexity/test policy checks,
whitespace and changed documentation links pass. The sole suite warning is an
existing Starlette/httpx deprecation.

## Contract and presentation mapping

- Contracts 1/3/4/7: border/path editing is first, historical management and
  advanced marker appearance remain reachable, and labels describe creator intent.
- Contracts 2/6/8: pointer and keyboard tree selection share the explicit-target
  policy. Feature actions works through native overflow; Enter/Escape remain owned
  by the innermost menu, dialog or active editing mode.
- Contracts 5/9: selection is independent of inspector identity; deliberate
  inspector opening and KRT-26 transition safeguards remain. Captured target,
  map, date and capability are checked before action execution, after deferred
  approval and before modal/modeless results apply. A replaced style-dialog scene
  item cannot receive an obsolete result.
- New controls use the shared secondary action role, including disabled, hover
  and focus. The selection caption inherits theme text. Native menus retain
  production theme treatment. Existing mode banners and destructive guards remain.
- Three exact legacy white-text QSS exceptions in the touched style-dialog scope
  were removed. Authored colors are icon swatches beside theme-owned button text;
  the baseline was reduced explicitly, not regenerated. Path style uses the shared
  scroll-safe choice control.

## Automated evidence

`tests/unit/test_map_feature_actions.py` uses real Qt pointer/keyboard events for
canvas and Layers selection, menu activation and narrow-toolbar submenus. Cases
cover locked, hidden, absent and out-of-date targets; raster/event capability
restrictions; changed/deleted targets; ambiguous selection; deferred approval;
same-map refresh; and stale modal/modeless acceptance.
Map replacement disables old-scene actions until the matching snapshot arrives.
Returning to a feature opens a fresh, valid modeless editor; delayed destruction
of an obsolete dialog cannot clear its replacement.

`tests/unit/test_map_feature_actions_persistence.py` creates a Location-backed
region in the empty shared database fixture, activates **Edit border at current
date** through a real menu click, drags a corner and chooses the visible Confirm
control. It executes the original geometry command against that test-owned DB,
waits for queued command acknowledgement, moves the playhead away/back, re-enters
the exact dated state, cancels with Escape, verifies undo/redo and reopens a durable
SQLite backup. Base geometry and the linked Location identity are preserved.
This is an automated component integration replay, not a live full-application
worker or human benchmark run.

Focused checks include geometry coordinators/commands, map draft transitions,
MapWidget, temporal visibility, Layers and KRT-64 inspector navigation.
Ruff, repository-wide mypy, visual/complexity/test policies and `ci_fast` are
required before delivery. Final observed results are recorded below.

The focused map/geometry/transition batch passed **213 tests**; the additional
modeless-reopening fix passed **152 focused feature/temporal/layer tests**.

## Rendered evidence

The [screenshots](screenshots/) directory contains six palettes at normal width
(1400 px) and requested narrow width (520 px; the existing splitter minimum can
make the actual widget slightly wider), with menu, focus, hover and disabled
variants. Production `src/resources/main.qss` and shared local control styles
are used. The test loads Windows Segoe UI explicitly because offscreen Qt does
not discover system fonts, and replaces the unsupported OpenGL viewport with a
software viewport. A synthetic gray map is a test fixture.

Representative captures:

- [Light normal](screenshots/light_mode-1400.png),
  [light menu](screenshots/light_mode-1400-menu.png),
  [light focus](screenshots/light_mode-1400-focus.png).
- [Dark narrow](screenshots/dark_mode-520.png),
  [dark hover](screenshots/dark_mode-1400-hover.png),
  [light narrow disabled](screenshots/light_mode-520-disabled.png).
- [Fantasy](screenshots/fantasy_mode-1400.png),
  [Imperial](screenshots/imperial_mode-520.png),
  [Cyberpunk](screenshots/cyberpunk_mode-1400.png),
  [Muted light](screenshots/muted_light_mode-520.png).

Reproduce from the project environment with `QT_QPA_PLATFORM=offscreen` and
`KRT48_EVIDENCE_DIR=docs/ux/evidence/krt48/screenshots`, running
`pytest tests/unit/test_map_feature_actions.py -k theme -q`.

The initial fontless screenshots were overwritten by these readable captures.
The popup harness initially crashed when replacing styles during popup teardown;
it now keeps production styles scoped to the test widget until destruction and
drains scheduled popup dismissal. These are harness observations, not evidence of
a production application crash. Existing header/tree styling outside the touched
selection row is not redesigned by KRT-48.

Longer combined runs subsequently hit a native Qt event-processing crash after
the new tests had passed; [the retained diagnostic](ci-fast-native-failure.log)
records one occurrence. The new tests followed immediately by raster persistence
passed 51 cases, and the existing `ci_fast` cases with the changed implementation
passed 1791/2 skipped when run separately. All twelve production-QSS render cases
now run in independent Qt child processes, remain part of `ci_fast`, and pass.
This avoids carrying their offscreen popup/style lifetime into unrelated tests;
it is not a diagnosed production crash fix.

A subsequent [crash before the new map tests](ci-fast-native-failure-before-map-tests.log)
showed that render-case isolation alone did not explain every failure. Palette
parametrization now reads plain JSON instead of constructing the Qt theme
singleton during collection. Final offscreen verification also sets the existing
`KRAKEN_NO_OPENGL=1` software-rendering option. Native-crash causality is not
claimed from these observations.

For comparison, the untouched HEAD archive at
`%TEMP%/krt48-baseline-bd9405f1ec9a4332afd01948a2fa995e` completed 1790 cases,
with two skips and one expected archive-only policy failure because `.git/HEAD`
is absent. Its `baseline-ci-fast.log` is retained there; it did not establish a
native-crash root cause. Scratch runners/logs remain outside the checkout.

## Human acceptance

The user confirmed **"Human review passed"** on 2026-10-09 after reviewing the
implementation. This records user-confirmed acceptance separately from the
automated component replay and rendered evidence above. No recording, task timing
or measured unassisted learnability result was supplied or is claimed.
Commit/push results and issue completion are recorded in Linear.
