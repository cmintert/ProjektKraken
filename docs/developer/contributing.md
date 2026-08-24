# Contributing

1. Create a focused branch.
2. Make one coherent change.
3. Update tests and documentation when behaviour changes.
4. Add a dated entry to the Unreleased changelog before committing.
5. Run the relevant test, lint, type, and documentation checks. CI requires
   `python -m ruff check` and `python -m mypy src` to pass with no diagnostics.
6. Open a pull request explaining user-visible behaviour and architectural
   implications.

Use conventional commit types such as `feat`, `fix`, `docs`, `refactor`,
`test`, and `chore`.

Do not mix unrelated cleanup with a feature change. Preserve existing user
changes in a dirty working tree.
