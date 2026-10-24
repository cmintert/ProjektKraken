# KRT-94 keyboard navigation evidence

2026-10-24. Evidence captured from the working tree based on `32259a2d`.
The exact local delivery commit is recorded in Linear KRT-94. Commit and push
are separate delivery actions. Contracts 2/5/6/7/8/9 apply. The keyboard
interpretation is synchronized with the authoritative Linear contract.

## Decision and implementation

Tab/Shift+Tab wrap in the current visible pane's tab strip and active panel.
Nested inspector sections remain local. F6/Shift+F6 cycle rail, left, center,
right, bottom, skipping unavailable regions and remembering eligible controls.
Focus alone never activates another workspace. Native table cell editing,
dialogs, menus and Help retain ownership. Focus writing contains Tab; F6 exits
that presentation deliberately.

All WikiTextEdit consumers share non-mutating plain Tab in Rich/Source and
read-only views. Completion dismisses on Tab and accepts the highlighted entry
on Enter. Source-only menu commands retain deliberate indentation/literal tabs
with local undo. No database, worker, command-history or world-schema change.

Presentation reuses existing quiet/secondary controls and `focus_ring`,
`selection_bg`/`selection_text` and disabled action roles. No new local colors,
style variants or visual-policy exceptions were introduced.

## Native observation, separate from owner reports

Computer Use skill, one Windows desktop session:

- The existing Northwatch Demo window reported application revision `32259a2d`.
  Clicking the Entity name, Shift+Tab reached the current tab close control;
  another Shift+Tab reached Save Changes. Tab returned through the active tab
  header and close control. No workspace/layout activation was observed in this
  bounded route. Existing world content was not edited by these actions.
- This does **not** reproduce the original report of Tab inserting text or
  establish its historical cause. The 2026-10-18 report remains owner-reported.
- `python -m tests.manual.krt94_keyboard_probe` launches an isolated production
  shell with temporary settings, in-memory Entity/Event data and a mocked database
  worker. It opens no world. Its close guard is bypassed only in this test harness.
- In the disposable description, Tab moved to Summary with the visible paragraph
  unchanged. F6 moved to Analysis; Shift+F6 restored Summary. In Focus writing,
  Tab remained in the writing surface, and F6 exited it and moved to Analysis.
- In the final dark-theme probe, typing ` [[Alp` opened Alpha/Alpine suggestions.
  Tab dismissed the popup, kept `[[Alp` unchanged and focused Summary. The Format
  menu showed disabled Indent/Outdent in Rich view.
- Switching to Source enabled Indent/Outdent. Native menu use exposed a missing
  focus return after a source command; it was corrected. In the restarted final
  probe, Indent returned keyboard ownership to the text view and one Ctrl+Z
  restored the original paragraph. Delivered-key tests cover all three commands.
- F1 opened the writing task in native offline Help. The new indentation section,
  command permissions, undo/save explanation and canonical excerpt were readable;
  Escape returned to the unchanged writing origin.

Requested client size was 1600 × 900. Native captures were observed through
Computer Use; there is no claimed native DPI/text-size matrix or participant
timing comparison. The first app-access request timed out; the later retry
succeeded. A disposable harness initialization failure was corrected by avoiding
a mock on the Qt class itself; it was not a product launch failure.

## Automated verification and artifacts

- Focused keyboard suite: 41 cases. Delivered Qt keys cover six presets,
  forward/reverse wrapping, F6 restoration, hidden/disabled/inactive controls,
  moved/closed/restored/collapsed regions, completion Tab/Enter, rich/source,
  source commands, Unicode/reverse selections, table delegates, modal/Help
  ownership, scrollable fields, Focus writing and a real production inspector.
- Earlier completion/toolbar/workspace group: 99 passed.
- Production workspace suite: 8 passed after aligning the two stale KRT-108
  expectations below. Help/architecture/summary group: 170 passed; the single
  stale fingerprint detected during the native fix was corrected and its
  isolated generation/bounds regression passed on rerun.
- Final Help generation/bundle regressions: **23 passed / 1 skipped** after
  placing the keyboard guidance within the existing workspace F1 task.
- Six themes × 1600/1280 widths with a narrow center pane: 12 captures, plus
  writing-state assertions. Windows Segoe UI was explicitly registered for
  readable offscreen output. Initial missing-font captures were superseded.
- Generated captures: `tmp/krt94-font-render/`; reviewed contact sheet:
  `tmp/krt94-contact-readable.png`. These are local, ignored artifacts. They show
  rendered focus/theme behavior, not independent native readability acceptance.
