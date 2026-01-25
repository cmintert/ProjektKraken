---
**Project:** ProjektKraken  
**Document:** Development Guide  
**Last Updated:** 2026-01-25  
---

# Development Guide

This guide covers setting up a development environment for ProjektKraken and understanding the development workflow.

## Environment Setup

### Prerequisites

- **Python 3.11+** (required)
- **Git** (for version control)
- **Virtual environment** (recommended)

### Platform-Specific Setup

#### Windows

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

#### Linux / macOS

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

## Dependencies

All project dependencies are managed in `requirements.txt`:

**Core Dependencies:**
- `PySide6` - Qt 6 GUI framework
- `fastapi` - Web framework for embedded server
- `uvicorn` - ASGI server for FastAPI
- `pytest` - Testing framework
- `pytest-qt` - Qt testing support
- `pytest-cov` - Code coverage
- `ruff` - Linter and formatter
- `pyvis` - Graph visualization
- `networkx` - Graph algorithms
- `python-dotenv` - Environment configuration

**Optional Dependencies:**
- `openai` - OpenAI API client
- `anthropic` - Anthropic API client
- `google-cloud-aiplatform` - Google Vertex AI client
- `sentence-transformers` - Local embeddings

## Environment Setup

This project uses a local virtual environment (`.venv`) on Windows.

## Pre-commit Hooks

We use `pre-commit` to ensure code quality with `ruff` and `pytest`.

### Configuration Rules

When modifying `.pre-commit-config.yaml`, always define hooks using `entry: python -m <module>`.

**Correct:**
```yaml
- id: ruff-check
  entry: python -m ruff check --fix
```

**Incorrect:**
```yaml
- id: ruff-check
  entry: ruff check --fix
```

**Reason:**
On Windows, executing the module via `python -m` ensures that the command runs within the correct Python environment (the active `.venv`), resolving imports and paths correctly. Direct executable calls may fail or pick up the wrong environment.

### Running Hooks

The hooks run automatically on `git commit`. To run them manually:

1. Activate the virtual environment:
   ```bash
   # Linux/macOS
   source .venv/bin/activate
   
   # Windows PowerShell
   .\.venv\Scripts\activate.ps1
   ```

2. Run the hooks:
   ```bash
   pre-commit run --all-files
   ```

## Development Workflow

### Running the Application

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows

# Run the GUI application
python launcher.py

# Or run directly
python -m src.app.main
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_events.py

# Run integration tests only
pytest tests/integration/

# Run with verbose output
pytest -v
```

See **[TESTING.md](TESTING.md)** for detailed testing guide.

### Code Quality Checks

```bash
# Format code with ruff
ruff format src/ tests/

# Lint code with ruff
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/

# Type checking (if mypy configured)
mypy src/
```

### Building Documentation

```bash
# Generate Sphinx documentation
cd docs
sphinx-build -b html . _build

