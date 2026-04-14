---
name: ProjektKraken Code Conventions
description: Key conventions enforced by ruff/pyproject.toml — Python 3.13, typing imports, docstring style
type: project
---

Project targets Python 3.13 (`requires-python = ">=3.13"`, `target-version = "py313"` in ruff).

**Why:** Modern typing syntax (`list[str]`, `dict[str, str]`, `set[str]` in lowercase) is preferred over `typing.Dict/List/Set` for Python 3.9+ code. At 3.13, `from typing import Dict, List, Set` is legacy and ruff will flag it under UP (if enabled) or mypy will accept both.

**How to apply:** Flag `from typing import Dict, List, Set` imports in reviewed files — recommend replacing with built-in generics (`dict`, `list`, `set`). Also `Literal` from `typing` is fine and preferred for constrained string params.

Ruff rules enabled: E4, E7, E9, F, I (isort), ANN (type hints), C901 (complexity ≤15). ANN401 (Any) is suppressed. ANN rules are skipped in tests.

**Enum docstrings:** `SeverityLevel` and `IssueType` in `src/core/analysis.py` had only one-liner docstrings — no `Attributes:` section for enum members. Flag this pattern in any new `Enum` subclass.

**Misleading cached-score pattern:** `CompletenessScore.completeness_score` field description implied it caches `calculate_score()` output, but the method recomputes from live fields on every call and never writes back. Watch for this disconnect between field description and method behavior in data model classes.

**`__post_init__` docstring gap:** `ValidationIssue.__post_init__` had no docstring. Always add at least a one-liner to public `__post_init__` methods.

**Relation-count duplication in WorldValidator:** `_check_orphaned_entities` and `_check_completeness_scores` both iterate `relations` with identical `sum(1 for r in relations if r.get("source_id") == obj.id or r.get("target_id") == obj.id)` generators per-entity. For large worlds this is O(entities * relations) twice. Extract a `_build_relation_count_map` helper that pre-computes a `dict[str, int]` in a single O(relations) pass.

**Magic number 20 in world_validator.py:** `_check_incomplete_data` uses `< 20` as the minimum description length, and `_check_unused_tags` uses `< 2` as minimum usage count. Both are inline literals with no named constant. Define `_MIN_DESCRIPTION_LENGTH = 20` and `_MIN_TAG_USAGE = 2` at module level.

**`from typing import Any` still used in world_validator.py:** `Any` from `typing` is acceptable (no built-in replacement), but the import exists alongside otherwise-clean Python 3.13 type syntax. Flag if `Any` can be narrowed.

**Test marker mismatch:** Tests in `test_world_validator.py` are decorated `@pytest.mark.unit` but each test method hits a real in-memory `DatabaseService` — they are functionally integration tests. Not a blocker but worth noting if test suite has separate slow/fast split.