- Full `ci_fast`: **2,589 passed / 3 skipped**, 583.45 seconds, in
  `tmp/krt94-ci-fast-final.log`. The earlier run found a Help fingerprint being
  updated during the native correction; the frozen rerun passed.
- Final panel-move focus restoration correction: **91 keyboard/workspace tests
  passed** after the full run's collection. This adds the moved-control case
  and preserves the coordinator's valid restored focus rather than sending it
  back to the old region. The complete broad suite was not repeated for that
  bounded correction.
- Native observations preceded that final panel-move repair. Its preservation
  of restored focus is automated evidence, not an additional native observation.
- Ruff, changed-file formatting, repository-wide mypy (509 source files),
  visual/complexity policies, inspection inventory, offline Help generation,
  schema generation check and strict Sphinx passed. Logs remain under `tmp/`.
- Manual browser render: isolated headless Chrome via Playwright, 1280 × 900,
  workspace keyboard section and writing source-edit section. Headings, wrapping,
  sidebar navigation and command prose were inspected. Captures and CLI logs
  remain under `output/playwright/` (ignored). A temporary localhost server
  exposed only `docs/_build/html` and was stopped after review.

The production workspace regression tests were aligned with already-delivered
KRT-108 behavior: View opens individual panels, and Reset uses an initialized
workspace collection plus explicit confirmation. Their previous references to
the removed panel-launcher rail and uninitialized reset were stale.

## Documentation review record

| Field | Record |
| --- | --- |
| Reader/task | Authors using keyboard navigation and deliberate source indentation |
| Diátaxis purpose | Workspace explanation/how-to; writing how-to; shortcut reference |
| Release/source | v0.20.1 checkout based on `32259a2d`, KRT-94 working tree |
| Canonical pages | Workspace, Wiki editor Markdown and links, Keyboard Shortcuts |
| Inspected behavior | Focus controller, completion dispatcher, source commands, production composition |
| Topics | `workspace.navigation`, `writing.edit`; existing meanings and anchors retained |
| Added excerpts | `help-inspect-workspace-focus-region`, `help-inspect-writing-source-edit` |
| Persistence | Focus changes do not save; source edits use local Undo and existing Save Changes |
| Source review | Individually recorded Help fingerprints and matching explanations |
| Rendered manual/offline Help | Browser manual at 1280 × 900 and native dark Help reviewed; source-edit instructions and anchors remain readable |
| Human prose/live Help approval | Owner approved “Indent source without using Tab” through F1 from the description: “Yes, I approve it.” This approves that section, not an independent review of the whole manual. |
| Reader-performance study | Not performed; no newcomer or timing claim |

## Owner acceptance

The bounded guided native question-and-answer review is complete. Owner reports
are recorded separately from the independent observations and automated checks
above. The earlier step-by-step pending dispositions are superseded by this
completed record.

- Entity panel Tab/Shift+Tab: owner answered **“Yes, both directions work”** to
  whether traversal stays inside the Entity panel without changing its
  description.
- Region movement: owner answered **“Yes, both work”** to whether F6 moves to
  the next visible panel region and Shift+F6 returns to the previous control.
  This accepts that bounded movement/restoration route.
- Completion dismissal: owner answered **“Yes, it works”** after typing
  ` [[Alp` and pressing Tab: suggestions dismiss, focus moves and the typed text
  stays unchanged.
- Completion acceptance: owner answered **“Yes, it works”** after opening
  suggestions with ` [[Alp`, highlighting an entry with an arrow key and
  pressing Enter. The selected wiki link is inserted.

- Focus writing traversal: owner answered **“Yes, both directions work”** to
  whether Tab/Shift+Tab stay within the writing surface without changing text.

- Focus writing exit: owner answered **“Yes, it works”** to whether F6 exits
  Focus writing, moves to another visible region and preserves the draft.

- Source indentation/undo: owner answered **“Yes, it works”** after choosing
  View → Markdown source, Format → Indent and one Ctrl+Z. This accepts the
  bounded source-menu-to-keyboard-undo route.
- Contextual Help: with the description focused, the owner pressed F1 and
  reviewed “Indent source without using Tab,” answering **“Yes, I approve it”**
  to whether the explanation is clear and accurate.

This is owner-reported acceptance of the listed routes and the named Help
section. It does not establish exhaustive native DPI coverage, an uncoached
participant study, or native observation of the final panel-move repair.

Implementation verification and bounded owner acceptance are recorded. The owner
authorized the local delivery commit using already-passed tests. The exact hash
and delivery status are recorded in Linear KRT-94 after committing. Verification
is reused; no test rerun or push was requested for delivery. Normal commit hooks
remain enabled.
