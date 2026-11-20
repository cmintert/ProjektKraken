# KRT-113 Event-to-Event timing

Implementation and verification record, updated 28 October 2026, for
[KRT-113](https://linear.app/projektkraken/issue/KRT-113/implement-event-to-event-timing-with-joint-uncertainty-and-reviewed),
following [KRT-111](../krt111/README.md). Baseline:
`2b0dddf09153048691fd4cfaaec7fa360ac78df3`, branch
`dev/krt-111-event-anchors`, application 0.20.1. The owner authorized a local
commit on 28 October, reusing recorded checks without another full suite.
Push, package and release remain separate delivery actions.

## Implemented boundaries

Events have one schema-2 timing definition. Start and independent end each choose
Manual date or Follow Event. A reference identifies a stable Event and its start
or authored end, with signed fractional days or whole calendar months/years.
Occurrence, fixed duration, independent end, and an explicit zero-duration end
remain distinct. Unsupported definitions retain their original metadata.

The pure endpoint engine separates the directed derivation graph from the
constraint network. Exact rational bounds, formal strictness, disjoint branches,
calendar validity, interval ordering and chronology determine joint feasibility.
Projected ranges retain gaps; possible/definite and duration queries retain the
joint model. Layout selects one deterministic feasible branch, preserving nominal
layout preferences for unbounded approximations. Representatives remain layout
coordinates, not historical assertions.

The database-thread feature adapter captures and registers detached snapshots.
Cancellable calculation runs outside write transactions. Registered commands
verify the reviewed intent and fingerprints, merge unrelated current content,
apply all persisted projections atomically, and form one undo operation. Redo
checks its expected inputs. Source deletion and referenced-end removal are blocked
until timing references are resolved. Observing Map/Relation windows do not add
evidence to Events and retain inclusive starts/exclusive ends.

Persisted legacy updates, chronology edits and previously confirmed deletions
replay recorded operations after checking their restored inputs. They do not
re-enter forward-edit validation. New deletions still block references. Calendar
creation, updates and activation restore the previous active selection through
persisted Undo/Redo, including a world with no active calendar.

Schema migration `004_event_timing` preserves authored values, referring records,
custom indexes/triggers and compatible history, and permits absent compatibility
coordinates. Recovery is backed up before migration; injected rebuild failure
restores the original database. Schema versions 0–3 remain recognizable before
upgrade; new worlds use schema 4.

No timing slot was added to DatabaseWorker. The existing command dispatcher
accepts a generic deferral hook; the feature coordinator and adapter own timing
work. The reviewed ImportService hotspot was reduced from complexity **32 to 29**
by extracting timing normalization; its existing allowance ceiling is now 29.

## Authoring contract review

| Contract | Route and preserved behavior |
| --- | --- |
| 1, progressive disclosure | Manual date remains the default. End fields, endpoint/offset choices, and saved evidence/constraints have disclosures. No persistent toolbar controls were added. |
| 2–4, semantics/surfaces/language | Inspector source selectors author dates; the cascade dialog reviews multi-object consequences. Duration and End Date state their distinct authority. |
| 5, context preservation | Context refresh updates target labels without replacing date/offset drafts. Same-Event hydration preserves follow disclosure state. Cancellation keeps the editor draft; temporal generations do not move the playhead. |
| 6–8, modes/discovery/consistency | Visible Manual date/Follow Event choices reuse wrapping, scroll-safe controls. Unavailable targets remain visible with explanations. Unsupported timing has a repair explanation and unavailable editing. |
| 9, feedback/reversibility | Incomplete source selection reports inline. Calculation must finish before saving. Cascade review exposes before/after dates and uses; accepted changes have one Undo. |
| 11, action labels | Complete labels remain visible in the retained 360 px captures; no shortened action names substitute for readable wording. |
| Keyboard interpretation | Native combo popup navigation, focused offset editing and local date Enter/Escape ownership remain in shared controls. New meanings have contextual Help declarations. Native traversal/modality review remains pending. |

Source selectors are input modes, not navigation links. They retain shared input,
selection, focus and disabled presentation. Disclosures use the shared quiet
control. Supporting calculation/evidence text uses the shared supporting-text
role; no local colors or policy exceptions were introduced. Bound Timeline starts
cannot drag and explain the inspector offset/detach route in their tooltip.

## Automated verification

Run with the project virtual environment and `QT_QPA_PLATFORM=offscreen`.
Commands and complete local transcripts are retained under `logs/krt113-*.log`
(generated artifacts, not source-controlled evidence).

| Gate | Recorded result |
| --- | --- |
| Focused caller/authoring/architecture matrix | 113 passed |
| Solver/calendar cancellation/migration/context matrix | 76 passed |
| Final consumer validation/query matrix | 73 passed |
| Recorded history/caller compatibility matrix | 49 passed; subsequent import/history boundary matrix: 35 passed, including eight dedicated history cases |
| Inspector composition across themes, fonts and widths | 63 passed; 80.15 s |
| Shutdown ownership followed by inspector composition | 68 passed; 87.85 s |
| Complete `ci_fast` sweep before the final consumer additions | 2,760 passed, 3 skipped; 506.55 s |
| Subsequent `ci_fast` including the refresh repair | 2,786 passed, 3 skipped, one Markdown export failure (`WinError 5` publishing its temporary asset directory); 677.32 s. The complete 17-case data-trust module passes on rerun. This does not turn the failed sweep into a pass. |
| Fresh `ci_fast` after the review refinements | **2,810 passed, 3 skipped**, 4,518 deselected; 521.10 s. Explicit exit code 0 and JUnit report retained under `logs/krt113-resume-ci-fast.*`. |
| Final `ci_fast` with completed Qt isolation | **2,810 passed, 3 skipped**, 4,518 deselected; 457.87 s. Explicit exit code **0**, `logs/krt113-verified-ci-fast.*`. |
| Refresh, progress, review and history matrix | 83 passed; 17.57 s. Subsequent review/calendar/clock-time and data-trust matrix: 43 passed; 4.58 s. |
| Full regression before Date-frame autosave changes | **7,326 passed, 5 skipped**, six deprecation warnings; 857.56 s. Explicit process exit code **0**, `logs/krt113-verified-regression.*`. Includes the repaired worker-class, persistence and presentation isolation paths. |
| Date-frame autosave `ci_fast` | **2,828 passed, 3 skipped**, 4,518 deselected; 608.25 s, exit **0**, `logs/krt113-autosave-final-ci-fast.*`. |
| Date-frame autosave full regression | **7,343 passed, 5 skipped, 1 failed**; 1,120.64 s, `logs/krt113-autosave-final-regression.*`. The sole failure is the muted-light secondary-action pixel test. This run is not recorded as a pass. |
| Focused checks after final fixes | **55 passed** for authoring, planning and history; **52 passed** for authoring and theme rendering after replacing the fixed render delay with an exact-state wait (`logs/krt113-autosave-render-state.log`). No full rerun was performed after the owner requested stopping broad reruns. |
| Ruff and repository-wide mypy | Passed; latest mypy covered 563 source files including the review dialog |
| Complexity, visual and test policies | Passed after the final source changes; no policy baselines were weakened |
| Help inspection, offline Help, generated schema | Passed |
| Strict Sphinx (`-n -W --keep-going`) | Passed with the final verification record |

Tests cover all endpoint combinations, endpoint-acyclic mutual Event references,
true cycles, collective interval infeasibility, correlated duration/queries,
calendar invalid candidates, periodic shortcuts, cancellation, large affine chains,
stale/unregistered/mismatched plans, concurrent prose, exact undo/redo, canonical
start-position searches without writes, broken imports, nullable reopen, custom
storage objects, retained history, and injected migration rollback. The exact
difference solver is checked against an independent bounded exhaustive oracle.

Serial-suite fixture repairs retain real Qt receiver objects, isolate each case's
theme sender, and give constructed application windows explicit `qtbot` ownership.
At the same Connections test checkpoint, retained Qt roots fell from 330 to 60
after fixing two shutdown tests; the two complete MainWindows and their popup
trees were no longer retained. This is test-lifecycle evidence, not a production
performance claim. Application infrastructure is not deleted by blanket cleanup.

The remaining serial native crash was traced to collection-time module reloading
in `test_llm_generation_widget.py`. It replaced `GenerationWorker` after the
preview test imported that class. Patching the stale class's `start` method then
missed the active factory and launched a real generation thread. Temporary weak
thread tracking recorded that worker surviving into later test files; Qt captured
the running-thread destruction fatal message. Removing the unnecessary reload
keeps class identities coherent. The preview test now verifies that its start
mock is called and the worker is not running. The combined 111-case replay
passes; no blanket widget deletion, forced thread termination or speculative
shared-fixture collection change was added.

Four existing date-entry persistence cases now use the shared prepared timing
command fixture. The duration-bounds case checks elapsed length and measured name
width rather than a removed fixed-width constant. All 32 cases in those two
files pass without weakening the command's required validation boundary.

The next complete run reached a pytest summary (7,319 passed, five failed,
five skipped and four teardown errors), then aborted at process shutdown.
The persistence fixture had mocked out workspace construction while invoking
real shutdown, leaving real worker threads behind. It now builds the real shell
with an unstarted mock worker and a disposable world; 31 related window cases pass.

Four remaining presentation failures passed in isolation. The shared test fixture
now restores the QApplication stylesheet, font and palette after deferred widget
cleanup, preserving the original size/color/font assertions across cases. The
Graph toolbar case instead required overflow even when both actions fit. It now
verifies the complete Filter action remains visible or in overflow, alongside its
existing label audit and geometry checks. The repaired 124-case presentation and
persistence matrix passes. The superseded run was stopped after verifying its
unique pytest report path; final full and fast runs use all these repairs together.

## Owner-reported Follow Event failure

The owner reported a native save rejection on 27 October: “Event timing changed
since this draft opened.” Read-only inspection and a detached offscreen
reproduction identify a refresh gap: accepted Timeline changes update the saved
calculation through the shared context, while the inspector's loaded timing
definition can retain the earlier start. The next Follow Event save then sends
that old definition as its expected state and is rejected before writing.

Using the recorded Timeline before/after dates reproduces the same rejection;
fresh loading of the current Event accepts the same Follow Event proposal.
The successful recorded command was a scalar Timeline move, not a persisted
Follow binding. Failed request payloads are not retained, so the exact baseline
of the owner's first failed attempt cannot be reconstructed from history.

**Refresh repair implemented after owner authorization.** The inspector now
compares controls with their hydrated presentation and retains the separate
authoritative definition, so minute-sized controls do not invent edits to finer
stored instants. Accepted generations refresh untouched timing without replacing
writing, selection or disclosure state. Unchanged definitions refresh saved facts
without replacing focused controls. Successful save acknowledgements advance the
baseline from the accepted snapshot, including while newer edits remain active.
Unchanged scalar fields retain Follow Event and independent-end authority.

Real timing drafts retain the original expected-state check. Explicit Discard
now clears local draft tracking before requesting reload, allowing recovery from
a genuine conflict. Tests cover Timeline and Undo followed by Save, writing and
date selections, uncommitted date text, active reference drafts, repeated Follow
Event saves, edits during an outstanding save, source cascades, fractional-date
preservation, and Discard through the real data-ready handler. The first targeted
run reproduced two failures before the correction; the Discard regression also
failed before its correction. No live world was modified for these tests.

Authoring Contracts 5 and 9 apply: preserve context and keep accepted saves distinct
from local drafts. Source/end routes, keyboard ownership, theme roles and inspector
geometry remain as recorded above. Native verification of this repair is pending.

## Owner-reported calculation and review overlap

The owner's native screenshot shows the calculation window alongside the old
message-box cascade confirmation. The coordinator now resets and retires delayed
progress before presenting a result. A calculation finishing within one second
does not open its progress window; longer calculations remain nonmodal and
cancellable. Validation still runs until complete or cancelled, without a timeout.

The single **Review date changes** window displays each affected item, Before and
After dates, interval durations and uncertainty directly in scrolling cards.
There is no separate Show Details step. Clock time appears when set, whole-day
dates omit midnight, and calendar changes retain the previous calendar for Before
dates. Strict bounds and alternative ranges remain distinct. Changes in timing
details with unchanged displayed dates are identified explicitly.

**Apply changes** is the shared primary action; **Cancel** has initial keyboard
focus and is the default. Escape cancels this review. Both cancellation and
accepted delivery terminate the inspector's Saving state; cancellation returns
to Unsaved changes with the intact draft. Tests exercise the actual nested dialog
loop and complete editor-to-command acknowledgement, including cancellation
while review is open. They check that progress is absent during review and no
write occurs until accepted command execution.

This applies Contracts 1–9 and 11 without adding persistent controls. Shared
dialog, temporal-card, supporting-text, primary/secondary action and focus roles
provide presentation; no local colors or policy allowances were added. Six-theme
360/680 px tests cover wrapping, reachable action labels and Cancel/Escape.
Native DPI, focus and owner acceptance remain pending.

## Date-frame draft boundary

The owner clarified that every control in the Date frame belongs to one draft:
manual date/time and uncertainty, start/end sources and endpoints, day/calendar
offsets, occurrence/end choice, duration and independent end. Debounced autosave
now submits only changed fields outside that frame. It never commits raw date text
or requests timing calculation/review. Save Changes deliberately submits the whole
timing draft through the existing prepared-plan and cascade-review path.

The worker-side content-only scope preserves the current authoritative timing,
including metadata and projection scalars. A content-only request containing date
or duration scalars is rejected. Successful partial acknowledgements advance the
content baseline, retain pending timing and expected-state checks, and do not
resubmit already saved prose. Untouched timing still adopts newer accepted facts;
active timing drafts, invalid date text, caret and selection remain intact.

The existing supporting-status label says **Timing not saved — choose Save
Changes** after an autosave tick leaves timing outstanding. No extra button,
toolbar, modal, color or interaction role was added. Contracts 1/3/5/6/7/8/9/11
apply; explicit Save/Discard and focused date Enter/Escape keep their meanings.
Help IDs and anchors are unchanged and the affected source reviews were updated
individually. The 40-case authoring matrix includes all frame controls, an
incomplete reference, prose delivery during invalid input, concurrent timing
refresh, command-scope enforcement and Undo; an earlier wider save/cursor/plan
matrix passed 134 cases. Broad and final focused results are recorded above.

## Rendered review

`render_timing.py` reproduces the retained offscreen captures without opening a
saved world or changing saved preferences. It registers Windows Segoe UI explicitly;
the first fontless captures were replaced after inspection revealed missing glyphs.

- Timing cards: all six themes at **360 × 1000** and **680 × 1000**; manual start,
  independent followed end, fractional offset, expanded endpoint options and focus.
  See [dark narrow](timing-dark_mode-360.png),
  [light wide](timing-light_mode-680.png), and
  [unsupported timing](timing-unsupported-360.png).
- Offline Help: the actual HelpViewer using the generated Event timing page,
  dark/light at **360 × 900** and **680 × 900**. Search for “follow event” was
  checked to reach Event timing. See [narrow Help](help-dark_mode-360.png) and
  [wide Help](help-light_mode-680.png).
- Cascade review: all six themes at **360 × 560** and **680 × 560**, showing
  completed Before/After snapshots and shared actions. See
  [narrow light review](review-light_mode-360.png) and
  [wide fantasy review](review-fantasy_mode-680.png).
- Timing draft after an autosave tick: actual Event inspectors in all six themes
  at **360 × 900** and **680 × 900**, using disposable data and no database worker.
  The status and Save Changes remain visible with no timing-review popup. See
  [narrow fantasy draft](autosave-fantasy_mode-360.png) and
  [wide light draft](autosave-light_mode-680.png). These establish offscreen
  rendering, not native DPI or human acceptance.
- Inspection corrected broad uppercase styling on calculation feedback, removed
  an empty Span heading in independent-end mode, and hid invented numeric fields
  for unsupported timing. Full action labels, focused input and scrolling remain
  visible in the reviewed captures. Existing shared combo arrows render as square
  indicators in this offscreen style; native arrow appearance is not established.

Retain these small PNGs and the reproduction script with this feature. Generated
manual/Help trees remain under `docs/_build/`; no recovery bundle or personal world
is included in the evidence directory. Offscreen captures do not establish native
Windows DPI behavior or independent human readability.

## Documentation review record

This uses the [documentation review form](../../../developer/documentation-review.md).

| Field | Record |
| --- | --- |
| Reader and purpose | Existing worldbuilders authoring relative Event dates; primary purpose is a how-to, with concise control reference explanations. |
| Canonical pages/release | Event chapter and Timeline/calendar chapter for the unreleased follow-up to 0.20.1; Map deletion wording and manual control index corrected. |
| Verified source | Timing source/range widgets, Event editor, feature coordinator, prepared commands, migration and tests in the dirty worktree above. |
| Routes | Start or independent End → Follow Event → source Event → endpoint/offset → Save Changes → cascade Apply changes; reopening verifies persisted definitions. Manual replacement detaches uncertainty deliberately. |
| IDs and destinations | Existing `event.timing`, date/chronology IDs and anchors retained. Ten new source/endpoint/offset/evidence/review inspection meanings point into the existing Event chapter. Reviewed source fingerprints were updated individually. |
| Rendered output | Generated manual HTML and actual offline Help content inspected; strict build and search checks recorded above. |
| Recovery | Cancel returns to the draft; Undo restores the accepted operation. Remove or replace references before deleting a source. Preserve the reported recovery bundle after upgrade. |
| Human reviewer/date | **Pending** |
| Native live Help/focus/modal ownership | **Pending** |
| Reader-round owner/cohort/date | **Pending**, using the [reader-testing form](../../../developer/documentation-reader-testing.md); no participant results recorded. |
| Human approval | **Pending**; automated results do not supply acceptance. |

## Remaining delivery limits

Native Windows interaction/DPI review, human prose/live Help review and owner
acceptance are outstanding. The Follow Event refresh repair has focused automated
coverage. The earlier complete regression passed; the latest autosave regression
has one theme-rendering failure followed by a passing focused rerun after the
exact-state wait correction. The owner requested no further full-suite rerun and
authorized committing with the recorded test results.
Push/package/release gates have not been run because
those delivery actions are not authorized. KRT-113 remains In Progress while
these review limits remain outstanding.
