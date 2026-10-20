# Worker failure contracts

KRT-38 implementation evidence, 2026-10-20. Comparison revision:
`6248e62c4e2b324b3547f73da4698dbdc7d96cc2`; the starting worktree was clean.

## Inventory

AST inspection of `DatabaseWorker` found **59 methods, 44 methods containing
exception handlers, and 54 except clauses** before this extraction. The earlier
issue description reported 52 clauses. Counts include nested handlers and count
constructs, not equivalent policies. After extraction there are **60 methods,
44 methods containing handlers, and 54 clauses**. The added reporter has no
exception handler.

This is a lightweight inventory of the 44 methods containing handlers. “Error”
below means `error_occurred`; a completion signal does not universally mean
success. Methods without handlers are outside this table. Outcomes describe the
worker's handling of exceptions; underlying service policies can differ.

| Method | Family | Observed exception outcome | Notable distinction |
| --- | --- | --- | --- |
| `_ensure_semantic_probe` | Capability probe | Warning, disables probe, returns `False` | Nonzero child exit also disables feature; no UI error |
| `initialize_db` | Lifecycle | Clears services, error, `initialized(False)` | Migration additionally emits report; diagnostic severity/messages vary by exception |
| `cleanup` | Lifecycle | Collects errors, emits `cleanup_finished` snapshot | Attempts DB close even after history failure |
| `initialize_history` | History | Logs and emits stable error | Missing DB also emits error; no history payload on failure |
| `load_timeline_grouping_config` | Fallback load | Logs, emits `None` | Failure and absent config/storage share a fallback shape |
| `save_world_theme` | Configuration write | Logs and emits stable error | Missing DB returns silently |
| `load_embedding_stats` | Fallback load | Logs, emits zero/default stats and error | Default payload alone cannot prove success |
| `load_events` | Selected simple load | Shared safe log, stable error and dataset failure | No loaded/completion signal; silent missing-DB guard |
| `load_entities` | Selected simple load | Shared safe log, stable error and dataset failure | Same contract as events |
| `load_maps` | Selected simple load | Shared safe log, stable error and dataset failure | Same contract as events |
| `load_markers` | Scoped load | Logs and emits map-specific error | Map ID payload; start/completion only on success |
| `load_trajectories` | Scoped load | Logs and emits map-specific error | Quiet success; no start/completion signals |
| `load_feature_geometry_states` | Scoped load | Logs and emits map-specific error | Quiet success; distinct scoped payload |
| `load_event_details` | Detail load | Logs and emits ID-specific error | Detail payload has three arguments |
| `load_event_authoring_context` | Fallback load | Logs, emits request-scoped empty context | Empty context also represents unavailable data/storage |
| `load_entity_details` | Detail load | Logs and emits ID-specific error | Distinct entity signal type |
| `load_entity_authoring_context` | Fallback load | Logs, emits request-scoped empty context | No error signal; empty context is ambiguous |
| `load_attachments` | Scoped load | Logs and emits owner-specific error | Guard requires attachment service; quiet success |
| `load_longform_sequence` | Load with partial fallback | Outer failure logs and emits exception text as error | Inner filter failures log and continue without the requested restriction |
| `load_calendar_config` | Fallback load | Logs, emits error and `None` | Missing storage also emits `None`; success can initialize default calendar |
| `run_command` | Command result | Emits failed `CommandResult` | Invalid request and missing DB have explicit failure results; no general error signal |
| `run_undo` | Command result | Emits failed `CommandResult` | Undo-specific result and history state |
| `run_redo` | Command result | Emits failed `CommandResult` | Redo-specific result and history state |
| `load_current_time` | Fallback load | Logs, emits `0.0` | Legitimate zero and failure are indistinguishable from payload alone |
| `save_current_time` | Configuration write | Logs and emits stable error | Missing DB returns silently |
| `load_ai_generation_preferences` | Fallback load | Logs, emits `None` | No error signal; missing DB returns silently |
| `save_ai_generation_preferences` | Configuration write | Logs and emits stable error | Missing DB returns silently |
| `save_graph_lexicon` | Configuration write | Logs and emits stable error | Missing DB returns silently |
| `load_grouping_dialog_data` | Compound load | Logs and emits stable error | Tags/config payload; no fallback on exception |
| `_do_index_object` | Background indexing | Logs and emits object-specific error | Finally releases in-progress state and processes pending embeddings |
| `rebuild_search_index` | Background indexing | Logs/error plus failed-count terminal signal | Missing dependency/service also emits failed count; missing DB only emits error |
| `apply_filter` | Filtered load | Logs and emits stable error | Two-list result; no empty-result fallback on exception |
| `resolve_entity_state` | Quiet snapshot load | Logs only | No failure result or error signal |
| `load_graph_data` | Compound load | Logs and emits stable error | Data/metadata can already have emitted before lexicon failure |
| `query_semantic_suggestions` | Optional background query | DEBUG traceback only | No result on error; unavailable/disabled service also returns silently |
| `load_completer_data` | Quiet compound load | Logs only | No failure payload or error signal |
| `run_import` | Import result | Logs, emits failed `ImportResult` | Returned failure gets status completion; raised exception does not |
| `run_markdown_import` | Import result | Logs, emits failed `ImportResult` | Missing DB also returns failed result; separate Markdown refresh flow |
| `run_markdown_batch_import` | Import result | Logs, emits failed `ImportResult` | Batch result and parsing; same terminal distinction |
| `run_single_obsidian_export` | Export result | Caught export errors become completion snapshot with `success=False` | Item lookup/path resolution occur outside its try block |
| `run_obsidian_vault_export` | Export result | Logs, emits completion snapshot with `success=False` | Snapshot contains output directory/errors; missing DB also has terminal result |
| `generate_summary` | Background generation | Safe log, target failure signal and stable error | No operation completion on failure; absent summary service returns silently |
| `_run_analysis_command` | Analysis | Error plus job-scoped failure signal | Always emits operation completion in finally, including failures |
| `prepare_intelligence_analysis` | Analysis snapshot | Logs, emits job-scoped snapshot failure | Missing DB has explicit failure; no generic error or operation completion |

