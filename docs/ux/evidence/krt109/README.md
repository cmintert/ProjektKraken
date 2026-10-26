# KRT-109 direct-connection browsing

Implementation evidence for the owner-authorized first slice, 26 October 2026.
Verification baseline: `5a5dda2557861a2cc1c04f40e93847fb1b1a12b8`. The owner
subsequently authorized the local delivery commit using these recorded checks;
its hash is recorded in KRT-109. No push, release or user-world write is part of
this delivery.

## Behavior and decision boundaries

Entity World Context has a separate human direct-connection browser. Its 25-row
pages scan at most 100 candidates per worker invocation, applying the existing
temporal policy before admitting rows. It reads either canonical direction and
all predicates, including system-managed references. Self-links appear once.
State-change records retain their own subgroup; their attribute payloads are
not displayed. Uncertain descriptions are selected by their actual payload field,
before human budgeting, so a stat named Description cannot masquerade as prose.

Counts distinguish loaded rows, unknown totals, checked date exclusions and
unreadable records. Only a successfully exhausted scan supplies an eligible
total. A full last page can require one more Load more action to establish
exhaustion; it never guesses that the scan is complete. Missing endpoints or
invalid All history timing remain an explicit partial-result count. Query
failures retain loaded rows and offer Retry from the last accepted cursor.

The feature task borrows the existing connection on its owning database thread.
Each bounded read closes its transaction before returning. The GUI schedules
the next batch only after accepting the preceding response, giving commands a
queue boundary and obsolete requests a cancellation boundary. Cursor identity
includes query, section, ordering, policy, session, application mutation
generation, connection identity, own connection changes and external data_version.
Visible idle browsing checks for external changes once per second. Changes
restart the context rather than append another revision. Invalidation is
conservative: unrelated database writes can also restart browsing.

| ADR decision | First-slice treatment |
| --- | --- |
| D1 | Human paging has a separate service/transport. AI builder selection, serialized domain snapshot and formatter remain unchanged. Description-only human facts travel in a separate reader sidecar. |
| D2 | Direct SQL discovery has no predicate or direction allowlist; canonical IDs and direction survive. Existing temporal qualification still determines mode eligibility. |
| D3 | Saved Event links do not claim occurrence or participation. Existing shared-Event summaries are unchanged; their known evidence defects remain follow-up work. |
| D4 | Bounded pages, loaded-only disclosures, nullable totals, separate exclusions/partial/failure states and retry. Other snapshot sections remain capped and overlapping. |
| D5 | Direct-edge UUID, endpoints, window, uncertainty and Event sources retained. Richer surrounding paths and shared map/Event evidence remain deferred. |
| D6 | Stable casefolded source/predicate/target names plus relation ID; no normalization, association-ranking or tag-fallback changes. |
| D7 | Own writes, undo/redo, external changes, query/policy/calendar changes restart pages. Cancellation never interrupts a database command. |
| D8 | Existing thread, repositories/indexes, short reads and bounded evaluation. No migration, persistent index, cache or extra thread. Measurements below document remaining costs. |
| D9 | No attribute rows, attribute-only possible-change rows or attribute omission notices in human Context. Matching statblocks do not produce evidence. Entity editing and bounded generation attributes remain available. |

This is compliance within the bounded slice, not a claim that all historical
World Context association defects covered by D1–D9 are fixed.

## Verification and reproducible artifacts

Use the project interpreter with `QT_QPA_PLATFORM=offscreen` on Windows.

Final focused matrix: **211 passed, 1 skipped** (212 collected, 60.23 seconds).
Repository-wide mypy passed for 520 source files using an isolated cache after
the existing cache raised a deserialization error. Ruff, visual/complexity/test
policies, inspection inventory, generated schema, offline Help and strict Sphinx
passed. The matrix includes dependency enforcement for the new service/task;
no database-service import was added to the application or GUI layers.

- Focused matrix: context builder/projection/widget/coordinator, direct browsing,
  prepared generation, Help inspection/search/bundle, dependency direction and
  choke-point architecture checks. The new cases cover 84 mixed links,
  temporally excluded batches, Unicode variants, uncertain edges, source-event
  rescheduling, real relation-command execute/undo/redo, external commits,
  attribute/prose separation, frozen prepared messages, retries, focus and queue
  fairness. Existing reviewed hotspots are untouched.
- Run `python -m scripts.measure_connection_browsing` for retained synthetic
  timings at `docs/_build/krt109/implementation/timings.json`.
- Run `python -m scripts.capture_context_rows_evidence --browse` for 60 captures
  and a manifest at `docs/_build/krt109/rendered/`: six themes, requested widths
  360/800, preview, expanded/focus, loading, retry and disabled states.
- Run `python -m scripts.check_action_labels --matrix fast --surface
  AuthoringContextWidget --report-dir docs/_build/krt109/action-labels`.
  The populated matrix records 48 states with zero failures at scale 1.0,
  including doubled text, loading, retry and exhausted controls.
