---
description: "Use when editing command classes under src/commands, including new undoable actions, command refactors, command history persistence, and coordinator-triggered mutations. Covers BaseCommand shape, tag helper usage, registry updates, and serialization expectations."
name: "ProjektKraken Command Guidelines"
applyTo: "src/commands/**/*.py"
---

# Command Guidelines

- Commands represent undoable user mutations. Keep them in `src/commands/` and let coordinators or app-layer code construct and dispatch them.
- Inherit from `BaseCommand` in `src/commands/base_command.py`.
- `BaseCommand.__init__()` takes no service argument. Do not inject `DatabaseService` or repositories into the constructor.
- Implement `execute(self, db_service)` to return a `CommandResult` and `undo(self, db_service)` to reverse the mutation.
- Override `has_history` only for silent background synchronization commands that should not be tracked.

## Tag Handling

- For entity and event tag updates, use `BaseCommand._assign_tags(...)` for initial tag assignment and `BaseCommand._sync_tags(...)` for update diffs.
- Do not duplicate inline loops for assigning or removing tags unless the command has a genuinely different behavior that cannot reuse the helpers.

## Serialization

- Every persisted command must implement `to_dict()` and `from_dict()` with enough state to support history replay and undo after deserialization.
- Serialize domain objects with their own `to_dict()` and reconstruct them with `from_dict()` instead of storing partial ad hoc structures.
- Preserve execution-relevant snapshots such as previous values, backup objects, or derived state when undo depends on them.
- Use stable dictionary keys and class names so history deserialization remains backward-compatible.

## Registration And Composition

- Add new command types to `src/commands/registry.py` when they must be deserialized from history.
- If the feature is a coordinated multi-step mutation, prefer `CompositeCommand` rather than hiding multiple persistent changes inside one large command.
- When embedding commands inside `CompositeCommand`, ensure each nested command also has correct `to_dict()` and `from_dict()` behavior.

## Boundaries

- Keep business mutation logic inside the command and persistence calls on `db_service`; do not pull GUI concerns into command classes.
- Commands should operate on worker-thread-owned `DatabaseService`, not on widgets, live Qt objects, or main-thread state.
- Prefer existing command modules as examples before introducing a new shape.
