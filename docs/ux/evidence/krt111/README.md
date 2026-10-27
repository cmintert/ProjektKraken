# KRT-111 event-bound map presence

Implementation and verification record, 26 October 2026, for
[KRT-111](https://linear.app/projektkraken/issue/KRT-111/support-event-anchors-for-map-temporal-validity).
Baseline: `28e3a764c3a9e8b94f493d09038a55d08a107a77`, application 0.20.1.
The owner requested a development-branch checkpoint on 27 October 2026.
Its commit hash is recorded in KRT-111 after commit. Feature clarification and
human acceptance remain open; this checkpoint is not release sign-off.

## Implemented behavior

Map features and groups can follow a named Event independently on each side of
their presence window. The default endpoint is occurrence/start. Advanced
controls select authored end, an independently unknown date before/after the
endpoint, or a signed offset in fractional lore days or whole calendar months
and years. Map and Relation editors share these controls.

An authored end expression takes precedence over duration. A positive duration
shifts the uncertain start; absence of both leaves the end unresolved. Manual
dates and Use Playhead remain fixed assertions. Unknown, unbounded, missing
Event, unavailable calendar and unsupported metadata retain distinct meanings.

| Boundary contract | Implementation evidence |
| --- | --- |
| Exact starts inclusive; ends exclusive | Shared resolver and Map/Relation playhead regressions; empty intervals are rejected on forward edits. Deliberate occurrence remains distinct. |
| Year-only succession | Old and new states individually possible during year 120, old inactive/new definite at year 121. Shared transition identity proves no parent/child overlap; independent Events remain independent. |
| Authored end versus duration | Endpoint precedence tests include unavailable ends, uncertain duration-derived ends and separate end expressions. |
| Strict before/after | New references constrain an independently unknown date strictly before/after the shifted endpoint. A start after E and end before E is provably empty. |
| Fractional offset identity | Float hexadecimal identity distinguishes 1.000001/1.000002 days; signed zero aliases the original transition. Keyboard input retains 1e-20 and 5e-324. |
| Calendar arithmetic | Ordinal month/day/time preserved with custom lengths, leap rules, year variants, negative years and year zero. Any invalid candidate makes a coarse-date shift unresolved. Disjoint image ranges remain disjoint. |
| Numeric envelope | ±10^12 lore days. Unrepresentable precision and offsets are diagnosed rather than collapsed into exact dates. Prefix arithmetic avoids iterating years for distant dates; ordinary period shifts skip sparse variants. |
| Version compatibility | Schema 1 retains legacy relative semantics. Explicit advanced edits use schema 2; untouched legacy sides retain `legacy_v1`. Existing numeric instants and source-event flags remain supported. |
| Lossless editing | Missing references, future boundary formats and unrelated metadata survive save/reopen. Replacing a future whole-window format requires explicit choices on both sides. |
| Live refresh | Immutable Event/calendar generations refresh names, dates, precision, duration, deletion/undo and calendar changes. Map visibility refreshes without requiring playhead movement; unfinished manual text/caret survives replacement context. |
| Persistence and recovery | Existing commands validate against worker-owned evidence. Undo restores exact attributes without forward validation. Dependency preflight remains in place; unresolved map references resolve again after Event undo. |
| Import/export | SQLite portable-world round trip retains precision and references. Matching imports remap accepted incoming structural references without retargeting existing dependents or rewriting unsupported formats. |

No database schema migration is introduced. The application composes a narrow
feature coordinator using existing event-cache, lore-mutation and queued
calendar notifications. Domain helpers have no Qt or persistence dependency.
No feature slot was added to DatabaseWorker, and no new capability was added to
the transitional choke points. Raster and basemap timing behavior is retained.

## Automated verification

Use the project interpreter and `QT_QPA_PLATFORM=offscreen` for Qt tests.

- **527 passed** in the focused Map, Relation, calendar, temporal, persistence,
  transfer, validation and architecture matrix (62.52 seconds).
- **93 passed** for Graph data/projection, Entity temporal context, authoring
  context, state, raster, relation repository and temporal integration consumers
  (1.72 seconds).
- **124 passed, 1 skipped** for Help bundle/coordinator, explanation shortcuts,
  inspection coverage and search (85.65 seconds).
- **130 passed** after the final Map/Relation layout correction (27.56 seconds),
  including expanded-control containment at 360/800 px under the production
  dark/light styles and Segoe UI where available.
- Repository-wide mypy passed for **532 source files**, using
  `artifacts/krt111/mypy-cache`. Ruff, visual policy, complexity policy,
  test-inventory policy, Help inspection, generated schema and whitespace checks
  passed. Reviewed C901 hotspots and their allowances are unchanged.

The focused matrix comprises `test_map_event_anchors`, map temporal visibility,
layer model/cache/view/theme, feature actions/persistence, Relation dialog/
authoring/playhead/custom attributes, temporal authoring/manager/resolver/
precision round trip, calendar/leap, compact date, uncertainty/chronology,
world validator, transfer pipeline, dependency direction and choke-point tests.
All are under `tests/unit`, except `tests/architecture/test_god_module_boundaries.py`.

The additional consumer run exposed an old Context expectation that a provably
reversed interval remained unresolved. The regression now distinguishes that
inactive interval from unreadable evidence, which remains indeterminate. The
existing equal-bound Relation save test now verifies rejection before testing
successful apply/undo with a later end.

### Complete-suite limitation

The following records the original implementation attempt. The owner requested
repair of these blockers on 27 October; current recovery evidence is recorded
in [KRT-112](../krt112/README.md). Its final complete `ci_fast` run passed
**2,721 tests, with 3 skipped**, process exit 0. The original suite blockers
below are resolved; package verification and human review remain separate.

The attempted `ci_fast` run did not complete. It reported 25 setup errors in
unchanged `test_wiki_link_return.py`: a fixture's mocked worker thread reaches
`AuthoringContextCoordinator._bind_connection_browsing`, where Qt rejects the
MagicMock passed to `moveToThread`. This precedes the new map composition.
The run then hit a native Qt access violation in unchanged
`test_connections_overview.py:125`,
`test_connections_stay_one_line_at_narrow_and_wide_widths`. Running that file
alone reproduced the crash after its first three tests.

These observations identify the paths blocking full verification; they do not
establish a clean-baseline full-suite result. No complete push/release preflight
or packaged Windows validation is claimed.

## Rendered and native evidence

Run `python -m scripts.capture_map_anchor_evidence` to reproduce
`docs/_build/krt111/rendered/manifest.json`: 72 current captures across six
themes, Map widths 420/800 and Relation widths 360/800, common, expanded/focus
and disabled states. The manifest defines the current set; older extra captures
are not evidence for this revision. These use production widgets with isolated
settings and disposable Foundation/Destruction snapshots, without a user world.

The narrow dark Map and narrow light Relation expanded captures were inspected.
An initial Relation expansion clipped the new fields. Each field now enters its
final boundary layout once, avoiding stale duplicate layout items; the containing
form scrolls. Enabled/disabled controls
and keyboard focus use shared theme roles. No new local colors or visual-policy
exceptions are introduced.

Run `python -m scripts.build_help`, then
`python -m scripts.capture_help_evidence --output docs/_build/krt111/help --topic
map.visibility --search-inspection`. The narrow dark offline Help capture was
inspected at the actual Temporal visibility heading. The capture helper now
seeks the topic anchor after reflow instead of restoring obsolete pixel scroll.
Search and explanation-popup captures accompany the topic images; the default
popup example is duration, while the automated map-endpoint shortcut test checks
the map-specific excerpt and draft preservation.

The disposable `--native` editor was also exercised through Windows input at
the current OS scale: disclosure, endpoint selection with arrow/Enter, Tab
focus, scrolling to the lower fields, a literal 1e-20 offset and local Enter,
an explicit unrepresentable-offset explanation, and Escape cancellation.
Retained PNGs are under `docs/_build/krt111/native/`:
`end-unresolved.png`, `tab-focus.png`, `tiny-offset-enter.png`. These precede
the final shortened hint and wrapped-field adjustment. They demonstrate the
bounded interactions, not final typography or every supported DPI/text scale.

Generated screenshots and diagnostic caches remain in ignored build/artifact
directories. Source retains the capture scripts and this indexed record. No
artifact cleanup or personal-world replacement was performed.

## Interaction and documentation review

| Review-form field | Record |
| --- | --- |
| Reader and purpose | Worldbuilders choosing fixed versus Event-following presence; maps is a how-to, Relation controls are reference, partial-date discussion is explanation. |
| Canonical pages/release | Maps, Events/Entities/Relations, Timeline/Calendars; Unreleased 0.20.1 worktree. |
| Source identity | Baseline above plus the KRT-111 development checkpoint; commit hash recorded in Linear after commit. |
| Behavior sources | Shared resolver/context/offsets, Map model/view, shared controls, worker-owned command validation, dependency scanner and transfer pipeline. |
| Procedure | Select feature/group, Feature actions or Layers → Visibility dates…, select boundaries, OK; move viewing time to check. Cancel leaves saved attributes unchanged; Undo restores accepted attributes. |
| Authoring contracts | 1/2/3/4/5/6/7/8/9: progressive advanced controls, local Enter/Escape, existing modeless date editor and visible routes, explicit uncertainty, preserved drafts/playhead, shared Map/Relation vocabulary and reversible commands. No contract rule change. |
| Visual roles | Shared dialog/input/scroll-area controls; quiet disclosure, neutral secondary actions, selection/focus roles and semantic error text. Disabled prerequisites remain explained. |
| Preserved context | Event/calendar refresh is presentation; unfinished manual input and unchanged reference metadata survive. Help inspection does not apply the draft or move the playhead. |
| Help identity | Existing map.visibility, relations.timing and date.precision topics/anchors retained. Existing Relation inspection IDs moved to the shared controls; map-specific endpoint/relative/offset/unit/disclosure and scroll excerpts added. |
| Search correction | Partial-date heading clarifies year-only/uncertain wording; its old heading anchor and stable control anchor remain. Existing query regressions pass. |
| Source impact review | Changed binding symbols reviewed individually in docs/help-inspection.json; no blanket fingerprint or visual baseline regeneration. |
| Rendered review | Production Qt captures and offline Help inspected; strict Sphinx passed with this page in navigation. |
| Human prose/live Help approval | Pending; no reviewer supplied. |
| Native Windows scale/theme acceptance | Bounded observations above only; broader supported DPI/text scale review pending. |
| Reader round and independent saved outcomes | Pending; no participant cohort, timing or newcomer-completion claim. |

Use the [documentation review form](../../../developer/documentation-review.md)
and [reader-testing protocol](../../../developer/documentation-reader-testing.md)
for remaining human review. Automated checks do not establish comprehension or
benchmark improvement. KRT-111 stays In Progress for continued feature work
and outstanding owner acceptance after the development checkpoint.
