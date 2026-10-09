# Development Setup

## Environment

ProjektKraken targets Python 3.13 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python launcher.py --check
.\start-kraken.cmd
```

The cross-platform entry point is:

```text
python -m src.app.main
```

`src/app/main.py` is a compatibility shim; startup orchestration lives in
`src/app/entry.py`.

## Local-first quality checks

Install both local Git hooks once in each clone (in an activated Python 3.13
environment with the project's development and docs requirements installed):

```powershell
python -m pip install "pre-commit>=4,<5"
python -m scripts.install_hooks
```

Commits only lint and format changed Python files. An ordinary `git push`
automatically runs `python -m scripts.preflight push`. It checks all tracked
source via Ruff and mypy; dependency, complexity, semantic-visual, test-inventory
and schema contracts; strict Sphinx; then the `smoke or ci_fast` regression suite.
The native push hook reads every ref supplied by Git and requires a clean
checkout with every pushed commit matching HEAD (annotated tags are peeled).
Commit or stash local changes before pushing. Check out another branch before
pushing it; multi-ref pushes are allowed only when all updates point to HEAD.
Deletion-only pushes need no code validation. Existing clones must rerun the
installer to replace the previous pre-commit push wrapper. The installer binds
the push gate to the selected Python and preserves unrelated hooks by refusing
to overwrite them. `git push --no-verify` bypasses these local hooks and never
counts as release validation.

It blocks a failed push. It does **not** update reviewed baselines. Policy checks
compare with the merge-base of `origin/main`; if this tracking ref is unavailable,
run `git fetch origin main`, or explicitly pass `--base-ref <commit>`.

Run the identical checks manually or verify a complete release candidate:

```powershell
python -m scripts.preflight push
python -m scripts.preflight release
```

Release mode runs all pytest cases once, with coverage, in place of the fast
suite. Always additionally verify the actual Windows package, including the
packaged-world data safety acceptance tests, before publication.

GitHub checks a small `smoke` subset, repository-wide Ruff, and changed-source
policy contracts on pushes to main and pull requests. Dependency contracts have
a separate cheap job. Full mypy and full regression are manual-dispatch options,
and documentation publishes only on manual dispatch or a beta tag. Local hooks
can be bypassed: do not release or tag unverified commits.

While developing, run focused tests as needed:

```powershell
python -m pytest -m smoke -q
python -m pytest -m ci_fast -q
python -m ruff check
python -m mypy src
```


Before approving a public beta, also complete the
[Wiki Editor Beta Release Gate](wiki-editor-beta-release-gate.md). A known
authoring-continuity or link-identity failure blocks release even if CI passes.

On Windows, set `QT_QPA_PLATFORM=offscreen` for GUI tests.

## Dependency authority

`pyproject.toml` is the authority for direct dependencies and their version
constraints. Runtime packages live in `project.dependencies`; optional groups
separate `dev` (tests and quality tools), `docs`, `semantic-search` (local
sentence-transformers embeddings), and `windows-build` (PyInstaller tools).
Runtime pins preserve the tested Windows beta versions. Bleach is no longer
required; the Markdown renderer uses `nh3`.

`requirements.txt` is a generated convenience environment combining runtime,
development, documentation and local embeddings. For a smaller environment, use
`python -m pip install -r requirements/runtime.txt`, `requirements/dev.txt`, or
`requirements/docs.txt`. Add `requirements/semantic-search.txt` for local
embeddings; LM Studio embeddings do not require sentence-transformers. Install
`requirements/windows-build.txt` plus `requirements/semantic-search.txt` when
building the full Windows package outside its locked release workflow.

After editing metadata, regenerate and check the secondary pip inputs:

```text
python -m pip install "packaging>=25"
python -m scripts.check_dependencies --write
python -m scripts.check_dependencies
```

Do not edit generated requirements files independently. The generator also writes
`packaging/windows/requirements.in` from runtime, semantic-search and build groups.
The hashed `requirements.lock` remains the Windows x64 / Python 3.13 release
resolution, including transitive packages. When constraints change, regenerate
it on that platform with pip-tools:

```text
python -m pip install pip-tools
python -m piptools compile --allow-unsafe --generate-hashes --strip-extras --output-file packaging/windows/requirements.lock packaging/windows/requirements.in
python -m scripts.check_dependencies
```

The dependency CI job rejects stale projections, startup-check coverage drift,
and missing, incompatible or unhashed direct Windows pins. Startup's module-name
mapping is validated against the runtime set rather than being an independent
dependency declaration. Optional embeddings are checked when used. CI does not
re-resolve the Windows lock on Linux; release installation still verifies hashes
and the package workflow audits and smoke-tests the resolved environment.

## Project layout

- `src/app`: startup, coordinators, worker lifecycle, cross-feature orchestration
- `src/gui`: presentation and user interaction
- `src/commands`: reversible mutations
- `src/services`: persistence, workers, import/export, analysis, and AI
- `src/core`: domain models and shared business concepts
- `tests`: unit, integration, GUI, and regression coverage
