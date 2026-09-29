# Contributing

1. Make one coherent change. Use a focused branch when isolation helps; a pull
   request is optional for solo work. A verified direct commit is also fine.
2. Update tests and documentation when behaviour changes.
3. Add a dated entry to the Unreleased changelog before committing.
4. Run the relevant test, lint, type, and documentation checks. CI requires
   `python -m ruff check` and `python -m mypy src` to pass with no diagnostics.
5. Commit the change. If using a pull request, explain user-visible behaviour
   and architectural implications there.

Linear tracks substantial features, bugs, and planned investigations. Reuse an
existing `KRT` issue when one fits; small fixes and housekeeping need no issue.
For a tracked change, add `Refs KRT-<number>` to the commit footer. Mark an
implementation issue Done after the work is verified and committed.

Use conventional commit types such as `feat`, `fix`, `docs`, `refactor`,
`test`, and `chore`.

Do not mix unrelated cleanup with a feature change. Preserve existing user
changes in a dirty working tree.
