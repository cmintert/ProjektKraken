# KRT-55 Settings Center implementation evidence

Implementation date: 2026-10-24. Starting revision:
`bf7335de7c4f1b351e932ef538dcaad86f520ad3`. The owner authorized the delivery
commit using already-passed verification. The delivery commit references
KRT-55; the issue remains open for native acceptance. Push is not authorized.

## Implementation and boundaries

One modeless Settings Center contains the actual configuration controls.
The owner's follow-up replaces the Settings dropdown with one direct menu-bar
action and removes the alternative AI, backup, appearance, calendar, grouping,
graph-style and spelling configuration launchers. Spelling checking remains
an immediate inline toggle, as do Snap to Events and editorial checks. File,
colour, icon and prompt pickers remain subordinate interactions. No production
route constructs the retired settings dialog shells.

The registry classifies local preferences, portable world configuration and
credentials. Calendar contents, tag colours and task templates are authored
resources, excluded from generic resets. Named layouts, brush presets, history,
world registrations and trust remain outside preference resets. Workspace
geometry, active selections, filters and playhead are transient state; their
separate reset is scheduled for startup. Backup creation/restoration, world
management and index rebuilding remain explicitly invoked operations.

Widgets emit intent. The coordinator owns drafts and backend acknowledgements;
the snapshot endpoint shares the database thread with explicitly queued signals.
World Apply uses one transactional command, expected-value checks and exact undo.
Local preferences and OS credentials report separate outcomes. Migration records
retain provenance; resets cannot reimport legacy policies.

The populated-world regression fixes Northwatch's reported false unavailable
state: tag enumeration does not include colours, so snapshot loading now reads
them through the repository API. The active world name is shown while loading.
A read-only snapshot of Northwatch succeeded; that diagnostic did not write it.

## Interaction and presentation review

Relevant authoring contracts: **1–3, 5–9 and 11**. Opening settings preserves
the original authoring widget instances; applying configuration refreshes derived
consumers without reloading editor content. Explicit Apply, OK and Cancel own
settings acceptance. Close and world transitions protect drafts. Focused inputs
retain Return; Escape reaches subordinate interactions before the Center's
pending-edit guard. Existing map transition protection remains in the route.

Controls use shared StyleHelper presentation: Apply is primary, navigation and
supporting actions are secondary, and pending/customized/conflict text states
name their meaning. Native dialog base styling supplies the window surface and
text roles. Scope captions explain local dependencies and world portability.
Narrow windows stack category navigation above the scrolling content.

Offscreen captures cover every page in all six themes at requested logical
sizes 960 × 680 and 700 × 600, plus disabled/focus captures. The manifest records
actual sizes, font size, device pixel ratio and physical capture dimensions.
Inspected captures include world Timeline, narrow world AI/Graph, local
Writing/AI/Advanced and disabled Writing across all six themes;
review corrected actual embedding, deep links, dark surface contrast and
oversized reset controls. These are automated renders with agent inspection,
not native Windows or human acceptance.

The action-label audit covers the SettingsCenter surface at Qt scale factors
1.0, 1.25, 1.5 and 2.0, four text scales, six themes, narrow/normal widths and
pseudo-localized labels. The final report is recorded below. An earlier run
invalidated by a source change is superseded; its result is not acceptance.

## Automated verification

| Check | Result |
| --- | --- |
| Focused settings, dependency and architecture checks | 80 passed; includes 32 settings regressions |
| Full `ci_fast` | 2,520 passed, 3 skipped; 4508 deselected |
| Smoke | 19 passed |
| Ruff | Passed for src, scripts and tests |
| Repository-wide mypy | Passed, 503 source files |
| Complexity policy | Passed; no touched reviewed C901 allowances or ceiling increases |
| Visual policy | Passed; baseline unchanged |
| Help declarations and fingerprints | Passed |
| Offline Help and strict Sphinx | Passed |
| SettingsCenter action labels | 9,984 measurements, zero label failures; all four reports match current presentation sources |
| Direct Settings action and removed launchers | 99 focused tests passed, including settings, menus, graph and spelling |
| Graph and writing entrypoint rendering | 16 measurements, zero failures; process exit 0 |

Settings tests cover draft retention and Cancel, validation before writes,
backend failures and retryable drafts, acknowledgements, external conflicts,
stale snapshots, world-only Apply preserving local drafts, migration idempotence,
two world policies and portable copies, transactional rollback, exact undo,
credential-store failure, reset preservation, real queued worker ownership,
populated tags, calendar absence, graph style preservation, embedding and
keyboard ownership. Existing consumer regressions cover WikiLinks, editor
coordination and timeline snapping.

The full `ci_fast` pass preceded the final surface/wording and availability
corrections; the 80-test focused run and static checks cover those later changes.
The owner-requested navigation simplification additionally has the 99-test
focused run. The owner requested committing with already-passed tests, so the
subsequent broad rerun was stopped and is not claimed as another pass.

The four rendering reports contain all 2,496 records per scale with no source
drift or label failures. The parent runner recorded exit 120 for three child
processes after their reports completed; that process shutdown anomaly is
retained in `action-summary.json` and is not presented as a clean runner exit.
The independent graph/writing audit exited successfully. Six-theme menu-bar
captures verify the single visible Settings action without a submenu.

Reproduction commands, with `QT_QPA_PLATFORM=offscreen` for Qt checks:

```text
python -m pytest tests/unit/test_settings_center.py tests/architecture/test_god_module_boundaries.py tests/unit/test_dependency_direction.py -q
python -m pytest -m ci_fast -q
python -m pytest -m smoke -q
python -m ruff check src scripts tests
python -m mypy src
python -m scripts.check_complexity_policy
python -m scripts.check_visual_policy
python -m scripts.check_help_inspection
python -m scripts.build_help
python -m sphinx -n -W --keep-going -b html docs docs/_build/html
python -m scripts.capture_settings_evidence
python -m scripts.check_action_labels --surface SettingsCenter --matrix full --report-dir artifacts/krt55/action-labels-delivery
```

Ignored local artifacts live in `artifacts/krt55/`: `checks` contains command
logs, `rendered` contains captures/manifest and `action-labels-delivery`
contains the final matrix. Superseded audit outputs are retained in a compressed
archive. Preserve these artifacts until review; captures are reproducible from
the script and do not contain personal credentials or world content.

## Documentation review

The primary user purpose is how-to with a scoped settings reference in
`user/workspace.md`. AI, spelling, timeline/calendar, backup and troubleshooting
procedures use the direct Settings route and its acceptance actions. Removed
control bindings are retired; their existing documentation anchors remain as
destinations pointing to current pages.
The new topic is `settings.center`; existing topic IDs and anchors are retained.
Source review traced widgets, coordinator, adapters, command, secret handling,
index consumers and tests. Help source fingerprints were reviewed individually.
The changelog records the implemented behavior. Builds validate structure and
links; they do not establish reader performance.
Generated offline Settings Center Help was inspected at 700 and 960 logical
pixels, including the scope table and Apply/Cancel procedures. Captures are in
the rendered artifact directory. Human prose and live Help approval remain open.

## Remaining acceptance

Native Windows review is **Pending**, including the required scaling matrix,
keyboard focus/disabled readability, modal ownership and subordinate Escape,
editor draft/caret/selection/scroll preservation, playhead, and live map sessions.
Human prose and live Help approval are **Pending**. No independent reader study
or owner acceptance is claimed. Package/release preflight was not run. The issue
must not be marked Done before coherent committed delivery and its required
verification/acceptance.
