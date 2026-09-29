# Versioned authoring UX benchmark

This benchmark measures authoring tasks in the running desktop app. The immutable
source world is the tracked `Rhine_Tribunal_UX_Benchmark_v1.krakenworld` package.
Its manifest's `022bc082` label identifies the fixture's origin, **not** the source
revision measured by a run. The package contains the calendar, map, 47 entities,
20 events, 78 relations, 19 markers, and 10 tags.

## Task contract

`tests/ux/catalog.py` is the versioned task catalog. Its KA-01–KA-20 prompts
and success conditions come from the authoring audit. KB-01–KB-10 preserve
advanced temporal capability; KC-01–KC-10 cover stress and edge conditions.
Each task starts from a separate imported copy of the package. Scenario
prerequisites live in `tests/ux/fixture.py` and have stable IDs. A failure in one
task cannot affect the starting state of another task.

The task prompt describes a worldbuilding goal. Give the operator the prompt
without naming the menu, tab, dialog, command, or intended route. Stop timing
only when the requested result is saved or the task is abandoned. For tasks
that ask the operator to inspect or explain a fact, record their answer in the
notes and compare it with the world state.

The core tasks cover creation (KA-01–05), finding and relating material
(KA-06–08), uncertain dates and chronology (KA-09–13), historical state and
provenance (KA-14–17), maps and trajectories (KA-18–19), and recovery (KA-20).
The exact prompts and success conditions are in the catalog so future runs
cannot silently reword them.

| Advanced task | Goal |
| --- | --- |
| KB-01 | Order three year-only events without exact dates. |
| KB-02 | Set a minimum gap between uncertain events. |
| KB-03 | Share one transition between two changes. |
| KB-04 | Keep conflicting date evidence distinct and visible. |
| KB-05 | Author event-relative relationship boundaries. |
| KB-06 | Preserve a one-sided unknown date. |
| KB-07 | Use a custom calendar without losing year precision. |
| KB-08 | Resolve non-commuting state changes with chronology. |
| KB-09 | Delete and recover a referenced temporal anchor. |
| KB-10 | Combine uncertain order, gap, and shared transition. |

| Stress task | Goal |
| --- | --- |
| KC-01 | Find a character among 25,000 added entities and 10,000 events. |
| KC-02 | Inspect a relation among 200,000 added relations. |
| KC-03 | Distinguish similar names. |
| KC-04 | Select and assign one of 128 tags. |
| KC-05 | Preserve a legacy exact date. |
| KC-06 | Repair imported invalid chronology. |
| KC-07 | Author with a 360-pixel-wide inspector. |
| KC-08 | Undo and redo five linked edits. |
| KC-09 | Recover navigation when a map image is missing. |
| KC-10 | Inspect a multi-leg temporal trajectory. |

## Internal walkthrough

Run the commands from the repository root with `.venv\Scripts\python.exe`.
Use a fresh run ID for each checkout state. The runner writes only under the
ignored `tmp/ux/<run-id>/` until `publish` is called.

```powershell
.venv\Scripts\python.exe -m tests.ux.runner 20260929-internal new
.venv\Scripts\python.exe -m tests.ux.runner 20260929-internal prepare --all
.venv\Scripts\python.exe -m tests.ux.runner 20260929-internal open --task KA-01
.venv\Scripts\python.exe -m tests.ux.runner 20260929-internal record --task KA-01 --completion success --correctness true --seconds 42 --actions 7 --errors 0 --backtracks 0 --help-events 0 --notes "Verified saved character and house fact."
.venv\Scripts\python.exe -m tests.ux.runner 20260929-internal report
```

`open` runs the normal source-launcher preflight after selecting task-local
Windows `QSettings`. Its settings, logs, and world discovery point to the
task's isolated runtime and world copy. Close the application after the task, inspect the copied database
or saved artifact, then record the outcome. `success` requires verified
correctness. Use `partial`, `failure`, or `blocked` with a precise note when
that is what happened. Never mark an unattempted task as blocked.

After all 40 attempts and screenshot inspection, `publish` copies the JSON,
derived CSV/Markdown, and named screenshots to `tests/ux/results/` with a
filename based on the real Git revision and dirty working-tree fingerprint.
It refuses incomplete runs. The archive remains unchanged; no runner command
opens or writes the real `worlds/` directory.

## Measurement rules

- **Completion:** success, partial, failure, or blocked; retain the attempted
  path and observed result in notes. Verify saved state after the app closes.
- **Time:** seconds from reading the prompt to saved result or abandonment.
  Record launch/loading time separately in notes if it interferes.
- **Actions:** one click, selection, keyboard shortcut, drag, confirmation, or
  continuous text entry counts as one action. Count retries and navigation.
- **Errors/backtracks/help:** record wrong actions, reversed paths, and tooltip,
  documentation, or facilitator help separately.
- **Decision/recall burden:** record meaningful choices and facts the author
  had to remember from another screen. Record internal terms encountered.
- **Relevant-control ratio:** count controls relevant to this task divided by
  visible enabled user-level controls in the captured state. Keep numerator
  and denominator in the JSON; do not turn the ratio into a master UX score.
- **Human ratings:** SEQ and NASA-TLX remain null in this internal run. A later
  participant study can add ratings without rewriting these observations.

Use `tests/ux/inspector.py` on shown Qt widgets to save a control tree and
visible/enabled count. It excludes a combo box's private line editor from
the control count. The tree is structural evidence; render inspection and
actual task attempts establish visual and interaction evidence.

Capture named PNG states from the real Windows app for Explorer, Event and
Entity Details, basic and advanced Relation, Chronology, AI Analysis Run,
World Manager, Longform, a narrow inspector, and marker/geometry/trajectory/
raster map modes. Record theme, scale, window size, and task state with the
runner's `screenshot` command. Inspect the images before publication.

## Comparison rule

Compare redesigns against the same archive hash, task catalog, scenario
version, and viewport settings. Keep completion, correctness, time, actions,
errors, discoverability, and advanced capability visible as separate measures.
Do not accept a lower control count alone as evidence of better usability.
