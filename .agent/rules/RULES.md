---
trigger: always_on
---

# ProjektKraken Rules

## Project Overview
Desktop worldbuilding app - timeline-first lore creation with Trinity view (Editor, Timeline, Relations). Hybrid SQL+JSON data model, dark-mode dockable UI.

## Stack
- Python 3.10+, PySide6, SQLite 3.35+
- pytest/pytest-qt, ruff, mypy
- Google docstrings, Sphinx docs
- Virtual environment .venv

## Architecture
- **Core** (`src/core/`): Business logic, dataclasses, no UI deps
- **Services** (`src/services/`): Database, workers, parsers
- **Commands** (`src/commands/`): Undo/redo pattern (inherit `BaseCommand`)
- **GUI** (`src/gui/`): Dumb UI—display + emit signals only
- **App** (`src/app/`): MainWindow orchestration

## Code Standards
- **ruff** for linting/formatting (88 char lines)
- Type hints required everywhere
- Google docstrings on all public classes/methods
- `logging` module, never `print()`
- No wildcard imports, no bare `except:`
- No god classes—keep focused
- Git commits initiated by user only

## Testing
- **pytest**, TDD approach (tests first)
- **85% minimum coverage**
- In-memory SQLite (`:memory:`) for tests
- Update tests when changing code
- `tests/unit/` and `tests/integration/`

## UI/UX
- 8px grid system (spacing: 8px, margins: 16px)
- Use `StyleHelper` from `src.gui.utils.style_helper`—no hardcoded colors
- Colors from `themes.json` via `ThemeManager`
- Phosphor Icons (SVG, recolor at runtime)
- Heavy ops on `QThread`—never block UI
- Empty states: show message + CTA button
- Destructive actions: confirmation dialog, focus on Cancel

## Data
- `.kraken` SQLite files, time as float (1.0 = 1 day)
- `@dataclass` with `to_dict()`/`from_dict()`
- Wiki links: `[[Entity Name]]`

## Security
- Never hardcode secrets, API keys, or credentials
- Use environment variables or secure config for sensitive data
- Sanitize user input before database queries
- No secrets in prompts or logs
- Review all file operations for path traversal risks

## Commands
```bash
python -m src.app.main          # Run app
pytest --cov=src                # Tests
ruff check src/ tests/ --fix    # Lint
```

## Misc

- Create Knowledge Items in Memory while interacting with the codebase

