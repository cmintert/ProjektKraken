# KRT-53 implementation verification — 2026-10-06

Implementation baseline: `11a35fdb2953aeba167c15e672454bfc888a4ec4`.
This is seeded automated and rendered evidence. It does not measure a human's
time, discoverability or completion rate, and does not complete the historical
partial KA-04 video sequence.

## Behavior and contract

Contracts 2/4/5/7/9: **Link to entry…** is a named writing action with a matching
context-menu accelerator. The existing-entry popup searches Entity/Event
snapshots, preserves the label, disambiguates duplicate names and accepts one
reversible document edit. Single click selects; Link/Enter/double-click accepts;
Escape/Cancel/outside dismissal preserves selection and text. Source syntax
boundaries and unsupported selections receive explanations, without rewriting
unrelated source. Read-only writing cannot insert links.

The shared overflow row stays visible when Focus writing hides formatting.
**Open link** and **Peek link** enable when the caret/selection identifies one
link, including in Source. **Return to writing** is also in the destination
inspector header. Opening and returning reuse Save/Discard/Cancel; delayed or
failed saves do not silently abandon drafts. Discarded text is deliberately not
cached. Origin restoration waits for its applied detail snapshot, restores
view mode, selection, scroll, disclosures and Focus writing, and never restores
old content over current data. Nested link visits return in order; unrelated
navigation/world changes clear the session trail. Missing origins are explained.

Plain mentions, linked mentions and authored connections remain distinct.
Insertion creates neither an entry nor an authored connection. Saving follows
the existing optional derived `mentions` command. Renaming the entry preserves
its UUID and the link's authored label. No schema migration or contract revision.

## Assisted KA-04 and KA-20

Automated scenarios use actual description actions, production editor signal
wiring, real save commands and isolated databases. They cover both origin
types, every Event/Entity navigation combination, Rich/Source round-trip,
rename, save/reopen, command undo/redo, optional mentions, nested return,
cancel/discard/save decisions, newer edits during save, delayed hydration,
context replacement and Focus writing/Peek escalation. The picker never emits
an object-create command.

Human KA-04/KA-20 acceptance remains a later observation: begin with a new empty
world, show the empty state and create dependencies on camera. Record linking,
actual opening/return, unfinished-edit decisions and Rich/Source/save/reopen
separately from this seeded coverage.

## Validation

- Focused authoring/navigation/save/presentation run: **192 passed, 1 skipped**.
  Four unrelated relation tests were explicitly excluded after baseline proof.
- The original wider run was **191 passed, 1 skipped, 4 failed**. All four failed
  identically with committed Event/Entity editor modules loaded in memory:
  `test_event_editor::test_add_relation_flow`, `test_context_menu_actions`,
  `test_entity_editor::test_add_relation_flow`, `test_edit_relation_flow`.
  They expect modal add/edit entry points replaced by KRT-22's inline authoring;
  they have no `ci_fast` membership and were left unchanged.
- Final bounded `ci_fast`: **1,502 passed, 2 skipped**, 54.69 seconds.
  [Retained output](verification-ci-fast.txt). One existing FastAPI/Starlette
  deprecation warning. All 50 new acceptance cases have explicit `ci_fast`
  membership; the updated collection baseline passes with zero added/removed
  tests pending review.
- Final repository Ruff and full-source mypy pass (437 modules). After the wider
  focused run, the completion/Source-click checks passed with all KRT-53 cases
  (**55 passed**); focused results-list Enter acceptance and all local authoring
  cases then passed (**26 passed**). The final bounded suite includes both.
- No executable build or world-data repair was performed.

## Rendered evidence

Run `.venv\Scripts\python.exe docs/ux/evidence/krt53/render.py` from the repository
root. It loads Windows Segoe UI fonts explicitly, uses temporary QSettings and
opens no world/database. The PNGs are cropped shared writing controls/picker
captures using production themes, not full application screenshots.

| Theme / width | Selection | Existing-entry picker | Linked / return controls | Formatting hidden |
| --- | --- | --- | --- | --- |
| Dark 360 | [Selection](dark_mode-360-selection.png) | [Picker](dark_mode-360-picker.png) | [Linked](dark_mode-360-linked.png) | [Writing tools](dark_mode-360-writing-tools.png) |
| Dark 650 | [Selection](dark_mode-650-selection.png) | [Picker](dark_mode-650-picker.png) | [Linked](dark_mode-650-linked.png) | [Writing tools](dark_mode-650-writing-tools.png) |
| Light 360 | [Selection](light_mode-360-selection.png) | [Picker](light_mode-360-picker.png) | [Linked](light_mode-360-linked.png) | [Writing tools](light_mode-360-writing-tools.png) |
| Light 650 | [Selection](light_mode-650-selection.png) | [Picker](light_mode-650-picker.png) | [Linked](light_mode-650-linked.png) | [Writing tools](light_mode-650-writing-tools.png) |

Return availability in these isolated renders represents the state while a
bookmark exists; the separate integration tests drive real navigation. At 360px,
Open/Peek move into More actions while Link and Return remain directly visible.
The picker is constrained to the current screen; duplicate rows show kind and
distinct ID portions. Labels/buttons are readable in both themes. Offscreen Qt
does not establish native popup mouse-grab behavior on Windows.
