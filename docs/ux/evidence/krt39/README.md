# KRT-39 — Spell-check ownership and lifecycle

Comparison base: `4ce41c0ad94a07e82ab7a773d7cf7264a7847920`.

## Ownership and compatibility

Before: WikiTextEditView owned the 800 ms debounce, lazy LanguageTool worker,
settings reads, request/result state, underline rendering and spelling actions.
The settings dialog also lived in the editor module.

After: one GUI-local `SpellCheckController`, parented to the text view, owns that
capability. Its editor dependency is a standard `QTextEdit`; it imports no wiki
conversion, completion, app orchestration, commands or persistence. WikiTextEdit
retains context-menu composition and wiki-link actions. `SpellCheckSettingsDialog`
has a dedicated module and remains importable from the original location. Public
editor methods/signals, QSettings keys/defaults, five-suggestion ordering, Ignore,
HTTP behavior and Markdown/rich-text conversion remain compatible.

Only detached text/settings and matches cross explicitly queued Qt connections.
Request identity, settings generation, rendered plain text and document revision
guard results. Edits, document replacement, settings changes, disable and shutdown
invalidate old work. Read-only replacements are disabled and cannot mutate text.
Menu actions retain match identity, so a stale action cannot target an equal fresh
match. Ignore does not edit text or undo history; replacement uses ordinary undo.

Close, application exit, direct view destruction and parent destruction stop
scheduling and join the worker without accessing the dying editor. A surviving
closed view can resume on show. The existing wait for an active HTTP request is
retained; no forced termination or new cancellation policy is introduced.

Theme changes recolor transient underlines with the existing `error` role. Qt's
highlighter can advance its revision during presentation-only refresh; valid
match revisions are refreshed and obsolete in-flight revisions are rechecked.
Authored text, caret, selection, scroll, modified state and undo remain intact.

## Automated verification

Verification outputs are retained under ignored `artifacts/krt39/`:

- Final `pytest -m ci_fast -q`: **2,359 passed, 3 skipped**
  (`ci-fast-complete.txt`). The only warning is the existing Starlette/httpx
  test-client deprecation warning.
- Focused editor, controller, LanguageTool, link authoring/return, toolbar,
  rendering, Help and dependency regressions: **279 passed** (`focused.txt`).
  The controller/spelling subset has **47 passing cases**, including real
  in-flight work during QObject/parent destruction, application exit, blocked
  widget signals, stale menus and settings integration (`controller-final.txt`).
- Repository-wide mypy: **490 source files clean** (`mypy.txt`). Ruff and
  changed-file formatting pass; complexity, visual policy and Help inspection
  checks pass. No baseline exception was added or raised.
- Strict Sphinx HTML build passes; rendered evidence/navigation and architecture
  links were inspected. The reproducible capture matrix is described below.
- `source-hashes.json` identifies the final production/render/Help inputs.
  Earlier partial suite logs were superseded after the final lifecycle change;
  they are retained and are not counted as completed verification.

The extraction has no reviewed C901 allowance. The existing complexity policy
passes against the comparison base; no allowance IDs, ceilings or suppressions
need modification. Dependency tests restrict the controller to theme/Help and
LanguageTool collaborators and prohibit spelling state/thread ownership in the
view. The view's context-menu complexity decreased **6 → 4**. Extracted
controller methods measure at most **5**; the relocated dialog measures at most
**2**, below the normal complexity limit of 15 (`callable-complexity.json`).

An existing theme test asserted that theme changes rewrite saved HTML. It fails
identically with the base revision (see `baseline-rerender.txt`). Its updated
assertions verify actual transient layout colors, unchanged HTML and unchanged
undo history, consistent with the established editor presentation contract.

## Presentation and acceptance boundary

Contracts **2/5/6/7/8/9/11** apply. **Tools → Spelling settings**, including narrow
overflow, remains the visible configuration route; right-click suggestions and
Ignore remain accelerators. Enter/Escape retain focused-control/dialog ownership.
Settings use shared primary Save, secondary Cancel and shared input/focus styles.
Underlines use `error`; selection and focus retain shared semantic roles. No
interaction-contract revision, local color, new visual exception or dimension
increase was introduced.

The [renderer](render.py) captures six shipped themes × requested 360/800 px widths
for enabled, disabled, read-only and source editor/context-menu states, plus
enabled/disabled settings dialogs. All **120 pairs** use isolated settings,
synthetic text, loaded Segoe UI/Consolas fonts and mocked HTTP; no world is opened.
Editor widths actually reach **360 and 800 px** using production adaptive width.
The existing settings-dialog minimum is **400 px**, so requested 360 px dialog
captures record 400 px actual width; this minimum was not changed.

**108 pairs are byte-identical.** The 12 differences are read-only menus: spelling
replacements are now disabled while remaining visible; Ignore and ordinary menu
actions retain their behavior. Captures/manifests are in `before/` and `after/`,
with `render-comparison.json` recording the comparison.

These are offscreen component captures at DPR 1, not native Windows acceptance,
OS/text-scale coverage or human task-time evidence. Native Contract 11 review at
100/125/150/200% OS and independent text scales remains unperformed and is not
claimed. KRT-39 remains open while uncommitted; no release sign-off is implied.

Reproduce from the repository root:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m docs.ux.evidence.krt39.render --output artifacts/krt39/before --baseline-ref 4ce41c0ad94a07e82ab7a773d7cf7264a7847920
python -m docs.ux.evidence.krt39.render --output artifacts/krt39/after
```
