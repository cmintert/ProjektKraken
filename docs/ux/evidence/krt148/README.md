# KRT-148 — Active objects under Explorer filters

Implementation and automated evidence, 2026-11-09. On 2026-11-10 the owner
instructed: “commit, trust passed tests, and consider human verified.” This
records owner human acceptance of KRT-148 and reuse of the recorded test results.
It does not establish independently measured native-DPI coverage, a separate live
Help inspection session or reader-testing results.

## Behavior and boundaries

Accepted navigation owns the active Entity/Event identity. Search, category,
tags, sorting, full reloads and incremental snapshots are presentation changes
and emit no navigation request. Direct accepted navigation cancels older delayed
Explorer gestures, including when the accepted target is unchanged.

Explorer retains the complete cached source. Its proxy admits the active object
when ordinary filters exclude it and places that one source row first. The
caption **Active item · Hidden by filters** explains this exception. The same
native list row retains checkbox, drag MIME, context menu and deletion routes.
It scrolls normally, is never duplicated, and returns to ordinary sorted position
when it matches. No row is invented for a missing record. Deletion removes the
pin; selecting a different world requires a restart and creates fresh UI state.

Deliberate creation opens the new entry while preserving all filters.
Contextual creation retains its originating editor. The explicit `reveal_hidden`
compatibility API still clears filters on request; normal navigation no longer
uses that path. No database migration or new worker operation was introduced.

Contracts 2/5/6/7/8/9 apply. Typed title identity is retained; the explanatory
caption uses `supporting_caption`, selected text uses the palette selection role,
and focused rows use shared StyleHelper `focus_ring` over a neutral `surface`
backing. Caption geometry wraps using native font and checkbox metrics. No
contract exception or policy-baseline change is needed.

## Verification

- Focused regression coverage exercises search/tag/type exclusions for both
  object types, model resets, incremental mutations, stale timers, cancelled
  navigation, matching-again transitions, check-state retention, genuine
  selection, drag payloads, context menus and deletion.
- Integrated MainWindow cases execute real create and editor manual/autosave
  commands against the shared disposable database fixture. The fixture supplies
  the normal worker command-ID acknowledgement and detached detail responses.
  Real undo/redo writes and full snapshot delivery retain the new editor and
  filters after waits beyond the 250 ms selection delay.
- Existing contextual creation, stale detail response and draft guards remain
  covered by the focused creation/coordinator suites.
- Offscreen Qt captures at 360 logical pixels were generated under
  `artifacts/krt148/` for all six palettes, with Segoe UI explicitly loaded.
  Those local images are disposable and excluded from Git. Automated renders
  also exercise 800 px, long names, focus and disabled rows.

Verification outcomes (overlapping test batches are not summed):

| Check | Result |
| --- | --- |
| Focused Explorer, creation, coordinator and mutation batch | 174 passed |
| Final Explorer batch after presentation optimization | 52 passed |
| Final real create/manual-save/autosave/undo/redo cases | 4 passed |
| Repository Ruff and formatting | Passed |
| Repository mypy | Passed for all 652 source files with isolated, refreshed and ordinary project caches |
| Visual, complexity and Help inspection policies | Passed; no baseline exemptions changed |
| Test inventory policy | Passed; additions reported, no baseline regenerated |
| Offline Help generation and current-source validation | Passed |
| Strict Sphinx | Passed |

The broad `ci_fast` run reported 3,533 passed, three skipped and two failures.
One was the Explorer render fingerprint while source review was still being
finalized during that run; the final reviewed inventory passes both its checker
and `test_every_declared_explanation_is_generated_and_bounded` independently.
The remaining failure is
`test_map_event_anchors.py::test_inherited_summary_shows_impossible_joint_presence`:
its expected `With group dates (Old reign): not present` differs from the current
caption `With group dates (Old reign: from unbounded, until Handover): not present
at the viewed date.` It reproduces independently. The test and temporal validity
dialog are unchanged from baseline `89c3df08`; no map-caption change is included
here. This batch does **not** claim a fully green `ci_fast` run.

A 10,000-row, unshown offscreen Explorer probe exposed an unnecessary synchronous
full-list layout and comparator overhead. The final path caches the pin decision
per snapshot, uses native source order when no pin is needed, and lets Qt schedule
layout. Observed initial load was about 50 ms, ordinary incremental save 28 ms,
and filtered incremental save 36 ms, versus roughly 760 ms for the initial save
implementation. These are local presentation timings under development load,
not native/end-to-end database or usability benchmarks.

## Documentation review

Reader: an author who knows how to create and open entries. Primary Diátaxis
purpose: the existing how-to task “Find and organize Explorer entries,” with
short reference corrections in its existing control appendix. Canonical page:
`docs/user/workspace.md`; affected release: Unreleased, baseline `89c3df08`.

Source review traced the proxy, native list/delegate, accepted navigation,
creation delivery and save/refresh tests. Existing headings, task destination
`help-explorer-browsing`, control meanings and inspection IDs are retained.
Three affected source fingerprints were reviewed individually. The Search,
category and sort excerpts explain the pin; the Clear Filters excerpt now
accurately distinguishes advanced tags from search and category controls.

Starting state: an active filtered Explorer and a different entry to create/open.
Use the existing New/open route, edit, then Save or autosave. The new entry stays
active and appears once above results if excluded. To recover the full list,
clear search text, advanced tags and the category choice through their existing
controls. No content changes merely from filtering or pinning.

Source/structure, rendered output and human review are distinct evidence:

| Review field | Status |
| --- | --- |
| Source and operational claims | Reviewed against implementation and automated scenarios |
| Generated Help and Sphinx | Passed; dark 360 px and light 640 px Help renders inspected, with six-theme captures generated |
| Native Windows scale/focus and live Help review | Owner human verification accepted; no separate scale matrix or live Help session recorded |
| Human reviewer, date and prose approval | Owner human acceptance recorded 2026-11-10 |
| Reader-round owner, cohort and milestone | Pending |
| Independent reader outcomes | Pending |

All six 360 px Explorer palette captures were visually inspected after responsive
layout settled. The pin title/caption, ordinary result, selection boundary and
existing toolbar routes remained visible. Generated Help search for “active item
hidden by filters” reaches `explorer.browsing` among the first five results; the
existing Search inspection excerpt retains its target and explains the pin.

Use the existing [documentation review form](../../../developer/documentation-review.md)
and [reader-testing protocol](../../../developer/documentation-reader-testing.md)
for any later independent review and reader evidence. The owner authorized
commit using the passed tests on 2026-11-10. Normal commit hooks remain enabled;
the delivery hash is recorded in Linear after commit. No push was authorized.
