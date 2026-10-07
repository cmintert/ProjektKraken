# KRT-56 verification — 2026-10-07

Implemented Longform gesture ownership, source-aware inspection, explicit
Connections drop drafts and identity-based relation-row merging.

## Automated evidence

- Initial focused acceptance: 146 passed (Longform, workspace, navigation,
  Connections, commands and signal wiring).
- Final drop framing, Escape and identity-change checks: 56 passed.
- Final fast suite: 1,636 passed, 2 asset-dependent skips in 98.18 seconds.
  The explicit-link origin regression was added afterwards. The subsequent
  navigation/link integration run passed its other 59 tests; that new test's
  first attempt failed because its Entity fixture omitted the required type.
  After correction, all 10 document gesture/navigation tests passed, including
  explicit-link save continuation cancellation. No outstanding automated failure.
- Ruff: clean. Mypy: clean across 444 source files. Test-discovery, visual and
  complexity policies: clean. No reviewed C901 hotspot was executable-touched;
  complexity ceilings and the visual baseline remain unchanged.
- Thirty-four new collected ci_fast cases cover both inspectors and document
  gestures. Existing advanced relation timing, custom attributes, command replay
  and undo semantics remain covered by the fast suite.

The tests deliver Qt pointer, keyboard and drag/drop events to production
widgets. QDrag.exec is replaced by an event-loop wait for deterministic
cancelled-drag tests. SQLite command verification uses disposable test databases.
These checks do not constitute a native desktop drag walkthrough or a human
usability benchmark.

## Rendered evidence

`render.py` uses the production main stylesheet, shared StyleHelper controls,
real Entity/Event inspectors and Longform view, and installed Segoe UI fonts.
Settings are redirected to a disposable INI directory. It opens no world.

Run from the repository root:

```powershell
.venv\Scripts\python.exe docs/ux/evidence/krt56/render.py
```

The themed `entity-*.png` and `event-*.png` images show prepared directed drafts
in all six themes; `*-narrow.png` and `*-disabled.png` show wrapping, overflow and
disabled Connect while retaining Cancel. `longform-no-selection.png` shows the
disabled Open prerequisite; `longform-narrow-selected.png` shows the visible
selected-entry action and its focus boundary. `render.json` records image sizes
and Connect availability.

Inspection verified readable endpoint direction, a visibly bounded labeled drop
target, shared action borders/focus, readable disabled controls and available
Connect/Cancel at narrow widths. The draft uses neutral mode-information roles;
object identity colors remain in document content. No local color variant was
introduced.

## Native check limitation

The computer-use skill's native helper returned:

`Computer Use native pipe is unavailable: failed to connect native pipe: The system cannot find the file specified. (os error 2)`

The initial call, delayed retry and fresh-kernel recovery all failed. No native
input was sent. The remaining acceptance item is a real desktop walkthrough in
a disposable world: shared/separate/moved zones, slow held presses, internal
reorder, external drop, Escape and draft-save continuation. Do not claim that
native pointer/focus behavior or human improvement was verified by these renders.

## Delivery state

User documentation, audit E-01, the KRT-22 plan and the repository/Linear contract
interpretation were synchronized. Commit and push were authorized on 2026-10-07.
KRT-56 stays In Progress because the native walkthrough remains outstanding.
No executable build or production-world repair was performed. Existing accidental
self-relations display once by UUID; their persisted records are preserved.
