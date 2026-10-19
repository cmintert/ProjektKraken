# KRT-98 — Relation handling preparation

Base revision: `34d8c45326036d63cfa276779dc78d72a2297bb3`.
See [relation handling boundaries](../../../developer/relation-handling.md) for
ownership, consumer contracts and deferred work.

## Reproduce presentation evidence

From the repository root, using the project environment:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m docs.ux.evidence.krt98.render --baseline-ref 34d8c45326036d63cfa276779dc78d72a2297bb3 --width 360 --width 650
python -m docs.ux.evidence.krt98.render --width 360 --width 650
```

The renderer reuses the KRT-93 synthetic host, production QSS, isolated settings
and capture scenarios. Baseline loads the original three affected widget modules
from Git without changing the worktree. Both runs capture Entity/Event at normal
and narrow widths in all six themes: browse, focused editing, expanded Timing and
disabled state. Generated PNGs and action-label/geometry JSON stay under ignored
`artifacts/krt98/baseline/` and `artifacts/krt98/current/`, preserving KRT-93 files.
No world is opened, no command executes and no authored content is used.

## Acceptance boundary

Contracts 2/4/5/6/8/9/11 apply. Control ownership and layout stay in widgets;
existing primary/secondary/quiet, disabled, selection and focus roles remain.
This is automated presentation evidence, not native Windows DPI acceptance or
creator usability improvement. KRT-93 and future vocabulary acceptance stay open.

## Results — 2026-10-19

- **268 focused tests passed** across pure presentation/policy, dependency,
  Connections, authoring, Help inspection, commands, authored persistence,
  temporal/dialog and WikiLink reconciliation regressions. This consists of
  final groups of 114, 54 and 100 tests; it is not a full-suite result.
- Repository Ruff, full-project mypy (**487 source files**), visual policy,
  complexity policy, Help inspection inventory and test collection policy passed.
  Strict Sphinx passed; the generated consumer table, headings and deferred-work
  boundaries were inspected in HTML.
- **96/96 corresponding PNG files are byte-identical** to the baseline. All
  **24 geometry records** are identical, with **zero** enabled/disabled
  action-label failures. Representative narrow editing, disabled/Timing and
  normal browsing captures were visually inspected. The paired sets contain
  Entity/Event × six themes × two widths × four states. Existing Connections
  regressions also exercise theme changes while editing and wheel/draft ownership.
- Ruff-measured local complexity: inline preview **5 → 2**, progressive form
  **11 → 10**, form type preparation **2 → 1**. Reverse remains **2** and Apply
  **11**; extracting their shared boolean assessment does not change Ruff's count.
  New pure functions are **1–4**. All 19 reviewed C901 hotspots are untouched;
  no complexity or visual baseline changed.
- The seven affected Help source records were reviewed against the existing
  `relations.create` task and Meaning/Connection type/Reverse/Apply explanations.
  Those explanations remain accurate. Only scoped fingerprints/review notes and
  six extracted dependency reviews changed; no control explanation was rewritten.

Local generated evidence is retained at `artifacts/krt98/comparison.json`,
`artifacts/krt98/complexity.json` and the two capture directories above. Comparing
SHA-256 hashes of corresponding PNGs and equality of `geometry-900.json` reproduces
the comparison. These files are ignored artifacts, not portable checked-in proof;
the renderer and this report are retained in the repository.

This report records verification before delivery. The final commit and delivery
status are recorded in [KRT-98](https://linear.app/projektkraken/issue/KRT-98).
KRT-95 and its feature subtasks remain Backlog. No human/native scaling acceptance
is claimed.
