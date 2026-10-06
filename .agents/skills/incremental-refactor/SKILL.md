---
name: incremental-refactor
description: Refactor an authorized ProjektKraken hotspot with measured strict improvement, focused behavior verification, and permanent complexity or responsibility boundaries. Use for KRT-35 child work or changes to reviewed C901 callables; not for repository-wide cleanup or unsolicited scheduled changes.
---

# Incremental refactoring

1. Inspect the worktree and authorized issue. Preserve unrelated edits. Read
   `docs/developer/contributing.md` and run
   `python -m scripts.check_complexity_policy --format json` before editing.
   Record the targeted callable ID, measured complexity, and required behavior.
2. Select one bounded responsibility seam within the authorized scope. For an
   extraction, record dependencies/responsibilities before editing and identify a
   narrow mechanical guard in the existing dependency-direction tests. File size
   alone is not a target. Preserve thread, transaction, queued delivery, undo/redo
   and authoring contracts.
3. Refactor and add focused behavior tests. Every executable edit to a reviewed
   hotspot must strictly reduce its measured complexity. Untouched debt can stay;
   extracted code must satisfy the normal Ruff limit without new suppressions.
   Consult UX contracts if presentation or interaction changes are necessary.
4. Carry the allowance ID through moves/renames by updating its locator, never its
   ID or ceiling upward. After verification, remove C901 suppressions at complexity
   15 or below and run `python -m scripts.check_complexity_policy --tighten`.
   This only lowers ceilings/removes obsolete allowances; it cannot create debt.
5. Rerun the checker against the same Git comparison revision, focused regressions,
   Ruff, relevant mypy and project policy checks. Review before/after metrics and
   boundaries. On failure, repair within scope; if that cannot be done, report the
   failure and stop rather than weakening baselines or continuing to another target.
6. Deliver measured improvement and validation evidence. Update the authorized
   Linear issue. Keep uncommitted work open. This skill does not authorize commits,
   pushes, scheduled execution, or unrelated extractions; follow explicit session
   authorization and the repository commit workflow when applicable.
