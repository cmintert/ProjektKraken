# KRT-54 — visual vocabulary verification

2026-10-06; implementation based on `78f689b25559d31efc67d453c4bf50199dccdcfa`.
Authority: [visual vocabulary v1](../../visual-interaction-vocabulary.md).

## Contract mapping and routes

Contracts 2/4/5/6/7/8/9 apply. The shared writing toolbar exposes Link to entry,
Open/Peek and destination-oriented Back; compact widths retain the labeled More
actions route, including disabled actions. The inspector header shares the Back
QAction. Supporting Summary/AI disclosures remain below the description, and the
Entity editing-state banner uses neutral mode roles. Rich wiki links use typed
solid underlines; unresolved/ambiguous links use dotted underlines and explanation.
Source mode keeps literal Markdown. Enter/Escape ownership and navigation guards
remain unchanged. No new modal exception or persistent navigation state.

KRT-53 tests cover Save/Discard/Cancel, nested origins, missing entries, world
changes, asynchronous hydration, Focus writing, selection/caret, scroll and
disclosures. New checks cover dynamic/compact/full accessible Back labels,
disabled geometry/overflow, theme switching without undo/draft changes, target
rename/delete refresh and all theme-role contrast pairs.

## Palette inventory and preservation

All pre-existing values in `themes.json` are unchanged. Entity/Event identity
colors, backgrounds and theme primary accents are preserved. New link-text
mappings retain their hue family while satisfying contrast on both surfaces.
New neutral mode/caption/control roles derive their palette identity from each
theme, with their concrete values stored explicitly in the theme definitions.
Quiet normal controls have transparent borders; checked/disabled/focused controls
retain recognizable state without changing geometry.

## Reproducible rendered review

Run `.venv\Scripts\python.exe docs/ux/evidence/krt54/render.py` on Windows.
The script uses production `src/resources/main.qss`, Segoe UI fonts, isolated
QSettings, synthetic Entity/Event snapshots and a small calendar. Unrelated
gallery worker requests are mocked; no world/database is opened or mutated.
Widgets are retained until process completion to avoid unrelated pending-layout
callbacks accessing deleted fixtures.

- `<theme>-<entity|event>-<360|650>.png`: 24 editor captures, widths asserted.
- `<theme>-controls.png`: normal/checked/disabled controls and real hover input
  on the secondary Interaction control.
- `<theme>-controls-pressed.png`: real mouse press on that control.
- `<theme>-controls-focus.png`: real keyboard focus, asserted with `hasFocus()`.

The six palettes are dark, light, fantasy, imperial, cyberpunk and muted light.
Review confirms neutral supporting actions/banners, button-like disabled actions,
typed/unresolved link cues and stable normal/narrow presentation. The control
captures show the same shared state vocabulary in each palette. These are assisted
offscreen renders, not human benchmark timings or live gallery/map validation.
KA-04/KA-20 human comparisons remain separate.

## Gates and adoption

The bounded suite passed **1530 tests, 2 skipped**; see
[raw regression output](verification-ci-fast.txt). Subsequent focused checks
verify the final resolver cache and full accessible destination wording.
Ruff, full mypy (441 source files), test-discovery membership and visual policy
passed. Mypy used an isolated cache because the existing cache contained
incompatible serialized entries. No executable build or database migration.

CI validates explicit roles and contrast, rejects new literals/variants and
stale exemptions, and expires legacy exemptions when a function/method scope or
stylesheet is next touched. Local comparison is against HEAD; CI uses the PR/push
baseline. Formatting/import-only changes do not force unrelated migration.
Reviewed authored-data palette exceptions remain independent of UI theming.
Tests protect this distinction and baseline growth/removal. Guidance and review
requirements are in AGENTS, Copilot instructions, contributing and the project
review skill; Linear and repository vocabulary copies are synchronized.

Static checks do not prove semantic role meaning. Future UI change descriptions
must identify roles/helpers, contract mapping, state/theme/narrow evidence,
preserved context and any explained exception. No automatic visual-baseline
regeneration mode exists.
