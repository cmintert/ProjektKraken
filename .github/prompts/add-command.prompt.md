---
description: "Scaffold a new ProjektKraken command with coordinator wiring and tests. Use when adding an undoable user action that needs BaseCommand, registry updates, app-layer integration, and pytest coverage."
name: "Add Command"
argument-hint: "Describe the new command, target domain, coordinator entry point, and expected tests"
agent: "agent"
---

Create a new ProjektKraken command from the user request and carry the change through implementation.

Requirements:
- Inspect existing command and coordinator patterns before editing.
- Implement the command as a `BaseCommand` subclass in `src/commands/` with `execute(self, db_service)`, `undo(self, db_service)`, `to_dict()`, and `from_dict()`.
- Use `BaseCommand._assign_tags(...)` or `BaseCommand._sync_tags(...)` when the change affects entity or event tags.
- Register the command in `src/commands/registry.py` if it must be deserialized from history.
- Wire the feature through the appropriate coordinator in `src/app/coordinators/` instead of letting GUI code call persistence directly.
- Add or update focused tests under `tests/` using shared fixtures from `tests/conftest.py`.
- Run the most relevant tests after editing. If the change is command-focused, prefer focused command or integration tests before broader runs.

Implementation checklist:
- Determine whether the feature is a single command or a `CompositeCommand`.
- Preserve enough serialized state for undo after deserialization.
- Keep GUI files as dumb UI and route mutations through coordinator -> command -> worker execution.
- Respect offscreen Qt handling and shared `MockQSettings` state in tests.

Useful reference points:
- `src/commands/base_command.py`
- `src/commands/entity_commands.py`
- `src/commands/event_commands.py`
- `src/commands/composite_command.py`
- `src/commands/registry.py`
- `src/app/coordinators/editor_coordinator.py`
- `tests/conftest.py`

Expected outcome:
- Implement the code changes, not just a plan.
- Summarize what was added, how it is wired, and which tests were run.