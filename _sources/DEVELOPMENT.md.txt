---
**Project:** ProjektKraken  
**Document:** Development Guide  
**Last Updated:** 2026-01-01  
**Commit:** `d9e3f83`  
---

# Development Guide

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

1.  Activate the virtual environment:
    ```powershell
    . .\.venv\Scripts\activate.ps1
    ```
2.  Run the hooks:
    ```powershell
    pre-commit run --all-files
    ```
