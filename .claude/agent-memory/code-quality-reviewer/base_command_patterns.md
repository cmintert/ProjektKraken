---
name: BaseCommand and Tag Helper Patterns
description: Recurring patterns in src/commands/base_command.py — tag helpers, inline imports, typing issues
type: project
---

`BaseCommand` in `src/commands/base_command.py` contains two static tag helpers (`_assign_tags`, `_sync_tags`) used by both `entity_commands.py` and `event_commands.py`.

Key observations from first review (2026-04-12):
- `object_type` parameter on both helpers is a plain `str` but only ever `"entity"` or `"event"` — good candidate for `Literal["entity", "event"]`.
- `CommandResult.data` field is typed `Dict` (bare, unparameterized) — should be `dict[str, object]` or at minimum `dict`.
- `from typing import Dict, List, Set` — legacy; replace with built-in `dict`, `list`, `set` (Python 3.13 target).
- `import time` and `import re` are deferred inside methods (`__init__` and `get_description`) instead of at module top-level — violates isort/standard practice.
- `_assign_tags` and `_sync_tags` are static helpers with no direct dependency on instance state; they could live in a shared `tag_utils.py` module in `src/commands/`, but living on `BaseCommand` is acceptable given current usage scope.
- `CompositeCommand.from_dict` contains a hardcoded `known_types` dict — should use `registry.py` instead. This is a separate design smell in `composite_command.py`.
