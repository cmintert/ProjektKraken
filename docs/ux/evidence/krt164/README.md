# KRT-164 neighboring-region creation

Verification recorded on 2026-11-15 against the implementation worktree based on
`54012c44`; see Git history for the resulting commit.
This is implementation and verification evidence, not human acceptance.

## Interaction review

Contracts 2/5/6/7/8/9 apply. The visible selected-feature action and its context-menu
equivalent start the same coordinator. The source name and captured date remain
explicit. Preview, Use result and Confirm are separate local steps; Escape unwinds
preview/acceptance to drawing, then discards the draft. An active Trace subtool owns
Enter/Escape first. Space-pan and wheel zoom retain their existing ownership.

Source geometry is read-only. A retained drawing feeds `cut_region(drawing, source)`;
the worker verifies the source again inside the creation transaction. New object and
region creation are atomic and form one undo step. Picker cancellation/save failure
keeps the draft. Once saved, the new Base Geometry is independent; no existence
dates or tracking relationship are invented. All split pieces are previewed but
cannot be accepted in this single-polygon increment.

Shared secondary actions use ActionFlowLayout. The context strip uses neutral mode
roles, and RegionPreview uses selection roles. No new color exception or deliberate
interaction-contract exception is introduced. Benchmark map-mode/context tasks in
the existing 20-task catalog remain relevant; no participant timings are claimed.

## Documentation review

| Field | Record |
| --- | --- |
| Reader/task | Map author drawing a region beside an existing border |
| Primary purpose | How-to addition in `docs/user/maps.md` |
| Sources | Feature action descriptors, coordinator, retained DrawingTool proposal, guarded command and atomic composite |
| Preferred route/result | Select source → Draw neighboring region → Preview new region → Use result → Confirm/link; verify shared edge |
| Help meaning | `map.features`; `help-inspect-neighbor-region` explains source/date, local acceptance, persistence and cancellation |
| Existing destinations | Existing topic IDs, anchors and control meanings retained |
| Automated source review | Individually reviewed affected inspection fingerprints; new declarations resolve to the canonical paragraph |
| Rendered/manual/Help checks | Offline Help and strict Sphinx passed; new paragraph and six-theme 320 px previews inspected |
| Native UI component | Windows Qt plugin, software map viewport: visible menu, pointer drawing, Enter preview/use, canceled linking, nested Escape and rendered Help passed |
| Frozen geometry probe | Standalone executable passed guarded creation, serialization, undo/redo and database reopening with exact shared border |
| Full application package | Build reached COLLECT but was interrupted when collection held up local checks; full-bundle verification remains pending |
| Human prose/live Help approval | Pending |
| Independent reader observations | Pending; no completion-rate/task-time evidence claimed |

See the [documentation review form](../../../developer/documentation-review.md)
and [reader-testing protocol](../../../developer/documentation-reader-testing.md).

## Verification record

On 2026-11-15, the initial affected regression group passed 195 tests (including
the initial 31 neighbor cases), and the standard smoke suite passed 22 tests.
The final neighbor group passed 34 tests, adding existing-object placement,
atomic Event creation, duplicate protection and paused-playback coverage.
Source-race rejection also requests fresh marker/state snapshots for retry.

Ruff, repository-wide mypy (688 source files), visual/complexity/inspection
policies, reviewed test collection, generated offline Help and strict Sphinx
passed. Narrow-layout cases check drawing/preview/accepted/pending stages at
320/540/900 px in all six themes, disabled actions, keyboard focus and retained
points. Local ignored captures are under `renders/`, including
`windows-preview.png` and `windows-help.png` from the Windows component probe.
These are automated native-component observations, not human acceptance or a
full application/package interaction benchmark.

Frozen probe output is in `build/krt164-geometry-probe/result.json`; its
`neighbor_creation` and `reopened` fields are true. It deliberately excludes the
optional ML runtime and does not establish complete application packaging.
The interrupted full build's log is retained at
`build/krt164-package/pyinstaller.log`. Both directories are local build evidence.
