# Logging and operation diagnostics

Normal launches write INFO and above. Add `--diagnostics` to the packaged
`ProjektKraken.exe`, `start-kraken.cmd`, or `python -m src.app.main` to include
DEBUG records for that launch. The flag is consumed before Qt receives arguments.
Provider HTTP client internals stay at WARNING and above in either mode.

The ordinary log is `logs/kraken.<process ID>.log` beside the executable or
repository. If that folder cannot be written, it moves to the platform user
data `logs` directory. Each process owns a 5 MB file and five backups. Files
from exited processes are not automatically deleted. Native and uncaught
failures go to `faults.<process ID>.log`. Full-content AI audit records are
separate and require the user's audit setting; diagnostics mode does not
enable them. See [troubleshooting](../user/troubleshooting.md) for recovery
locations and report collection.

## Levels and ownership

- INFO: startup/session metadata, world lifecycle, and command operation
  requested, started, terminal and received/discarded events.
- DEBUG: bounded troubleshooting details such as counts and retry state.
  Repeated widget rebuilds should emit one summary, not one line per child.
- WARNING: recoverable errors or degraded capabilities.
- ERROR: one owner records a failed operation. For command exceptions this is
  the worker, which logs the exception type and stack *locations* without
  exception text or source lines. UI propagation is not another ERROR log.

Every ordinary record has a UTC millisecond timestamp, process ID, and thread
name. The launch record adds session ID, version and source/packaged build.
Save, undo and redo requests carry a serializable trace created by
`CommandCoordinator`: `operation_id` (unique per attempt), stable `command_id`,
command type, action, world ID, target ID where available, history epoch, and
monotonic request time. The worker logs the same IDs and terminal outcome plus
elapsed milliseconds; the coordinator records receipt or a discarded stale
result. New command operations should create their context at the request
boundary, pass the snapshot through the queued signal and attach it to the
result. Do not query the worker database or a mutable current world to
reconstruct it later. Empty world/target fields mean that context was not
available at the request boundary.

Temporal Entity saves add `save_origin=manual|autosave` and keep the entity ID
as the target even when WikiLink reconciliation wraps the edit in a composite
command. A rejected comparison emits `stage=temporal_rejection` with a stable
`reason`, `field`, optional bounded `field_key`, `lore_time`, and expected/actual
source kind, relation ID and event ID. `value_changed` reports a comparison,
never either value. The reasons are `visible_value_or_source_changed`,
`hidden_source_changed`, `metadata_changed`, `validation_rejected`, and
`unexpected_failure`. A successful command has no rejection record. The main
thread adds `stage=temporal_ack` with `outcome=accepted|rejected|invalid|stale`.
`invalid` means the command succeeded but the checkpoint was absent or failed
validation; `stale` includes a bounded mismatch reason such as
`generation_mismatch`. Match records by `operation_id` and `command_id` before
interpreting an acknowledgement. No description body, attribute value, event
name or resolved manuscript value belongs in these records.

Ordinary diagnostics must not include credentials, authored prose, complete
prompts, model responses, unrestricted HTTP bodies, or URLs that may contain
tokens. Log IDs, lengths, provider/error classes and numeric HTTP status
instead. Provider retries record bounded details at DEBUG; the worker owns the
final summary-generation error record. The opt-in AI audit path retains its
separate full-content behavior.

## Sanitized acceptance evidence

The focused mode test submits one DEBUG and one INFO record to the same log
path: the former DEBUG-default behavior records **2**, normal INFO mode
records **1**, and explicit diagnostics mode records **2**. The reviewed
historical log was about 89% DEBUG, with Sheet Builder accounting for about
41% of records; those figures describe the inspected log, not a predicted
volume for every session. Per-pair Sheet Builder clear/rebuild messages were
replaced with count summaries.

A representative operation transcript has this shape (synthetic IDs; authored
content omitted):

```text
session=<uuid> version=<version> build=source mode=normal
operation_id=A command_id=C1 action=save world_id=W target_id=T stage=requested
operation_id=A command_id=C1 action=save world_id=W target_id=T stage=started
operation_id=A command_id=C1 action=save world_id=W target_id=T stage=terminal outcome=succeeded duration_ms=12
operation_id=A command_id=C1 action=save world_id=W target_id=T stage=received outcome=succeeded
operation_id=B command_id=C1 action=undo world_id=W target_id=T stage=terminal outcome=succeeded duration_ms=9
operation_id=C command_id=C1 action=redo world_id=W target_id=T stage=terminal outcome=succeeded duration_ms=11
operation_id=D command_id=C2 action=save world_id=W target_id=T stage=terminal outcome=failed duration_ms=4
operation_id=D error_type=ValueError stack=worker.py:820:run_command
operation_id=E target_id=T stage=temporal_rejection save_origin=autosave reason=visible_value_or_source_changed field=description expected_source_kind=baseline actual_source_kind=relation actual_relation_id=R lore_time=12.0 value_changed=True
operation_id=E target_id=T stage=temporal_ack save_origin=autosave outcome=rejected reason=command_rejected
```

Each action also has requested and started events; they are omitted from the
last four lines for brevity. A late result after history reset or world switch
has `stage=discarded` with a reason, so it cannot be mistaken for a successful
edit to the current world. The focused tests check the queued payload/result
IDs, stale-result rejection, mode selection, sensitive-content exclusion and
bounded provider HTTP errors.