No common cancellation protocol follows from these handlers. In particular,
silence, fallback values and failed results must not be interpreted as intentional
cancellation. The selected simple loads do not support cancellation.

## Selected contract and responsibility boundary

The three selected slots retain worker-owned `DatabaseService` calls and their
existing `@Slot()` entry points. Each checks the missing-DB guard, calls
`ensure_fresh_view()`, emits its start message, queries its list, emits the list,
then emits its completion message. No dispatch or database operation moves into
the reporter.

| Situation | Exact observable result |
| --- | --- |
| Nonempty or empty success | `operation_started("Loading Events...")`, `events_loaded(list)`, `operation_finished("Events Loaded.")`, once each, in that order |
| Database unavailable | No database calls, logs or signals |
| Refresh raises | One safe ERROR record, `error_occurred("Failed to load events.")`, then `dataset_load_failed("events")`; no start, loaded or completion signal |
| Query raises | Start already emitted; one safe ERROR record, the same error signal, then dataset failure; no loaded or completion signal |

Entities and maps substitute their corresponding nouns and list signals. User
messages and signal signatures are unchanged. A successful empty list is still
an actual loaded result, unlike an exception.

`_report_load_failure(operation, user_message, exc)` owns only one ERROR record
and one error emission. Its call sites supply constant operation names and
existing stable user messages. The record contains operation, exception class
and `safe_stack(exc)`: bounded basename/line/function traceback locations without
exception text, source lines or absolute database paths. This intentionally
replaces unrestricted `traceback.format_exc()` diagnostics for these three
handlers only, following [logging ownership and content rules](logging-diagnostics.md).
It does not change shared traceback formatting or other operation families.

