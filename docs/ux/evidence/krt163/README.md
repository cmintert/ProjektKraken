# KRT-163: one temporal rendering pipeline

Recorded 2026-11-14 against local base `fe14e5b27c227ee140283cd3e7ee5ab49f102c4d`
plus the uncommitted KRT-163 implementation. This is source, automated and
offscreen rendering evidence. Native application, live Help and human acceptance
remain pending. No saved world was opened or modified for the captures.

## Behavior and boundaries

The former direct and resolved renderers disagreed about minute/second dates.
`present_event` now owns a single immutable `TemporalPresentation`; both retired
modules and their functions are removed, with all consumers migrated directly.
Detached resolution snapshots carry original assertion meaning through references
and serialization. Geometry and navigation consume the resulting classification.
Ordinary items prepare meaning on Event/calendar changes rather than during paint.

The owner selected filled markers for asserted/calculated day-and-finer dates,
with uncertainty qualifiers and explicit limits retaining their temporal grammar.
Month/year dates remain windows. Precision intervals and possible/certain presence
remain mathematically intact. Repeating Events retain circles, the compact strip,
clustering and existing zoom suppression. This work does not resolve the separate
discoverability question about hidden repeats at wider zoom.

Rendering snapshots are excluded at both single/bulk repository write boundaries.
Timing plans compare equivalent canonical views while still repairing stale stored
coordinates. Exact numeric timestamps and authored definitions remain preserved;
certified translation previews update the accepted snapshot definition as they move.

## Verification and rendering

Local command logs are retained under ignored `artifacts/krt163-*.txt`.
The boundary run passed 154 tests, and the separate MCP reader run passed 85 tests.
The affected Timeline/temporal run passed 1,270 tests; the final canonical-model
and architecture run passed 38 tests, including malformed timing metadata.
Help suites passed 73 tests with one skip. Offline Help and strict Sphinx builds
passed. Ruff, repository-wide mypy (677 source files), visual policy, complexity
policy, contextual Help inspection and whitespace checks passed. No complexity
allowance was changed. Detailed command evidence is also recorded in Linear. A broad initial run stopped at a
native Windows access violation in an MCP semantic-preparation test; that test
and related factual-reader suites passed in isolation. This is not evidence of
a successful full-repository run.

`python -m scripts.render_temporal_presentation` produces 48 composed production
widget captures in `artifacts/krt163/`: six themes, 1200/480-pixel widths, two zoom
levels, ordinary/repeating and collapsed comparisons. It uses synthetic dates,
isolated QSettings, loaded Segoe UI fonts and offscreen Qt. Inspected dark normal
and light narrow overview captures: numeric/day/minute diamonds are filled;
month precision retains a capped hollow window; approximate dates retain soft
marks; repeating occurrences retain filled circles. Focus/selection outlines,
future captions and narrow toolbar overflow remain visible. Long Event names can
extend beyond the panned viewport, as before; glyph dates are not moved to fit.

Shared roles remain `event_main`, `text_main`, `supporting_text`,
`supporting_caption` and `focus_ring`. No new visual-policy exceptions are added.
Contracts 1/2/4/5/6/7/8/9 and KA-09–11 apply. Regression coverage includes schema
parity, day/hour/minute/second, bounds/qualifiers, derived dates, disjoint
solutions, duration/endpoints, missing calendars, invalidation, save purity,
selection under the playhead, translation previews, undo/redo and history.

## Documentation review

| Review field | Record |
| --- | --- |
| Reader and purpose | World authors reading temporal marks; explanation in the existing Timeline manual, architectural explanation for maintainers |
| Release and pages | Unreleased; Timeline and calendars, visual vocabulary, architecture |
| Verified sources | Canonical builder, geometry/painter, repeat markers, repository writes, timing plans and the focused suites |
| Retained destinations | Existing headings, `date.precision`, `timeline.viewing`, `event.recurrence`, inspection IDs and anchors |
| Help review | The specific repeat painter fingerprint is reviewed: source of geometry changed, while circle pins, labels, selection and keyboard explanations remain accurate |
| Rendered manual/Help | Strict HTML and validated offline bundle built; production HelpViewer inspected at 800px dark and 480px light, including the revised uncertainty section. Existing search/inspection suites pass. Local captures: artifacts/krt163/help-*.png |
| Human approval/live Help | Pending; no native-DPI, independent reader or usability claim |
| Reader round | Owner/cohort/date pending; no new interaction procedure or save action introduced |

The authoritative Linear visual vocabulary and repository counterpart were revised
together. Documentation generation, search and source-review checks are separate
from reader comprehension and owner acceptance. Implementation remains open until
verified and committed.
