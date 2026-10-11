# Action label release gate — UI-GATE-01

Before approving a beta/release, satisfy Contract 11 in the authoritative
[UI/UX contract](../ux/authoring-contract.md). Any unreadable action or incomplete
required evidence blocks sign-off. Automated success does not override a known
failure or establish native Windows DPI behavior.

## Supported boundary

The minimum application **client area** is 1280 × 720 Qt logical pixels, excluding
window decorations. Check 1600 × 900, 360 px inspectors and narrower allocations
reachable through the workspace. Dialogs must fit within the supported client area
without increasing minimum dimensions to conceal failures. OS scales 100%, 125%,
150% and 200% are independent of text-size factors at those percentages.
Physical monitor resolution must accommodate the selected logical client area;
1280 × 720 physical pixels at 200% is not the supported minimum client area.

## Automated verification

```powershell
.venv\Scripts\python.exe -m scripts.check_action_labels --matrix quick --report-dir tmp/action-labels-quick
.venv\Scripts\python.exe -m scripts.check_action_labels --matrix fast --report-dir tmp/action-labels-fast
.venv\Scripts\python.exe -m scripts.check_action_labels --matrix full --report-dir tmp/action-labels-full
```

Routine editing defaults to `quick`: four shared/editor/Explorer surfaces,
normal and enlarged text, dark theme, default/disabled states, one simulated
scale, and screenshots only for failures. Use `--surface` to narrow a changed
surface check further. This profile is a local regression check, not release
coverage. The `fast` and explicit `full` release profiles retain their existing
coverage. `ci_fast` runs once at the end of a coherent batch rather than after
each edit.

Only one render audit may run in this checkout at a time. Child processes use
below-normal priority on Windows. Snapshot records and final reports stream to
disk, avoiding a full matrix of live Python dictionaries and a giant JSON
string in memory. Run the exhaustive matrix separately from other test suites,
preferably while the workstation is idle; do not launch one process per scale.

Each DPI factor runs in a new process. Fixtures use production widgets, application
QSS, isolated settings and synthetic snapshots. They do not execute commands,
save worlds, call models or access personal databases. Font enlargement scales
the actual application and local font-size declarations used by Qt painting and
layout. Longer labels are deterministic substitutions, not translations.
The substitution doubles vowels and adds brackets to action labels; it changes
fixture wording while retaining the original widget/actions and signals.
Wrapping prefers complete words and preserves every glyph when an individual
word exceeds the allocation. Dense commands use overflow; a separate overflow
access control can occupy a wrapped row or its own reserved tab-corner area.

The offscreen screen is configured to retain 1920 × 1080 logical pixels at each
simulated scale, so native menu geometry is not constrained by Qt's default
800 px virtual screen. Configuration uses the
[Qt 6.10.1 offscreen platform source](https://github.com/qt/qtbase/blob/v6.10.1/src/plugins/platforms/offscreen/qoffscreenintegration.cpp).

Reports identify surface/state, control path, complete wording, failure type,
required/available geometry, requested/actual logical dimensions, effective font,
device pixel ratio and physical captures. Inventory/coverage gaps remain visible.
Unknown adapters and missing required fixtures fail; they are not exceptions.
Tabs, disclosures, modes and menus need explicit coverage beyond the default state.

Style-specific adapters and negative tests verify horizontal/vertical clipping,
ancestor clipping, collisions and changed menu wording. Recoverable scroll routes
are checked with original positions restored. Data-name elision must be classified
deliberately; command labels cannot use a blanket data-value exemption.

## Reviewer checklist

- [ ] Inventory every creator-facing surface/contextual mode and resolve missing
  routes or adapters rather than silently skipping them.
- [ ] Complete action wording is direct or in a visibly labeled overflow
  destination; primary task-completion actions retain a direct route.
- [ ] Reflow preserves order, keyboard activation/focus, disabled meaning, drafts,
  caret, selection, scroll, playhead and split-pane selection.
- [ ] Normal, disabled, focused, hover/pressed and checked states retain wording
  and semantic theme roles in every shipped theme.
- [ ] Check all four native Windows OS scales and enlarged text, minimum/resized
  windows, narrow panels, longer strings, split/overflow buttons and wrapped forms.
- [ ] Retain genuine before/after failures with source/environment hashes and a
  surface/configuration coverage matrix.
- [ ] Compact alternatives have complete accessible names and explicit evidence
  and sign-off; tooltip-only meaning or unfamiliar icons do not qualify.
- [ ] Record reviewer/date, exact revision/fingerprint, actual OS/text scale,
  dimensions, captures and result. Missing evidence remains pending.

Native review is separate from offscreen/simulated captures. Geometry assertions
do not establish screen-reader conformance, per-monitor transitions or improved
task times. KRT-82 stays open until verification and the intended implementation
commit are complete. Commit, push and release are separate delivery steps.

Release preflight requires `docs/ux/evidence/krt82/native-review.json`. Pending,
missing or stale approval fails. Approved records identify the surface and OS
scale, worst-case text enlargement/long labels, reviewed modes, theme, fonts,
Windows display settings, requested/actual logical size, physical image size,
screenshot path and SHA-256. Each audited surface needs a reviewed native record
at all four OS scales. Images must exist, decode, match their hash and dimensions;
the presentation fingerprint must match the reviewed source and theme files.
