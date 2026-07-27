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

