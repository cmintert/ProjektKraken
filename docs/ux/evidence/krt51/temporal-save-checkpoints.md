# KRT-51 — acknowledged temporal entity saves

Verified on 2026-10-04 against baseline `718b54ba`, using Python 3.13.14,
PySide6/Qt 6.10.1, offscreen Qt, isolated settings and disposable databases.

## Defect and change

The original diagnostic reproduced a successful save followed by a second save
before the asynchronous comparison refresh. That second save failed with
“The visible value or its source changed. Reload before saving.” A refresh
delivered during the pending second save was ignored and a manual retry failed.

Successful saves now carry `temporal_entity_checkpoint`: selected entity, saved
lore time, resolved state/provenance and baseline metadata. Commands build it
inside their transaction; WikiLink composites rebuild it after all children.
The coordinator checks command, entity, draft generation, revision and time.
The editor installs a deep copy before clearing pending state or restarting
autosave. Dirty drafts retain those comparisons when background refreshes arrive.

Missing or malformed successful acknowledgements preserve the live draft,
stop further saves and explain that the changes were saved but the entity must
be reopened. Existing Save Changes/Discard routes remain visible. Discard and
world/entity rehydration invalidate old acknowledgement generations.

## Rapid-edit walkthrough

`test_rapid_typing_uses_acknowledgement_before_real_autosave_timer` uses real Qt
keyboard events, the actual debounce timer and the actual EditorCoordinator,
with commands executing against an isolated database:

1. Open the entity description “Old harbor” and focus its text editor.
2. Type “ rebuilt”; let the debounce timer submit the first save.
3. While that save is pending, type “ again”.
4. Execute and acknowledge the first save, delivering no background refresh.
5. Let the restarted debounce timer submit the second save.
6. Execute and acknowledge it. The database and live document both contain
   “Old harbor rebuilt again”, and the draft is clean.

Assertions verify the caret and focus survive the first acknowledgement and
timer firing, the document retains undo, and the final acknowledgement preserves
the caret. Separate regression cases preserve selection and scrolling, test
manual follow-up saves, metadata/attribute edits and historical/current/future
baseline and event-owned state. Source labels update without rebuilding fields.

This is an automated functional walkthrough, not human benchmark timing or
a claim of improved first-time learnability. It addresses the context and
save-feedback expectations in benchmark KA-20 without changing that task.

## Authoring contract

Contracts **5, 6 and 9** apply: preserve creative context, make save state clear,
and retain feedback/reversibility. Ordinary editing stays in the inspector.
Enter remains owned by the focused field, including multiline writing; Escape
retains its existing local ownership. No additional modal chain, shortcut,
interaction exception or contract revision is introduced.

## Validation and limits

Permanent coverage in `tests/unit/test_temporal_save_checkpoint.py` exercises
consecutive saves, stale/during-save refreshes, old acknowledgements after
discard/entity/world changes, real conflicts, malformed delivery, dated creation,
calendar-aware source resolution, rollback on checkpoint failure, composites and
worker delivery after commit with persisted-history undo/redo.

Focused editor/coordinator/command/worker/temporal tests, the bounded `ci_fast`
suite, Ruff, full-source mypy and the collection policy are used for validation.
No executable build or real-world database modification is performed.

Final recorded results: 35 new checkpoint cases; 114 focused
editor/checkpoint/coordinator/time tests passed. The bounded suite passed
**1,324 tests, with 2 asset-related skips**. Ruff passed across `src/` and
`tests/`; mypy passed across all 428 source files; collection policy passed
with 5,699 full-suite tests and 1,326 `ci_fast` members. Additional focused
worker/command/temporal cases passed in the earlier expanded checks.

Two additional checks expose failures already present at the baseline:

- The architecture API ratchet omits the existing
  `DatabaseService.require_connection` method from its reviewed baseline.
- `test_mainwindow_check_unsaved_changes` uses a `MockEditor` without the
  `show_world_at_event_requested` signal required by the existing MainWindow.

These are outside this fix. The original log's cross-thread timer warning,
invalid font-size warning and AnalysisPanel signal warning also remain outside
scope; these tests do not establish their causes or remediation.
