# Testing

## Test levels

- Unit tests cover domain logic, commands, services, and focused widgets.
- Integration tests cover coordinators, worker delivery, and persistence.
- GUI tests exercise PySide6 behaviour with an application fixture.
- Regression tests preserve previously fixed workflows.

## CI suites

- `smoke` is the small safety net on GitHub pushes and pull requests.
- `ci_fast` is the locally required pre-push regression suite. It covers CLI,
  security, packaging, core/services/repositories, and selected command and
  persistence tests. Keep it deterministic and within the 12-minute CI budget.
- The full suite, including coverage, runs locally before release via
  `python -m scripts.preflight release`. Remote full regression is an optional
  manual-dispatch fallback.

### Discovery and membership policy

`tests/` is the single test root. The local push/release gate runs
`python -m scripts.check_test_policy` before executing tests. This checks
project-owned `test_*.py` files, including untracked files, for misplaced tests,
then collects the entire canonical suite and compares it with the reviewed
`tests/collection_baseline.json`. Dependencies, environments, caches, build
outputs (including `artifacts/`), and `tmp/` are excluded from the source scan.

Assign `pytest.mark.ci_fast` explicitly at module, class, or test level for
deterministic core, persistence, command, CLI, security, and bounded graph/search
regressions. Assign `smoke` explicitly for the smallest critical-path gate.
Markers travel with a test when it moves; filenames never assign membership.
New tests need a deliberate suite choice during review. Tests without either
marker run in the full-only suite by default. `unit` and `integration` describe
test level; they do not select a CI gate. `slow` describes expensive execution;
`performance` describes measurement tests. Both are independent of CI membership,
and bare/full pytest includes them. Category counts group tests by their first
directory under `tests/` (or `root` for modules directly in it); suite counts
overlap and must not be added together. Tests in `tests/performance/` validate
the measurement tooling; they are full-only functional tests, not large-world
measurements, so they do not carry the `performance` marker.

The checker fails on removed node IDs or lost `smoke`/`ci_fast` membership.
Additions are allowed and reported. Collection errors fail before comparison or
baseline writing. Ordinary focused pytest commands remain unchanged; baseline
collection ignores `PYTEST_ADDOPTS` and config `addopts` selectors.

For an intentional rename, removal, or suite change, run
`python -m scripts.check_test_policy --update` after verification. Review the
baseline diff with the test change and explain any removal; never refresh it
merely to silence a failure. Commit the baseline alongside the tests.

The pre-migration snapshot contained 5,398 tests, 18 smoke tests, and 1,018
ci_fast tests, plus 34 undiscovered graph/search cases. Migration preserves every
original node ID and critical membership. The five hidden search cases were
merged into existing coverage, retaining dictionary partial/case/missing-match
checks and adding `None` search-term coverage without duplicate tests. Required
prompt-template and alternate-theme tests now fail if bundled assets are missing
instead of silently skipping.
The resulting baseline contains 5,440 tests: 18 smoke, 1,078 ci_fast, 4,353
full-only, one slow, and zero performance-marked tests. It includes 13 new
policy regression cases and all 29 migrated graph cases.

Skips must represent a real unavailable platform capability or an inapplicable
parameter case, with a precise reason. Fix outdated expected behavior instead
of skipping it. Missing required fixtures/assets must fail on a supported CI
environment; environment-dependent symlink and optional-display skips may
remain. There are no expected-failure markers at this baseline.

For public beta approval, verify the
[Wiki Editor Beta Release Gate](wiki-editor-beta-release-gate.md) against the
release candidate and record the lifecycle test and manual-check evidence.

Do not use `not slow` as a CI suite selector. It means every test that has not
been explicitly marked slow, not a bounded fast suite.

Use fixtures from `tests/conftest.py`, including `qapp`, `db_service`, and
`init_theme_manager`.

## Local pre-push automation

See [Development Setup](development.md) to install the commit and push hooks.
The pre-push gate covers the entire `ci_fast` membership on your Windows PC;
GitHub no longer duplicates that curated suite on every push.

## Windows GUI tests

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
pytest -m smoke -q
```

## Common hazards

- `MockQSettings._storage` is shared; clear keys touched by a test.
- Debounce timers may fire during teardown.
- A text editor's viewport may be the focused widget.
- Check Qt object validity before delayed access.
- Database work must remain on the worker thread in integration tests as it
  does in production.

## Type checking

Mypy is a required repository-wide CI check. `python -m mypy src` must pass
with zero diagnostics; no error baseline or changed-files exception is used.
`pyrightconfig.json` remains available for IDE diagnostics, but Pyright is not
a separate CI gate.
