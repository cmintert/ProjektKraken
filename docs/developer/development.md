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
pytest -m "not slow"
```

On Windows, set `QT_QPA_PLATFORM=offscreen` for GUI tests.

## Project layout

- `src/app`: startup, coordinators, worker lifecycle, cross-feature orchestration
- `src/gui`: presentation and user interaction
- `src/commands`: reversible mutations
- `src/services`: persistence, workers, import/export, analysis, and AI
- `src/core`: domain models and shared business concepts
- `tests`: unit, integration, GUI, and regression coverage

