# KRT-158 visual description tables

Implementation on 12 November 2026, based on parser commit `54beba85`.
This table-authoring work remains uncommitted.

## Contract and interaction review

Contracts 2/3/5/6/7/8/9 apply. Tables extend the existing description editor.
The visible route is **Insert → Table**. It inserts a small table and exposes
row/column operations, table removal and column alignment. Bold, Italic and Link
to entry retain their existing routes; Format adds table-cell strikethrough.
Headings are unavailable in cells because GFM cells contain inline content.
The first row remains the header. Removing it promotes the following row.
Merged cells and multiline blocks remain outside visual GFM editing.

Tab/Shift+Tab navigate cells without changing content and leave the table at its
ends. Enter moves to the next row in the same column, leaving after the last row.
Ordinary writing and Source retain existing Tab focus traversal. The workspace's
focus controller delegates to the table while the caret is in a cell, just as it
delegates to item-view cell navigation. No contract rule is changed.

Every structural operation uses one native edit block. The existing retained
document history carries Undo/Redo across Source/Rich views. Untouched source is
exact; edited tables serialize semantic GFM, including alignment, inline marks,
escaped pipes and stable-ID links. Other unsupported content retains Source
fallback. Persistent saves still use the existing coordinator/command path.

Menus use existing secondary controls and overflow. Cell boundaries use the
theme's `action_secondary_normal_border`; the stronger first-row boundary marks
the header. Boundaries are painted as presentation, so theme changes do not
create authoring commands or alter source. Link identity, selection and document
focus retain existing semantic roles. Read-only and Source commands are disabled
and describe their prerequisites.

## Verification

Focused behavior checks cover direct paste/render, actual table dimensions,
structural one-step undo/redo, save/reopen and command undo, inline code and marks,
stable links, alignment, literal pipe characters, multiple tables, surrounding
prose, Source fallback, Unicode selections, theme/history preservation, menu
lifetime and delivered keys inside a composed workspace. The bounded run passed
222 editor regressions, then failed Help setup on a new documentation cross-link.
After correcting that link, all 23 Help checks passed. Repository Ruff and mypy
(668 source files), visual, complexity, test and inspection policies passed. Strict
Sphinx and offline Help builds passed. The earlier focused selections overlap;
their counts are not added to this record.

Composed offscreen editor captures at 360 and 680 logical pixels in dark/light
themes, with Windows Segoe UI/Consolas fonts explicitly loaded, are retained
locally under `artifacts/krt158/`. Narrow captures use the inspector's production
adaptive-width option. Enabled/disabled table menus and overflow routes were
inspected. The generated table Help excerpt was also rendered and inspected in
the production Help viewer. Offscreen evidence does not establish native Windows DPI or owner
human acceptance. No packaging or full-suite run is claimed for this milestone.

## Documentation review

The existing writing topic remains the canonical how-to for description authors;
the Markdown profile remains a reference. The new table section explains the
visible route, cell keyboard ownership, Save Changes, Undo and GFM limitations.
Existing Help IDs remain; `writing.tables` resolves to the table section.
Changed handler fingerprints are reviewed individually.

[Documentation review](../../../developer/documentation-review.md) and
[reader-observation](../../../developer/documentation-reader-testing.md) evidence
remain distinct. Human prose/live Help approval, independent reader outcomes
and native acceptance are pending.
