# KRT-93 Stage 1 — Connections overview

Implemented against `c47e07d61a6e51bfe994b5a0dacb56299942f736` after approval
of the staged Option A plan. KRT-93 remains open: this is a Stage 1
implementation, not completed vocabulary delivery or human acceptance.

## Behavior and boundaries

Both inspectors use the same grouped Qt tree, wrapping rows, search and direction/
group filters. Single-click selects; Edit, Enter or double-click refines that
UUID below the overview. References remain read-only. Event membership is no
longer treated as participation, and incoming relations use the same categories.

The existing capture/refinement commands and independent draft guard remain.
Switching tabs retains its widgets and text;
changing objects continues through the existing navigation guard. Pending saves
block competing relation operations. Refresh preserves UUID selection, filters,
group expansion and draft/caret state. Removed rows disable Apply; changed rows
retain command-level expected-snapshot protection. Incoming removal confirmation
names the opposite endpoint. Delete on a group heading never removes a relation.

Contracts 1–11 apply. Connect/Edit/navigation use shared secondary actions;
Apply uses primary; removal retains its explicit menu label and confirmation. Selection and focus use
`selection_bg`, `selection_text` and `focus_ring`; quiet disclosures and neutral
captions use shared helpers. No new UI color literals or policy exceptions were
added. The selected assertion remains identified when filters or collapse hide it.

KRT-69/71/72 are unfinished. The owner additionally requested one editable Meaning
dropdown on 2026-10-18: it reuses existing keys when suggestions are selected and
accepts unfamiliar phrases directly, with no separate Custom type control.
Readable built-in captions do not rewrite keys on opening or Notes-only edits.
Full vocabulary-backed definitions, template resolution and ambiguity warnings
remain deferred. No temporary dictionary schema, stable-key migration, graph
changes or relation-storage migration was introduced. The optional category
projection input is presentation context, not a definition-storage format.

The selection footer combines its wrapped summary with Edit. Navigation and
removal remain in the visible More actions menu; this keeps both scroll regions
usable at the minimum height even with long assertions.

The owner also requested a plain **Edit relationship** heading instead of a
disclosure on 2026-10-18. The outer editor therefore stays open until Apply or
Cancel; Timing and Advanced details retain their separate disclosures. This
supersedes the original outer-panel collapse detail without changing the draft
guard or advanced values.

The owner requested a subtle frame around the entire draft and reported a gray
scrollbar after changing themes. The draft now uses one scoped neutral
surface/border frame, and its scroll-area QSS refreshes on every theme change.
The frame contains the plain heading, fields and Apply/Cancel; it adds no mode.

## Automated evidence

Run from the repository root with the existing project environment:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m scripts.capture_connections_evidence
python -m scripts.capture_connections_evidence --height 720 --width 360 --width 380
```

The script reuses the existing synthetic gallery host, isolated QSettings,
production QSS and Segoe UI 10. It opens no world/database and executes no
commands. Outputs are retained locally in ignored `tmp/krt93/final/`:

- Entity and Event captures at 360/380/640/650/920 logical px and height 900,
  plus narrow height-720 captures, across all six shipped themes.
- Browse, focused ordinary editing, expanded Timing and disabled states. Timing captures scroll
  that region into view; they do not imply the whole advanced form fits at once.
- Geometry JSON records requested/actual dimensions, font, DPR, browser/summary
  bounds and the draft viewport height. Draft captures from development remain
  separately under `tmp/krt93/`; only `final/` represents the final layout.
- Enabled/disabled action-label measurements use the shared UI-GATE-01 adapters
  scoped to Connections, including clipping and collision checks.

The 720 px regression checks that the wrapped summary does not overlap the list,
the two splitter panels do not overlap, and the draft retains a usable scroll
viewport. Other focused regressions cover 0/5/20/100 rows, semantic fallback,
identity/direction, ten pointer selections without edits, keyboard activation,
draft choices, caret, stale/deleted relations, wheel behavior and dependency
boundaries. Existing command tests retain persistence/undo/redo coverage.

## Human review still required

Offscreen captures establish rendering at DPR 1, not native Windows scale or
text-size acceptance. Review 100/125/150/200% OS and independent text scaling,
normal/disabled/focused states, all themes, long wording, Timing, splitter sizing
and wheel handoff. Small allocations intentionally require scrolling; verify
that complete action wording and usable routes remain available.

Before production merge, compare the baseline and this implementation using
the authoring benchmark's fresh empty-world setup and assistance protocol.
Measure finding an incoming connection, explaining its direction/validity,
editing it and resuming browsing. Record time, decisions, errors, hesitation and
assistance separately from persistence checks and participant self-report.
Existing KRT-22 seeded screenshots are visual references, not comparative task
measurements. Record explicit reviewer acceptance in KRT-93; keep the issue open
until vocabulary integration, intended verification and a coherent commit exist.

## Verification results — 2026-10-18

- Final `ci_fast`: **2,151 passed, 3 skipped**. The focused relation/browser run
  after the owner refinements passed **73 tests**.
- Ruff, repository-wide mypy (482 source files), visual policy, complexity policy,
  reviewed test policy and Help inspection inventory passed. No reviewed
  complexity hotspot was touched and no allowance ceiling changed.
- Offline Help and strict Sphinx HTML builds passed. Rendered guide text and all
  seven new control-inspection excerpts were independently loaded and checked.
- **84 layout fixtures / 336 Qt captures** cover both inspectors and all six
  themes: five widths at height 900, and widths 360/380 at height 720. Shared
  enabled/disabled action-label audits reported **zero failures**; geometry checks
  reported no list/summary overlap or unexpected requested/actual size changes.
- Retained logs are `tmp/krt93-ci-fast-verified.log`,
  `tmp/krt93-framed-panel-tests.log`, `tmp/krt93-docs-final.log`, and
  `tmp/krt93-help-build-final.log`. Machine-readable capture results are in
  `tmp/krt93/final/verification-summary.json` and `geometry-720.json` /
  `geometry-900.json`. These results do not substitute for the human review above.