- Run `python -m scripts.capture_help_evidence --output docs/_build/krt109/help
  --topic authoring.tags --search-inspection --inspection-example connections`
  for actual offline Help, search and native explanation-popup captures.

Generated images/timings remain under the ignored build tree; the reproduction
scripts and this explanation are retained in source. No artifact cleanup or
personal-world replacement was performed. Offscreen captures do not establish
native Windows scaling or human comprehension. Narrow dark preview and wide
light retry rows were visually inspected; complete action labels and timing/
source wrapping remain reachable in the scroll area. The narrow dark native
explanation popup was also inspected after explicitly registering Segoe UI in
the offscreen capture helper; its prose and task link are readable.

### Synthetic measurement record

Windows 11 build 26300, AMD64 Family 26 Model 68 Stepping 0, Python 3.13.14,
Qt 6.10.1. Each world contains three Entities and generated links, with one
quarter of root links excluded by date. This models high adjacency and unrelated
edges, not a representative author's complete world or many distinct endpoints.

| Measurement | 100 direct / 500 unrelated | 1,000 direct / 5,000 unrelated |
| --- | ---: | ---: |
| Existing bounded snapshot, milliseconds | 11.04 | 83.93 |
| Existing snapshot direct rows | 12 | 12 |
| Warm first browse batch, milliseconds | 0.89 | 1.44 |
| First batch with Python memory tracing, milliseconds | 3.30 | 6.22 |
| Median continuation with tracing, milliseconds | 2.46 | 7.42 |
| Complete eligible scan with tracing, milliseconds | 8.24 | 228.39 |
| Eligible rows / read batches | 75 / 3 | 750 / 30 |
| Browse SQL statements | 21 | 210 |
| Retained-row Python peak memory, bytes | 153,926 | 1,354,189 |
| Queued sentinel delay, milliseconds | 5.33 | 7.49 |
| First 25-row widget render, milliseconds | 6.59 | 6.67 |
| All-loaded-row widget render, milliseconds | 14.10 | 78.49 |

Browse first-batch timings follow the snapshot baseline and are not cold-disk
measurements. The queue sentinel includes connection initialization and runs
behind one browse batch; a separate threaded regression verifies an actual save
runs before continuation. Rendering uses an actual 360-pixel offscreen widget;
the all-loaded measurement redraws the accumulated result, not a virtualized
model. Native Qt memory is not included in Python peak memory. No thresholds or
human speed-improvement claims are established by these samples.

EXPLAIN confirms existing source/target indexes select the adjacency and a
temporary B-tree performs ordering. Bounded returned candidates therefore do
not guarantee bounded SQL sorting time. The existing bounded overview still
runs before direct browsing in the current composition; these service timings
do not represent end-to-end context-open latency.

## Documentation review record

| Field | Record |
| --- | --- |
| Reader and purpose | Authors finding saved connections; existing World Context explanation plus operational Help/reference updates |
| Canonical pages | World Context model, search/AI guide and Entity/Event control appendix; Unreleased |
| Behavior sources | Browse service/repository/task/coordinator, existing temporal evaluator, human renderer and description-sidecar projection |
| Retained contracts | Authoring 1/2/4/5/6/7/8/9/11; typed links, semantic captions, shared quiet controls, same-object disclosure/scroll and local keyboard ownership |
| Help identity | Existing authoring.tags topic and anchors retained; context-load-connections adds help-context-load-connections |
| Help impact review | Three changed widget source fingerprints reviewed individually: constructor, theme application and same-object section presentation |
| Save and recovery | Browsing does not save lore; Retry resumes a failed read, relevant changes restart the sequence |
| Human prose approval | Pending |
| Native Windows DPI/live Help acceptance | Pending |
| Reader round and independent source-tracing outcomes | Pending; no participant cohort or timed improvement claim |

## Possible follow-up work

1. Neutral shared-Event evidence identifying the Event and both authored links,
   their directions, predicates and uncertainty; never infer interaction. Keep
   stronger role semantics coordinated with KRT-69/71/72.
2. Root-relative surrounding paths with actual supporting link chains, cycle
   handling and path-level uncertainty.
3. Shared-map identity by map/marker UUID, including duplicate map titles; then
   complete root-tag discovery with explicit Unicode and legacy-tag policy.
4. Representative-world cold/warm/end-to-end and prolonged browsing measurements,
   more distinct endpoints and supported native DPI/text scales, plus unfamiliar
   authors finding a custom link and tracing its source without predicate coaching.
5. Measure larger adjacency sorting and accumulated-row redraws before proposing
   any optional index, detached cache, separate read thread or incremental model.
6. Consider extracting generation attributes into an explicit input later, in a
   separate reviewed compatibility change; the current internal AI payload stays.

These are candidates, not activated implementation work or new release gates.
