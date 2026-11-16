# A1 flexible hierarchy authoring

## Scope and source review

KRT-170 implements A1 of KRT-167 on `detail-maps`, based on A0 commit
`9951813e`. The canonical user task is the independent/detail maps section in
`docs/user/maps.md`; its primary purpose is how-to. Existing Help topics and
inspection destinations are retained, including the former master-action anchor,
which now explains Manage Map Hierarchy. New controls have explicit explanations.

Visible routes are **Map settings > Manage Map Hierarchy**, **Attach or change
parent**, **Make independent**, and **Edit Footprint**. The hierarchy dialog is
temporary and emits intent; it adds no persistent panel or drag/drop reparenting.
Registration is suggested until Apply. Escape cancels the innermost preview;
Enter on the canvas applies, and Enter on a focused hierarchy button invokes
that button. Opacity, reset, zoom and comparison lock are session-local helpers.

Contracts 1/2/3/4/5/6/7/8/9/11 apply: bounded disclosure, direct spatial editing,
complete labels, explicit modes, protected drafts, one-operation undo and preserved
context. The shared transition guard also protects footprint previews and waits
for the matching worker acknowledgement before continuing. Save failure retains
the preview. A changed saved hierarchy retains the preview with Apply disabled.
Cancel returns to the origin and its viewport, including edits on the current parent.

Local map content, descendants, registrations, physical calibration and authored
temporal data remain owned by their maps. A2 exact placement preservation and
B/C projections remain separate. Changing parent starts manual placement.

## Presentation review

The comparison strip uses the shared neutral mode panel, with `mode_bg`,
`mode_border` and `mode_text`. Controls use shared secondary action roles;
Apply uses the existing primary role. Breadcrumbs use neutral navigation links
and supporting captions. Touched footprint paints use semantic theme roles;
15 exact legacy color/alpha exceptions were removed for the corrected paint,
label, handle and breadcrumb paths. No new exceptions were added.

Real-widget checks cover six themes at 360/640 logical pixels, normal text and
actual 20pt text at 360 pixels. They check complete action labels, wrapped
instructions, containing bounds, disabled actions, focus/Enter activation,
comparison locking and state preservation. Captures and effective font/DPR/platform
metadata are local under `artifacts/krt170/presentation`. Offscreen software
rendering is distinct from native Windows, GPU and OS DPI evidence.

## Verification and acceptance

The feature coordinator receives frozen, explicit presentation/intent ports rather
than the whole map widget. MapHandler loses hierarchy orchestration, retains
delegating compatibility methods and composes those ports without growing its
public method API. Dependency and god-module guards pass.

Focused integration checks exercise real map widgets, the transition guard and
structural commands: attach/reparent/detach, one-command Apply, cancel, serialized
undo, viewport restoration, unreadable images, stale hierarchy, failed/mismatched
acknowledgements, descendants with legacy role mismatches and escaped names.
Existing ordered-history restart tests cover the same structural command.

Automated evidence on 16 November 2026: 193 final focused cases passed before the
last port-only extraction; 31 authoring/boundary and 96 handler/dependency checks
passed after it. The final 16-case authoring group also verifies exact marker,
trajectory, dated hole-aware region, layer-tree and image preservation through
attach/detach/undo. All 18 six-theme layout cases passed. Native Windows checks
passed 46 component cases and three enlarged-text presentation cases; metadata
records the actual platform, effective font, requested size and DPR.

The broad `ci_fast` run recorded 3,948 passed, three skipped and one Help-review
failure while the two new presentation fingerprints were being revised. The
final inventory passes; the exact failed Help coverage group, Help bundle and
authoring tests then passed 60 cases with one skip. These are corrected/segmented
results, not a clean final-state full push preflight. KRT-169's previous native
access violation did not recur in that broad run and remains a separate issue.

Final rendering review corrected the old thumbnail's screen-space rotation/crop:
the image now projects through the same affine corners as its registered outline,
including on non-square parents. A 32-point colored-image regression checks the
rendered placement against the registration service. The resulting 17 authoring
and 31 footprint cases passed together (48 total). This changes rendering only;
it adds no registration format or A2 geographic-position preservation behavior.

Ruff, repository mypy (699 source files), complexity/visual policy, test policy,
Help inspection/build and strict Sphinx pass. The native hierarchy/component
checks, offscreen layout captures and Help reader captures remain separate
evidence. The dark/narrow enlarged controls and light/narrow hierarchy captures
were inspected after correcting wrapping/reflow. The actual Help reader produced
six-theme 360/640 captures for Map settings and the new hierarchy task; dark/narrow
and light/normal content and navigation were inspected.

The KRT-170 Linear record contains final automated check results. Rendered manual
and offline Help review, native component checks and automated offscreen layout
checks are recorded separately. Human prose/live Help acceptance and a fresh
reader round remain **Pending / Not tested**. No usability improvement, full-app
native DPI matrix, package acceptance or resolution of KRT-169 is claimed.
