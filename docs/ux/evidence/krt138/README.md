# KRT-138: Timeline grouping tag refresh

Verified 2026-11-03. Native owner acceptance and human task-performance review
have not been recorded.

## Behavior and scope

Settings Center reconciles grouping rows on every accepted world snapshot.
Existing rows retain widget identity, selected order, checkboxes, keyboard focus
and staged colours. Counts refresh, new tags appear unchecked, and unused
unchecked rows disappear. Selected or configured tags remain visible at count
zero when they have no matching events, preserving saved and pending grouping.
Saved ordering moves model rows without destroying their widgets.

Embedded rows include the shared stylesheet's padding and border metrics in
their height, including after deliberate Up/Down ordering. Event counts are
retained in row state as well as the visible label.

The visible Settings Center route, grouping modes, checkboxes, Up/Down actions,
Apply/Cancel boundaries and command-based Undo remain. Contracts 2/5/6/7/8/9
apply. Rows reuse the existing controls and shared application QSS; no local
stylesheet or policy exception is added. Stored tag colours retain their authored
meaning; unavailable configured tags use `event_main` as the fallback event-group
identity until a stored colour is available. No interaction contract is revised.

## Automated verification

- `pytest tests/unit/test_settings_center.py tests/unit/test_timeline_grouping.py -q`:
  **56 passed**, using the checkout environment and offscreen Qt.
- Regressions cover empty-to-populated snapshots, reopening the existing view,
  count updates, tag additions/removals, selected unavailable tags, staged colours,
  grouping mode/order, focused checkbox identity, unrelated pending settings,
  saved row ordering with deferred deletion, styled row geometry and Apply/Undo.
- Ruff checks and formatting checks passed for the changed Python files.
- Repository-wide mypy: **603 source files**, no issues.
- Visual policy and complexity policy passed; no reviewed C901 hotspot touched.
- Git whitespace check passed.

## Rendered review

[Theme and width contact sheet](grouping-refresh-themes.png) uses production QSS,
Segoe UI, detached tags and non-persistent theme changes. Reviewed all six themes
at 420 and 800 pixels: labels/counts fit, the disabled Up action remains visible,
and selected/check states and grouping modes remain. Geometry assertions verify
label height before and after deliberate reordering in all 12 combinations.
Keyboard focus preservation is established by the focused regression test;
offscreen renders do not establish native focus appearance or human usability.

World data was inspected through a read-only connection during diagnosis and was
not modified. Existing unrelated timeline presentation changes were preserved.
