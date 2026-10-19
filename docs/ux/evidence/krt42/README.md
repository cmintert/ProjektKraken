# KRT-42 — Temporal entity mutation planning

Implementation evidence, 2026-10-19. Comparison revision:
`b20db164872dfb3cf182d5baa715fad295fffa88`.

## Responsibility boundary

Before: `TemporalEntityEditCommand.execute` resolved source destinations,
modified baseline values, applied relation payload patches, grouped dated
changes and persisted all records in one suppressed callable.

After: `TemporalEntityEditPlanner` prepares owned baseline values, separate
before/after relation snapshots and insertion-ordered dated groups from detached
inputs. Hidden metadata, field routing, masking and override removal remain
the same operations. Names are still grouped untrimmed and trimmed only when
creating an event. The planner does not validate domain payloads or allocate IDs.

The command retains fresh source and metadata comparisons, distinct relation
reads, payload validation, database writes, normalized tag updates, undo capture
and the final checkpoint. `BaseCommand` still rolls back failed results and
uncaught exceptions. Dated ordering is calculated before each insertion against
the state after previous writes. No plan is stored in command history; intent
and snapshots retain their existing serialization format and redo rebuilds a
plan. The planner's import guard permits only `copy`, `dataclasses` and `typing`
and rejects file-opening and dynamic-execution/import calls.

## Preserved authoring contract

Contracts 5/6/8/9 apply: existing manual Save/autosave and source/baseline/dated
choice routes, keyboard ownership, selection, drafts, caret and playhead remain
with their existing owners. Fresh conflict provenance, checkpoint delivery,
newer-draft preservation and one-action undo semantics remain covered by the
existing checkpoint and worker-history regressions. KRT-40 UI preparation is
unchanged. No presentation tokens, interaction rules or visual exceptions change;
this is automated behavior evidence, not new native UX acceptance.

## Verification

- Complexity policy passes before and after against the comparison revision.
  `execute` decreases **24 → 9**, its C901 suppression and allowance
  `c901-b0bb141a685d` are removed, and every other allowance is unchanged.
  Planner callables measure **1–6**; the command's snapshot/planning adapter is
  **2**. No new suppression or exception is introduced.
- Focused regressions: **136 passed**, covering pure planning, commands,
  checkpoint/acknowledgement flow and dependency direction.
- Repository-wide mypy passes across **488 source files**.
- Repository Ruff, changed-file format checks, dependency contracts, visual
  policy, Help inspection and test collection policy pass. The existing test
  inventory baseline is unchanged; new cases are discovered in `ci_fast`.
- Strict Sphinx builds successfully. Rendered HTML headings, the architecture
  cross-reference and UX evidence navigation were inspected.
- Final `pytest -m ci_fast -q`: **2,311 passed, 3 skipped**, with 4,468
  deselected. The only warning is the existing Starlette/httpx test-client
  deprecation. This is the curated suite, not a full-regression result.

New regressions check shared-owner reads, mixed baseline/relation/dated changes,
hidden metadata removal and no-ops, empty descriptions, repeated patch masking,
untrimmed ordered dated groups, detached nested values and planner rejections.
Persistence cases check same-time insertion precedence, tag synchronization,
missing/wrong-date events and invalid payloads. Injected failures after baseline,
tag, relation and event writes and during checkpoint construction leave no
partial records or successful checkpoint; unexpected exceptions also roll back.
JSON-restored mixed edits undo existing relations and newly created records,
then redo through a freshly built plan.

An AST comparison against the comparison revision also confirms unchanged fresh
state/metadata conflict checks, rejection diagnostics, payload validation, undo
and both history serializers. The moved payload patch operations have the same
AST body; only their owning module and docstring change.

The focused selection is `test_temporal_entity_edit_planner.py`,
`test_temporal_entity_edit_command.py`, `test_temporal_save_checkpoint.py` and
`test_dependency_direction.py`, all under `tests/unit/`. Run it with the project
interpreter and `QT_QPA_PLATFORM=offscreen`. Reproduce the broader checks with:

```powershell
python -m pytest -m ci_fast -q
python -m scripts.check_complexity_policy --base-ref b20db164872dfb3cf182d5baa715fad295fffa88 --format json
python -m mypy src
python -m scripts.check_visual_policy --base-ref b20db164872dfb3cf182d5baa715fad295fffa88
python -m scripts.check_help_inspection
python -m scripts.check_test_policy
python -m sphinx -E -n -W --keep-going -b html docs artifacts/krt42/html
```

Ignored local artifacts are retained under `artifacts/krt42/`: `ci-fast.txt`,
`complexity.json`, `sphinx.txt` and the rendered HTML tree. No prior evidence
directory or personal world was changed.

## Remaining candidates and limits

WikiLink resolution/reconciliation, legacy command-completion refresh planning
and import identity/action resolution remain future candidates; they are not
part of this extraction. Explicit `relation` scope is not a supported transport
scope: relation ownership is resolved from `source`. No new destination is added.
World schema, transactions, worker wiring, chronology rules and UI drafts remain
outside this change. The owner authorized a local commit on 2026-10-19, reusing
the passed verification above. Linear records the resulting commit and delivery
status. Push remains separately authorized.
