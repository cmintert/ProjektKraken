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

## Quality commands

```text
python -m ruff check src/ tests/
python -m mypy src/
pytest
pytest -m smoke -q
pytest -m ci_fast -q
```

CI requires both `python -m ruff check` and a clean, repository-wide
`python -m mypy src` result. `pyrightconfig.json` remains available for IDE
diagnostics, but Pyright is not a separate CI gate.

Pull requests run the smoke and `ci_fast` suites. The full, coverage-enabled
regression suite runs nightly, on beta tags, and on manual dispatch; run that
workflow before approving a release.

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
