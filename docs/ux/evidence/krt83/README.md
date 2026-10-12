# ProjektKraken writing-editor presentation — KRT-83

2026-10-12. Base: clean `main`, `9496ffbe5ff0a97f1f360916d2e966a5d9c7d513`.
Implementation is local and uncommitted. No branch, commit, push or pull request was created.

The user requested a different appearance while retaining existing functionality.
WikiTextEdit remains the editor. The traditional menu/formatting/secondary hierarchy
uses Kraken's palettes and locally bundled Phosphor Regular SVGs.

## Final presentation

- A text-like **Edit / Insert / Format / View / Tools** menu row.
- A naturally sized **Headings** selector and compact Bold, Italic and Clear
  Formatting icons. Each formatting icon has its full accessible name and a
  tooltip containing its existing shortcut. Full names also appear in Format.
- A flat secondary strip for Link to entry, Open link, Peek link and inspector
  Focus writing. Disabled Open/Peek remain discoverable, with readable subdued
  text and prerequisite explanations.
- The duplicate More writing actions control is removed. Menu-row and secondary
  overflow remain labeled More actions. At constrained widths formatting commands
  remain reachable through Format, without partially displayed controls.
- Project New, shared overflow, inspector corner More actions, relation More
  actions and Sheet overflow use the same small, spaced, theme-aware caret.
  Project and ordinary overflow retain their existing secondary button role.

The former Body command is labeled **Clear Formatting** because its existing
handler clears heading/bold/italic formatting. Its handler and shortcut are
unchanged. No new Body operation or formatting behavior was introduced.

## Preservation evidence

`preservation-and-assets.json` verifies identical syntax trees for the entire
WikiTextEditView, ResizableWikiTextEditField and FocusWritingController classes,
and for icon_loader.py, against the base revision. This protects the existing
formatting handlers, shortcuts, rich/source conversion, caret/selection paths,
link behavior, spell-check lifecycle, splitter and Focus enter/exit logic.
Shared QAction instances are presented in menus; native QTextEdit commands power
the Edit menu. No storage, schema, command, worker or coordinator behavior changed.

The centered writing column remains bounded at 760 logical pixels. Final
Entity/Event captures at requested widths 360 and 1200 measure column widths
302 and 760 respectively, with zero horizontal scroll in every captured palette.

## Local assets

Only three missing official Regular icons were downloaded: `text-b.svg`,
`text-italic.svg` and `caret-down.svg`. Kraken's existing eraser.svg is reused
unchanged. Runtime loading uses icon_loader.py and currentColor recoloring.
There are no network icon references in the UI.

The exact upstream revision, URLs and SHA-256 hashes are recorded in
`default_assets/icons/ui_icons/editor-icons-provenance.json`; the official MIT
license is bundled as `PHOSPHOR-LICENSE.txt`. Downloaded SVG bytes are unchanged.
[Official Phosphor source](https://github.com/phosphor-icons/core).

## Verification

- Final fast gate: **1,919 passed, 2 skipped**, `ci-fast-final.xml`.
- Editor/caret/inspector/creation regression group: **106 passed**,
  `final-focused.xml`; the two obsolete inspector fallback assertions were
  subsequently updated and passed against the new View menu.
- Final icon/layout and detector regressions: **63 passed**,
  `final-icons-layout.xml`, including genuine clipping detection and the
  natural-width selector/tooltips check.
- Bounded affected-surface audit: **60 records, zero failures**,
  `label-audit-verified/scale-1.0/report.json`. Covers WikiTextEdit, Entity/Event,
  Project, shared overflow and the splitter inspector at the audit's quick widths,
  normal/disabled states and selected text factors in dark mode.
- Ruff, focused mypy on nine source files, visual policy and complexity policy
  passed before the final responsive placement/detector refinement. Final
  applicable checks are recorded separately in verification.json.

The fast gate ran before the final compact-row and detector refinement; the
63-case final targeted group and final affected-surface audit cover those changes.
Earlier failed audit reports are retained as intermediate evidence and are
superseded by `label-audit-verified`.

Seven failures in a broader non-fast selection were reproduced against the
original baseline: six stale style-helper assertions and the Entity repeated
Focus restoration size assertion (659 to 673 pixels). Those unrelated behavior
or legacy test changes were not included. No claim of a full test-suite pass.

## Rendered evidence and limits

`before/` uses the original presentation modules from the base revision.
`after/` renders the production widgets with the installed Windows fonts and
production stylesheet. All six existing palettes are represented. Inspector
captures use supplied models with queued worker calls stubbed, leaving world data
untouched. `after/captures.json` contains dimensions and scroll measurements.

These are actual Qt offscreen renders, not design mockups. They establish layout
and theme appearance; they do not establish native OS-DPI or human benchmark
acceptance. The user's supplied live application screenshot informed revisions;
the running source state of that screenshot was not independently established.
KRT-45/KRT-81 acceptance remains separate.

## Contracts and bounded PR sequence

Contracts 1/2/5/6/7/8/9/11 apply. Styling is centralized in StyleHelper using
existing quiet, secondary, surface, border, text and focus roles. The compact
writing strip is a user-requested contextual variation of the ordinary secondary
toolbar presentation: quiet enabled chrome and flat disabled link controls.
Menus retain full action labels, and focus/hover states remain visible. No theme
colors were changed and no competing interaction contract was introduced.

If published as sequential PRs, use these review boundaries:

1. **Editor presentation:** menu hierarchy, flat compact controls, existing action
   reuse, accurate Clear Formatting label, local formatting/caret assets, inspector
   Focus placement and writing regression coverage.
2. **Shared caret adoption:** Project New and shared/direct More routes using the
   same local caret, retaining their existing secondary roles and native menu
   handling; verify creation shortcuts, relation routes and inspector overflow.
3. **Evidence and gate maintenance:** rendered matrix, registered presentation
   owners, detector correction for unpainted icon action-name metadata, meaningful
   positive/negative checks and documentation. Do not weaken label thresholds.

These are planned review boundaries, not existing pull requests. KRT-83 remains
In Progress until the implementation is verified and committed. Publication and
delivery steps need their own authorization.
