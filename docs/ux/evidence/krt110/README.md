# KRT-110 World Context fact rows

Presentation follow-up to KRT-96, requested on 2026-10-25. The owner chose the
Fact rows prototype; acceptance of the implemented native UI remains pending.
KRT-109 tracks future research into browsing limits and association relevance.

## Behavior and boundaries

Overview → History & context uses one fact per row, with timing and provenance
below it. Counts describe loaded entries. Sections preview three rows; Show all N
and Show fewer control an individual section. Expand all and Collapse all reveal
all loaded rows or restore previews. Omitted records remain explicitly listed.
State-change records have their own section; shared Event, tag and map evidence
has an explanation of its limited meaning.

The presentation consumes the existing snapshots. Selection, traversal, temporal
qualification, budgets and provider prompts are unchanged. Canonical relationship
predicates remain intact. Legacy snapshots without calendar/source metadata show
explicitly labelled lore-day boundaries rather than an unexplained numeric range;
an absent boundary is called “not supplied”, without guessing unknown vs unbounded.

Contracts 1/4/5/6/7/8/9 apply. The existing mode selector, typed navigation signals,
draft guards and editor hosts remain. Same-object refresh reuses section controls
and retains disclosure/scroll; selecting another object resets disclosures.
Shared quiet controls provide focus/checked/disabled states. Surface, main text,
supporting captions and typed/neutral links use semantic theme roles. There is no
new authoring action or interaction exception.

## Verification

Run `python -m scripts.capture_context_rows_evidence` with
`QT_QPA_PLATFORM=offscreen`. It isolates settings, opens no world/provider, and
retains 36 captures plus a manifest in `docs/_build/krt110/rendered/`: six themes,
requested widths 360/800, preview, expanded/focused and ancestor-disabled states.
Actual content widths are 334/774 at device pixel ratio 1. These are full content
captures; the real inspector scrolls. Narrow dark and wide light captures were
inspected. A malformed stylesheet rule discovered in rendering was corrected;
the regression now checks actual Entity/Event link character colors.

Focused row/inspector tests passed (66 cases); the final typed-link assertion also
passed in the seven-case renderer suite. Verification includes keyboard Space
on the section disclosure, independent local/global expansion, unchanged input
snapshot, source navigation, narrow wrapping, same-object state and editor dirtiness.
Repository mypy, Ruff, visual/complexity policies, offline Help, schema consistency
and strict Sphinx passed during implementation.

Final integration: the 210-case context/temporal/inspector/Help run returned
208 passed, one skipped and one stale Help review fingerprint. After updating
the reviewed stylesheet fingerprint, all 27 affected renderer/inspection cases
passed. The final eight-case renderer run additionally verifies nearest earlier
and later Event previews. No remaining failed check is known. Repository typing
is clean across 516 source files. The populated action-label fast matrix has
24 records and zero failures (dark/light, 360/800 widths, normal/double text,
preview/expanded/disabled; scale 1.0). Other DPI settings remain native review work.
Offline Help was captured in six palettes at 360/640 widths under
`docs/_build/krt110/help/`; narrow dark Help was inspected. Updated Help anchors
are included in the generated-excerpt tests. The strict manual build is clean.

## Human review

Pending: native Windows readability/focus at the owner's DPI, finding a single
relationship and its supporting Event, local/global expansion and omission wording,
and updated Help prose. These captures and tests do not establish human task-time
improvement or repeat the accepted KRT-96 temporal/model review.
