---
name: code-quality-reviewer
description: Review ProjektKraken Python and PySide6 changes for correctness, architecture, threading, Qt lifecycle safety, maintainability, typing, docstrings, and test coverage. Use when the user asks for a code-quality review, pre-commit review, diff review, architecture review, or assessment of newly written or modified code. Diagnose and report findings; do not implement fixes unless the user separately asks for changes.
---

# ProjektKraken Code Quality Review

Review the requested scope against the current repository rather than remembered or
historical observations. Treat `AGENTS.md`, current code, tests, and tool output as
authoritative.

## Establish the review scope

1. Read the applicable `AGENTS.md` instructions completely.
2. Inspect `git status`, the staged diff, and the unstaged diff. If the user names
   files or a commit range, review that exact scope instead.
3. Read enough surrounding production code and tests to evaluate behavior, not just
   formatting.
4. Do not modify files, stage changes, or commit during a review-only request.

## Review priorities

- **Correctness and data integrity:** Trace inputs, mutations, persistence, undo/redo,
  failure handling, and edge cases. Verify claims against tests or call sites.
- **Architecture:** Preserve `app -> gui -> commands -> services -> core`; keep GUI
  widgets free of business logic and SQL; route mutations through coordinators,
  commands, and the database worker.
- **Threading:** Ensure `DatabaseService` remains worker-thread owned; require queued
  Qt delivery across threads; pass serializable snapshots; preserve command overlap
  guards.
- **Command behavior:** Follow `BaseCommand`, keep services out of constructors,
  implement symmetric `execute`/`undo`, preserve persistent history, and use the tag
  helpers.
- **Qt lifecycle safety:** Check signal ownership, teardown timing, timers/debounce,
  `shiboken6.isValid`, focus behavior, and stale QObject access.
- **Maintainability:** Flag material duplication, mixed responsibilities, excessive
  complexity, misleading names, and magic values. Do not recommend abstraction when
  established structural symmetry is clearer.
- **Standards:** Verify annotations, Google-style public docstrings, import order,
  double quotes, 88-character lines, fully qualified Qt enums, theme-aware styling,
  and logging instead of `print`.
- **Tests:** Require focused regression coverage for behavior changes and reuse
  repository fixtures. Distinguish meaningful missing coverage from low-value churn.

## Verification

Run the narrowest useful checks when execution is authorized and available:

```powershell
python -m ruff check <changed Python files>
mypy <changed production modules>
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest <focused tests> -q
```

If a broad check fails because of unrelated existing debt, report that separately and
keep findings tied to the reviewed change.

## Report findings first

List findings in descending severity. For each finding include:

- severity and concise title
- exact file and line
- concrete behavior or maintenance impact
- evidence and a focused recommendation

Separate confirmed defects from questions or optional improvements. Avoid praise,
style-only noise, and speculative claims. If no actionable findings remain, state
that explicitly and mention any verification gaps.
