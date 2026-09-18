# Event and Entity inspector UI verification

Implementation date: 2026-09-18.

## Scope

Both inspectors retain their seven sections, signals, command payloads, and
data storage. Responsive presentation reuses the existing widgets. Text-first
date entry and flexible description width are opt-in; other date and wiki
consumers retain their previous presentation.

The redundant permanent Sections row was removed following design feedback.
A tab overflow menu appears only when needed. Tab context menus expose split
and reset actions; drag splitting is retained. Disclosures use thin,
theme-colored chevrons instead of filled triangles.

## Verified

- 210 focused regression tests passed, covering editors, dates, durations,
  calendars, autosave, unsaved-change guards, splitters, and wiki editing.
- Five additional cases passed for parser-unavailable presentation, preserving
  time when hidden, both start-date anchor modes, and navigation to all tabs.
- Styled layout tests cover both editors at 360, 560, 800, and 1200 logical
  pixels, at heights 480 and 900, including expanded date/generation controls.
- Ruff passed; mypy reported no issues in the nine changed source modules.
- Native Windows Qt captures cover both themes, all seven tabs, four widths,
  and scale factors 1, 1.5, and 2. Representative rendered inspections caught
  and corrected clipped primary controls and a platform-colored Relations
  background. Capture artifacts are local, disposable evidence, not fixtures.

## Interaction budget

These are source-derived action counts, not timed usability-study results.
Typing a value counts as one action; initial state is the Details tab with
optional controls collapsed. Dialog-specific target searches are excluded.

| Task | Previous presentation | New presentation |
| --- | --- | --- |
| Type a basic date | Reveal text input, focus, type, Enter: 4 | Focus, type, Enter: 3 |
| Set one duration component | Focus, type, accept: 3 | Reveal range, focus, type, accept: 4 |
| Change time | Reveal time, focus, type, accept: 4 | Same: 4 |
| Begin linking a relation | Activate Add: 1 | Activate descriptive Add: 1 |
| Open an overflowed tab | Scroll repeatedly, select: variable | Open overflow, select: 2 |

Nonzero durations initially reveal range controls, so editing an existing
duration does not require the extra disclosure action. No advanced capability
was intentionally removed to achieve the simpler basic-date path.

## Remaining acceptance evidence

An interactive desktop walkthrough was blocked by the desktop-control approval
timeout. Native captures and widget tests do not replace that walkthrough.
In particular, manually verify keyboard/screen-reader navigation, populated
relation and gallery states, split panes, long custom calendar names, and
description resizing on the production app. The Qt scale-factor matrix is
not proof of live Windows per-monitor DPI transitions. A comprehensive contrast
audit and formal accessibility conformance assessment have not been performed.

The implementation uses existing theme tokens, typography, icon conventions,
and overflow controls. Control-boundary and keyboard-focus styling is scoped
to these inspectors; it does not claim application-wide WCAG compliance.