The existing dependency tests restrict reporter calls and instance access to
logging, exception-class lookup, safe traceback formatting and `error_occurred`.
No new service, feature responsibility, Qt wiring or generic operation executor
is introduced. This centralizes a safe reporting policy; reducing line count or
cyclomatic complexity is not the objective.

## Receiving path and deferred findings

`WorkerManager` moves the worker to its database thread and explicitly queues
loaded results to `DataHandler` and errors to its GUI error-status slot.
`DataHandler.events_ready` reaches `DataCoordinator.on_events_ready`, which
updates caches, the unified list and timeline. Failed loads emit no loaded
snapshot, so existing data remains visible. A successful empty result travels
the normal loaded route and clears the list. The same distinction holds for
entity caches; maps reach `MapHandler.on_maps_ready` only through `maps_loaded`.
This extraction does not change connections or error-status presentation.

### Authorized startup follow-up (KRT-99)

After KRT-38, the owner explicitly requested fixing the stale tests and the
startup gap on 2026-10-20. The failure scenario and its fix are now exercised by
an automated real-thread/real-splash regression. This is offscreen Qt evidence,
not a native full-application launch.

The three simple-load slots now additionally emit
`dataset_load_failed("events" | "entities" | "maps")` after their existing error
signal. The reporter itself remains limited to safe logging and its original
error signal. `WorkerManager` explicitly queues this structured notification to
`DataCoordinator.on_dataset_load_failed`, without matching user-facing strings.
A failure for a pending primary dataset completes startup once with `False`,
which dismisses the existing splash through the existing entry-point connection.
Late loaded results still update data but cannot subsequently report startup
success. Unrelated datasets, already-loaded datasets and reload failures after
startup do not change its terminal outcome. Error-status presentation and the
worker's missing-DB guards remain unchanged.

Regression coverage includes failure of either primary dataset before or after
the other succeeds, duplicate failures, late success, unrelated/map failures,
normal empty startup and failures after successful startup. Four integration
cases drive a real worker thread, temporary database, data handler/coordinator,
unified list, error-status receiver and splash fade/close. All pass. Relation-only
refresh assertions now explicitly require `relations_only=True`, preserving the
existing draft-protection behavior.

The following observations remain separate work, not fixes or accepted new
contracts:

- Fallback payloads (`None`, `{}`, zero/default stats or `0.0`) can mask failures
  when observed without their accompanying signals. Several quiet loads do not
  emit terminal failures. Preserve those distinct policies in this issue.
- Longform filter failure can continue with broader data, graph load can emit
  partial results before failure, and single-item export preparation can raise
  outside its catch boundary. These require their own contract review.

## Verification and retention

### Initial KRT-38 verification

The focused worker/consumer/dependency selection produced **119 passed and
3 failed**. All 20 new cases pass: the 18-case family matrix, the real-thread
consumer regression and the reporter architecture guard. The three failures
are existing `TestReloadActiveEditorRelations` assertions expecting calls without
`relations_only=True`; actual calls include that keyword. They reproduce in
isolation (**1 passed, 3 failed**) and both the coordinator and its test module
are unchanged from the comparison revision. No unrelated expectations or
production behavior were altered to make these tests pass.

Other completed checks:

- Final `ci_fast`: **2,379 passed, 3 skipped**, with 4,447 deselected in
  523.50 seconds. The only warning is the existing Starlette/httpx test-client
  deprecation. This is the curated suite, not full regression; the three existing
  coordinator assertion failures are outside its selected membership.
- Repository Ruff and changed-Python-file formatting pass.
- Repository-wide mypy passes across **490 source files**.
- Complexity policy passes before and after against the same comparison
  revision. Each selected slot remains **3 → 3**; the reporter measures **1**.
  No reviewed C901 hotspot, suppression or allowance changes. An AST comparison
  verifies every other pre-existing worker method is unchanged.
- Visual policy passes against the comparison revision; no UI presentation,
  authoring routes, keyboard ownership, drafts, selection or theme roles change.
- Strict Sphinx builds successfully. Inspection of the generated HTML confirms
  the 44-method inventory table, contract table, headings and links from the
  developer index and architecture page. This checks rendered HTML structure,
  not a native screenshot review.
