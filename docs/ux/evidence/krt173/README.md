# A2 geographic placement preservation

## Scope and review

KRT-173 implements A2 of KRT-167 on `detail-maps`, against baseline
`62e1a0e34a70873cfbdca5bed840c8dfd9031ff0`. The original plan's exact-or-manual
rule is retained: creator-chosen parents in a shared registered hierarchy can
preserve placement when the computed transform fits version 1. Unsupported
shear, invalid alignments and numerical instability require explicit manual
placement. No image matching, new registration format or cross-map feature
projection is introduced. Descendants, authored local content, calibration and
temporal data remain unchanged.

The feature-owned service computes over snapshots. The worker command recalculates
and compares snapshots of both ancestry chains, including the moved map, before
saving. Exact before/after snapshots support persisted Undo/Redo. The existing
coordinator and protected transition guard own dispatch; no new worker slot or
business logic in MapHandler is added.

## Authoring and presentation contracts

Visible routes remain **Map settings > Manage Map Hierarchy > Attach or change
parent** and the current map's direct action. Contracts 1/2/4/5/6/7/9/11 apply:
bounded disclosure, explicit intent, complete labels, protected drafts, reversible
operations, existing keyboard ownership and preserved canvas context. No contract
exception is introduced. Space toggles the available checkbox; Enter invokes the
focused native action and Escape cancels. Same-parent preservation disables the
no-op action; clearing the option permits manual editing.

The parent picker uses the shared wrapping checkbox and responsive native dialog
actions. Existing neutral surface/text, native focus, disabled text and action
roles come from the application theme and shared controls. No local color,
stylesheet variant or visual-policy exception is added. An unavailable option
has a plain-language reason and does not silently launch a manual preview.

## Documentation review record

| Field | Record |
| --- | --- |
| Reader and purpose | Existing map authors; how-to for changing parent or aligning manually |
| Canonical pages/release | Maps manual, Unreleased; developer architecture explanation |
| Source/dirty identity | Baseline above plus A2 files in this commit |
| Sources inspected | Parent dialog, nesting mixin, hierarchy coordinator, reparent service and command, registry and persisted history tests |
| Anchors/Help | Existing map.features and parent/action inspection targets retained; old attach heading ID retained; added help-map-parent-keep-placement |
| Save/recovery | Change parent saves one undoable operation; manual preview requires Apply; Cancel/Escape saves nothing |
| Additional discrepancy | Baseline timeline confirmation commit had a stale Help fingerprint; reviewed that handler and documented Yes/No in its existing task/excerpt |
| Human prose/live Help approval | Pending |
| Reader-round owner/cohort/date | Pending; no participant observations or completion-time claim |

The [review form](../../../developer/documentation-review.md) and
[reader protocol](../../../developer/documentation-reader-testing.md) govern
future human review. Automated checks do not establish reader performance.

## Verification

Focused regressions verify root-coordinate invariance on a grid for moved maps
and descendants, rotated and non-square registrations, aligned anisotropic
transforms, shear fallback, missing/invalid/disconnected/cyclic chains, numerical
failure, stale dependencies on either ancestry, preserved unrelated attributes,
and exact serialized history. A real worker/coordinator test closes and reopens
the database before both Undo and Redo.

Real widget tests cover parent choice, manual opt-out, disabled/no-op actions,
Space/Enter/Escape, unchanged database before dispatch, protected transitions and
unchanged selection/viewport after refresh. The six-theme matrix covers 360/640
logical pixels and actual 20pt text at 360 pixels, with complete labels and
containing bounds for both native actions. Offscreen captures are local at
`artifacts/krt173/presentation`; dark/narrow enlarged-text and light/normal
captures were inspected. Long instructions were shortened after the first
enlarged-text capture to retain both actions in bounds.

The final A2/ordered-history group passed **43 tests**; the six-theme matrix
passed **18**. The wider affected group recorded 364 passed, one skipped and
one new rollback-test setup failure. That test initially bypassed the worker's
outer retry-state transaction; it was corrected to exercise that boundary and
passes in the final 43-case group. Repository Ruff, mypy (702 source files),
complexity/visual policy, Help inspection/build and strict Sphinx pass.

The actual offline Help reader was captured in six themes at 360/640 pixels at
`artifacts/krt173/help-hierarchy`; dark/narrow task content was inspected. A real
focus-explanation shortcut regression resolves the new checkbox excerpt without
accepting or changing parent intent. Generated Help validation and search tests
pass; human live Help approval remains separate.

Test discovery policy still reports 13 obsolete test identities from the earlier
search-indexing commit `d5a5ed7a`. These are unrelated baseline removals, not A2
test failures. The inventory baseline is deliberately unchanged; no push-preflight
success is claimed.

These are automated/offscreen checks. Native full-application DPI/GPU acceptance,
human prose/live Help approval and a fresh reader round remain **Pending / Not
tested**. Earlier accepted broad tests are reused at the user's request; this
change does not claim a new full push preflight or package release.
