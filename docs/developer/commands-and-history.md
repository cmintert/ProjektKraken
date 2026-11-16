# Commands and History

Commands represent user-visible mutations and make undo and redo possible.

## Required contract

```python
class ExampleCommand(BaseCommand):
    def __init__(self, item_id: str, value: str) -> None:
        super().__init__()
        self.item_id = item_id
        self.value = value

    def execute(self, db_service: DatabaseService) -> CommandResult:
        ...

    def undo(self, db_service: DatabaseService) -> CommandResult | None:
        ...
```

Do not pass a service into the constructor. Commands are created on the main
thread and executed with the worker-owned service.

Commands must:

- retain enough state for undo;
- return a `CommandResult`;
- serialize only stable data;
- preserve failure information;
- leave undo and redo stacks unchanged when execution fails.

Use `BaseCommand._assign_tags()` and `_sync_tags()` for tag work.

## Persistent and session artifacts

The command coordinator maintains overlap guards so undo and redo cannot run
concurrently. Some large binary mutations store reversible artifacts outside
the serialized command payload. Preserve those lifecycles when extending maps
or rasters.

Worker entry points delegate to `execute_with_history`: command effects and the
ordered history transition share one transaction. Persistence errors propagate
instead of producing a successful action without undo information. Outcome hooks
wait for the outer transaction; asset stores journal touched paths and restore
them on rollback. Commands must continue to serialize complete undo state and
must use the managed asset stores for filesystem changes.

The `HistoryStore` manifest owns stack ordering and branch invalidation. Both
stacks cross the queued worker boundary as detached dictionaries; startup never
skips an invalid active record to expose older history. Session-only commands
form restart boundaries. The hierarchy command preserves exact key presence,
including legacy nulls, without overwriting unrelated map attributes.