- Test collection policy is blocked by an existing renamed WikiTextEdit test:
  the baseline expects `test_on_theme_changed_forces_rerender`, while its
  unchanged module defines `test_on_theme_changed_refreshes_transient_colors`.
  Both that file and the collection baseline match the comparison revision;
  the baseline was not regenerated. New tests explicitly carry `ci_fast`.

Only synthetic test data is retained. Local reports and rendered documentation
live in ignored `artifacts/krt38/`; no existing artifacts or personal worlds are
removed or changed. Automated offscreen widget evidence is not native UX review.
No presentation or authoring interaction changes require new human acceptance.

### KRT-99 and test maintenance verification

The owner-authorized follow-up focused selection passes **73 tests**, including
all coordinator tests, the family failure matrix, four real-splash failure cases,
the queued display-retention case, the renamed theme test and existing splash
tests. Repository Ruff, formatting, mypy (490 source files), complexity and visual
policies pass after the fix.

Fresh follow-up `ci_fast`: **2,393 passed, 3 skipped**, with 4,442 deselected in
442.52 seconds. The only warning is the existing Starlette/httpx test-client
deprecation. The repaired relation-refresh assertions and all new startup cases
are selected in this curated suite; this is not a full-regression result.

The collection baseline was intentionally updated with the canonical collector
after verifying the renamed theme test. Review confirms that the old theme-test
ID is the **only removed ID** and its replacement is present; no smoke or
`ci_fast` membership is lost. The full snapshot also records 866 added IDs,
including previously unbaselined coverage and this session's additions, and
26 existing membership changes (all critical memberships retained). Current
collection: 6,838 tests, 2,396 in `ci_fast` and 19 in smoke. Collection policy now
passes; no production theme/editor behavior was changed.

An additional architecture/worker/dependency selection produced **54 passed and
2 pre-existing architecture failures**: its older module baseline omits
`DatabaseService.require_connection`, and its worker size warning budget is 2,089
lines while HEAD already contains 2,102 (current combined work: 2,115). The DB
service is unchanged. These baselines were not weakened and no unrelated
extraction or line-count cleanup was performed. Current dependency-direction and
complexity policy checks pass.

Follow-up local reports are retained separately under ignored
`artifacts/startup-load-fix/`, including focused/curated test output, collection
update/check/review, before/after complexity and pre-existing architecture evidence.

Reproduce with the project interpreter and `QT_QPA_PLATFORM=offscreen`:

```powershell
python -m pytest tests/unit/test_worker_load_failures.py tests/integration/test_worker_load_failure_delivery.py tests/unit/test_worker.py tests/unit/test_data_handler.py tests/unit/test_data_coordinator.py tests/unit/test_dependency_direction.py -q --tb=short
python -m pytest tests/unit/test_data_coordinator.py tests/unit/test_worker_load_failures.py tests/integration/test_startup_load_failure.py tests/integration/test_worker_load_failure_delivery.py tests/unit/gui/widgets/test_wiki_text_edit_re-render.py tests/unit/gui/test_splash_screen.py -q --tb=short
python -m ruff check
python -m mypy src
python -m scripts.check_complexity_policy --base-ref 6248e62c4e2b324b3547f73da4698dbdc7d96cc2 --format json
python -m scripts.check_visual_policy --base-ref 6248e62c4e2b324b3547f73da4698dbdc7d96cc2
python -m scripts.check_test_policy
python -m pytest -m ci_fast -q --tb=short
python -m sphinx -E -n -W --keep-going -b html docs artifacts/krt38/html
```

Retained local evidence includes `focused.txt`, `ci-fast.txt`, `sphinx.txt`,
`complexity-before.json`, `complexity-after.json`, `boundary-and-render.json`
and the `html/` tree.

The owner authorized a local commit on 2026-10-20, reusing the completed
verification above. Linear records the resulting commit and delivery status for
KRT-38/KRT-99. Push remains separately authorized.