# Open in browser
open _build/index.html  # macOS
xdg-open _build/index.html  # Linux
start _build/index.html  # Windows
```

## Project Structure

```
ProjektKraken/
├── src/
│   ├── app/           # Application entry point and MainWindow
│   ├── core/          # Business logic and data models
│   ├── services/      # Data access and background workers
│   ├── commands/      # Command pattern implementations
│   ├── gui/           # PySide6 widgets and UI components
│   ├── cli/           # Command-line tools
│   ├── webserver/     # Embedded FastAPI server
│   └── resources/     # UI resources (icons, themes, etc.)
├── tests/
│   ├── unit/          # Fast unit tests
│   └── integration/   # Integration tests
├── docs/              # Documentation
├── scripts/           # Utility scripts
└── themes.json        # UI theme definitions
```

### Layer Architecture

ProjektKraken follows a strict **Service-Oriented Architecture (SOA)**:

1. **Core Layer** (`src/core/`) - Data models and business logic
   - No dependencies on GUI or services
   - Pure Python dataclasses and utilities

2. **Services Layer** (`src/services/`) - Data access and operations
   - Database operations
   - Background workers
   - External API integrations

3. **Commands Layer** (`src/commands/`) - Command pattern for undo/redo
   - All user actions as command objects
   - Shared between GUI and CLI

4. **GUI Layer** (`src/gui/`) - User interface
   - "Dumb UI" - no business logic
   - Signals/slots for communication

5. **App Layer** (`src/app/`) - Application orchestration
   - MainWindow coordinates components
   - Signal/slot wiring

6. **CLI Layer** (`src/cli/`) - Headless tools
   - Reuses commands from Commands layer
   - 100% feature parity with GUI

See **[Design.md](../Design.md)** for complete architecture specification.

## Development Best Practices

### Code Style

- **Line Length:** 88 characters (Black/Ruff default)
- **Imports:** Group by stdlib, third-party, local (no wildcards)
- **Type Hints:** Required for all functions
- **Docstrings:** Google Style, required for all public APIs
- **No print():** Use `logging` module instead

### Adding New Features

1. **Define data model** in `src/core/`
2. **Add service method** in `src/services/`
3. **Create command class** in `src/commands/`
4. **Add GUI widget** in `src/gui/` (if applicable)
5. **Add CLI tool** in `src/cli/` (for feature parity)
6. **Write tests** in `tests/`
7. **Update documentation** in `docs/`

### Common Tasks

#### Adding a New Entity Type

1. Update `src/core/entities.py` if needed
2. Add service methods in `src/services/db_service.py`
3. Create command in `src/commands/`
4. Add GUI editor in `src/gui/`
5. Add CLI tool in `src/cli/entity.py`
6. Write tests

#### Adding a New CLI Command

1. Create module in `src/cli/<name>.py`
2. Reuse command classes from `src/commands/`
3. Add argparse configuration
4. Update `src/cli/README.md`
5. Write integration test

#### Adding a New Service

1. Create service class in `src/services/<name>_service.py`
2. Add to `MainWindow` initialization if needed
3. Use Qt threading patterns for background operations
4. Document in appropriate docs file
5. Write unit tests

## Environment Variables

ProjektKraken supports configuration via environment variables:

**LLM Configuration:**
```bash
# Embedding provider
EMBED_PROVIDER=lmstudio  # or sentence-transformers

# LM Studio
LMSTUDIO_EMBED_URL=http://localhost:8080/v1/embeddings
LMSTUDIO_MODEL=nomic-ai/nomic-embed-text-v1.5-GGUF
LMSTUDIO_API_KEY=optional-key

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229

# Google Vertex AI
GOOGLE_PROJECT_ID=my-project
GOOGLE_LOCATION=us-central1
GOOGLE_MODEL=gemini-pro
```

**Webserver Configuration:**
```bash
WEBSERVER_HOST=127.0.0.1
WEBSERVER_PORT=8000
```

Create a `.env` file in the project root for local configuration (not committed to git).

## Troubleshooting

### Virtual Environment Issues

**Problem:** Command not found after activating venv

**Solution:**
```bash
# Recreate virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Import Errors

**Problem:** `ModuleNotFoundError` when running tests or app

**Solution:**
```bash
# Ensure you're in project root
cd /path/to/ProjektKraken

# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Qt Platform Plugin Errors

**Problem:** `qt.qpa.plugin: Could not load the Qt platform plugin`

**Solution (Linux):**
```bash
# Install required system libraries
sudo apt-get install -y \
    libegl1 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1

# For headless testing
export QT_QPA_PLATFORM=offscreen
```

### Pre-commit Hook Failures

**Problem:** Ruff or pytest fails during commit

**Solution:**
```bash
# Fix formatting
ruff format src/ tests/

# Fix linting issues
ruff check --fix src/ tests/

# Run tests to identify failures
pytest
```

## Related Documentation

- **[TESTING.md](TESTING.md)** - Testing guide
- **[Design.md](../Design.md)** - Architecture specification
- **[DATABASE.md](DATABASE.md)** - Database architecture
- **[QT_THREADING_SAFETY.md](QT_THREADING_SAFETY.md)** - Threading patterns
- **[CLI.md](CLI.md)** - CLI tools overview
- **[SECURITY.md](SECURITY.md)** - Security best practices

## Getting Help

- **Documentation:** Check `docs/INDEX.md` for complete documentation index
- **Code Examples:** Browse existing code for patterns
- **Tests:** Check test files for usage examples
- **Architecture:** Review `Design.md` for system design
