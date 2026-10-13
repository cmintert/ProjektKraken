# KRT-87 contextual Help implementation evidence

Date: 2026-10-13. Implementation verification is recorded below; commit delivery
and issue status are tracked in KRT-87. This implements the F1/viewer portion of the
[Expert Assistance contract](../../expert-assistance-contract.md), applying
authoring Contracts 1–9 and 11. Search and Inspect control remain KRT-88;
canonical prose sign-off remains KRT-89 and full package/human acceptance KRT-91.

## Delivered behavior

F1 and Help → Help for current task resolve registered controls, surface-local
operations, dialogs, panels and manual home in that order. Semantic ownership
survives F11 reparenting. Help → User manual provides direct manual access.
The reusable non-modal companion has Back, Forward, Manual, Refresh context and
Return to work. Closing or Escape returns to a surviving origin without restoring
stale editor snapshots. Navigation and reading positions belong only to Help.

The existing validated offline bundle supplies content, anchors, related topics
and images. The reader rejects external resources, escaped paths and invalid
fragments. Invalid bundles show local recovery guidance; reopening or refreshing
can retry. No world database or command dependency is introduced.

Supported dialogs notify before Qt completion; Close and DeferredDelete guards
detach Help before owner teardown. Window-level tests establish input delivery
under application modality. Help-owned keyboard input bypasses global world
undo/redo, creation, trajectory operations and F11 exit handling.

Date fields normally validate on focus loss. The Help origin is temporarily
marked so queued focus loss into the Help menu/window cannot accept a draft.
Returning to authoring clears that mark; ordinary Enter validation still works.
The existing map TemporalValidityDialog edits existence dates and therefore
routes to `map.visibility`; relation form timing routes to `relations.timing`.

## Verification

- Focused Help, bundle and CompactDateWidget regressions: 65 passed, one skipped.
  The only skip is
  the existing optional packaged executable probe. Machine-readable results:
  `artifacts/krt87/focused.xml`.
- All 27 native Windows Qt Help scenarios pass using `QT_QPA_PLATFORM=windows` and
  window-level key delivery for modal cases. Results:
  `artifacts/krt87/native-help.xml`. This is automated native testing, not human
  acceptance or an extracted-release test.
- Tests cover Rich/Source and live F11 writing, unfinished relation/chronology/date
  inputs, a real geometry coordinator working copy, background trajectory
  shortcut isolation, exact/fallback routing, history, missing bundles, resource
  confinement, destroyed origins and nested modal owner deletion.
- All six theme transitions preserve Help reading position and authoring context.
  Ruff, repository-wide mypy, visual policy, complexity policy, test collection
  policy and Sphinx validation pass. Reviewed complexity allowances do not grow.
- Dependency-direction tests pass. Additional architectural baseline checks
  expose the two existing failures listed below.

## Presentation

Navigation uses shared secondary controls, neutral inline links, supporting
captions and focus roles. The shared read-only companion surface uses app/surface
and text theme roles. Controls wrap without increasing minimum window dimensions.
No visual-policy baseline was regenerated and no new exception was added.

[Presentation metadata](presentation.json) records Qt, app/source identity,
native platform, DPI and label geometry. Twelve PNGs cover all six themes at
640 × 560 and 360 × 560 logical client pixels, disabled Back/Forward and focused
Return to work. Control widths meet their natural size hints. Native images were
visually inspected for readable content, complete labels, wrapping and link roles.

Examples: [dark narrow](dark_mode-360.png), [light normal](light_mode-640.png),
[muted light narrow](muted_light_mode-360.png).

Reproduce with:

```powershell
$env:QT_QPA_PLATFORM = "windows"
python -m scripts.build_help
python -m scripts.capture_help_evidence --output docs/ux/evidence/krt87
python -m pytest tests/unit/test_help_coordinator.py -q
```

This bounded evidence does not establish all display/text scales, multi-monitor
behavior, screen-reader usability, independent human task success or package
acceptance. Those remain KRT-91.

## Existing failures outside this change

The broader native writing/shortcut/window run returned 83 passed, one skipped
and one failure: `test_repeated_entry_restores_width_and_chrome[entity]`.
The Entity description splitter changes its first size after repeated Focus
writing entry. The same failure reproduced offscreen using the untouched HEAD
FocusWritingController loaded in memory: `[659, 0]` became `[673, 0]`.
No worktree rollback or baseline modification was used for that comparison.

`test_god_module_boundaries.py` reports two stale limits: DatabaseService gained
`require_connection` relative to its reviewed API baseline, and DatabaseWorker
has 2,102 lines against a 2,089 ceiling. Both source files have identical Git
blob hashes to HEAD and were not changed by KRT-87. The boundary/dependency run
returned 53 passed and these two failures; see
`artifacts/krt87/help-architecture.xml`. These limits were left unchanged.

The full ci_fast/release gates were not run during implementation verification.
Commit delivery reuses these recorded results at the owner's request; pushing
remains a separate delivery step.
