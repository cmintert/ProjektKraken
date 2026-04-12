---
name: ProjektKraken Code Conventions
description: Key conventions enforced by ruff/pyproject.toml — Python 3.13, typing imports, docstring style
type: project
---

Project targets Python 3.13 (`requires-python = ">=3.13"`, `target-version = "py313"` in ruff).

**Why:** Modern typing syntax (`list[str]`, `dict[str, str]`, `set[str]` in lowercase) is preferred over `typing.Dict/List/Set` for Python 3.9+ code. At 3.13, `from typing import Dict, List, Set` is legacy and ruff will flag it under UP (if enabled) or mypy will accept both.

**How to apply:** Flag `from typing import Dict, List, Set` imports in reviewed files — recommend replacing with built-in generics (`dict`, `list`, `set`). Also `Literal` from `typing` is fine and preferred for constrained string params.

Ruff rules enabled: E4, E7, E9, F, I (isort), ANN (type hints), C901 (complexity ≤15). ANN401 (Any) is suppressed. ANN rules are skipped in tests.
