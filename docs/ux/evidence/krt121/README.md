# KRT-121 import/export integrity evidence

Implementation record, 1 November 2026. Based on
`a14ff51ebae97d19b152d22d3e348f50f8a437cf`.
[Parent issue](https://linear.app/projektkraken/issue/KRT-121/repair-importexport-integrity-and-native-record-preservation)
and KRT-122–126 track delivery; the local commit identity and current issue
statuses are recorded in Linear. Native human review remains pending.
The [supplied audit](https://linear.app/projektkraken/document/importexport-capability-audit-1-november-2026-86ea57061645)
is preserved as a Linear document attached to the parent.

## Implementation and boundaries

The shared preview validates supplied shapes and known native structures before
materializing a private database clone. UUID/selected-match identity precedes
external identity and reviewed name fallback. Authored Relation UUIDs identify
facts independently of their endpoint/predicate triple. Text dates retain
authored precision; numbers remain day coordinates. Supported invalid timing and
cycles block apply; missing sources need deliberate unresolved acceptance.

Lore v2 carries referenced calendar definitions. Mapping requires equivalent
definitions and epoch meaning and currently targets the active calendar because
the temporal resolver uses that calendar. Import never installs or switches a
calendar. Native tables carry a manifest and typed scalar cells. Selected exports
expand semantic relationships one hop from the original selection, then close
required timing dependencies with a visited set. Missing dependencies are named
in the export review. Future timing metadata remains opaque with diagnostics.

Native Markdown uses safely serialized YAML, a separate user-attribute mapping
and versioned native metadata with outgoing Relations. Readable user fields are
editable; conflicting projected timing or Related links require correction.
Third-party notes retain their existing route. No new database schema, domain
model, unique Relation triple, automatic calendar installation or vocabulary
authoring feature was introduced.

CLI rereads source files and reconstructs saved review intent, verifies source,
world and temporal-context fingerprints, registers the current timing plan and
applies through the existing prepared command. Successful commands enter world
history. The old public direct-write API refuses mutation; only transfer
preparation calls its private materializer. Unused legacy worker slots, signals,
wiring and completion UI were removed after caller discovery. The worker remains
a facade; no feature responsibility was added to a choke point.

## Automated evidence

- New integrity/portability tests cover explicit matches, renames, separate
  creation, repeated Relation periods, malformed shapes, state payloads, authored
  dates, future versions, remapping, dependency cycles/missing sources, calendar
  equivalence/epoch conflicts, typed CSV and native Markdown. Apply checks inspect
  database rows, including source preservation and exact undo/redo snapshots.
- A file-backed prepared import is serialized, the database is closed/reopened,
  then undo and redo restore exact lore and normalized tags.
- Actual CLI processes exercise existing-world targeting, review files, changed
  sources, consequential cascade confirmation and command-history persistence.
- The portable-world control compares every database table and asset bytes after
  export/import. Populated controls include calendar, layers/raster references,
  geometry history, trajectories, gallery records, tags, Longform attributes and
  an opaque relation-configuration storage value. This is synthetic storage
  preservation evidence, not exhaustive native feature acceptance.
- Architecture tests restrict private materialization to transfer preparation
  and prevent the retired worker routes from returning.
- Complexity: Event import **29 → 26**, Entity import **28 → 22**; private batch
  materialization is **8** and its public retired-write wrapper is **1**, compared
  with the original batch's **29**. Exact ceilings decreased and the obsolete
  batch allowance was removed. No allowances were raised.

Final check results are recorded below. Test artifacts live in
`tmp/krt121-*`; generated manuals and offline Help live under `docs/_build/`.
Six removed inventory nodes deliberately covered the retired completion UI
(five tests) and hand-built YAML quote escaping (one test). Replacement tests
exercise shared review behavior and typed serialization.
The inventory change is scoped to this work; 369 previously unbaselined additions
elsewhere in the checkout remain outside this change's recorded baseline.

| Final check | Result |
| --- | --- |
| Consolidated transfer, CLI, timing, architecture and Help regressions | **449 passed, 1 skipped**; 116.01 seconds |
| Skip | Existing Windows symlink test: privilege unavailable |
| Smoke | **21 passed**, 7,501 deselected |
| Ruff | Clean across `src` and `tests` |
| Repository-wide mypy | Clean across **582 source files** |
| Complexity and visual policies | Passed; no raised or regenerated allowances |
| Inspection declarations/source reviews and offline Help build | Passed |
| Test inventory policy | Passed; six intentional removals and scoped replacements |
| Generated database schema | Current |
| Strict Sphinx HTML | Build succeeded with warnings treated as errors |
| Rendered manual and Help | Preservation matrix inspected in offscreen Chromium; dependency explanation inspected in the actual Help viewer |

An initial consolidated run exposed stale Help fingerprints after the final
record-detail correction. Those three functions were individually reviewed;
canonical explanations remained accurate and the inspection notes were updated.
The final consolidated run above passes. The only runtime warning is the existing
FastAPI/Starlette test-client deprecation.

## Presentation and documentation review

Contracts **2/4/5/6/7/8/9/11** apply. Existing Import/Export routes, focused-control
keyboard ownership, editable review JSON, draft state and command history remain.
New decision rows reuse the shared wrapping combo and existing tree, input,
secondary-action, selection and focus presentation; no local colors or new action
variants. Calendar and dependency decisions have explicit F1 destinations.

Offscreen tests exercise enabled choices, disabled apply, keyboard focus and
recheck across all six shipped palettes at 780 × 560 and 1200 × 800. Screenshots
are in `tmp/krt121-renders/`. The final probes register Segoe UI explicitly and
use the production theme renderer and stylesheet. Earlier placeholder-glyph
renders were replaced and do not count as readability evidence. Narrow review
tables require horizontal scrolling to see identity and choice columns together;
choices remain reachable and their action labels wrap. Native DPI/human
readability has not been observed.

| Documentation review field | Record |
| --- | --- |
| Reader | Authors exchanging lore; operators using the existing CLI |
| Primary purpose | Existing transfer page: how-to; preservation matrix and CLI page: reference |
| Canonical pages | `docs/user/import-export-and-backups.md`, `docs/reference/cli.md` |
| Operational sources | Transfer coordinator/dialog, prepared command, file adapters, calendar/identity validators and stored-row tests |
| Topic and anchors | `world.transfer`; existing anchors retained; calendar and missing-Event choice explanations added |
| Recovery | Recheck stale/edited input; correct/exclude invalid records; persistent Undo after successful apply |
| Source/automated review | Implemented behavior traced and exercised; final checks recorded below |
| Rendered manual/offline Help | Locally inspected: `tmp/krt121-renders/manual-preservation.png` and `offline-help-dependency.png` |
| Human prose/live Help approval | Pending; no participant results claimed |
| Reader tasks/native DPI review | Not performed; separate from automated evidence |

The owner authorized a local commit reusing the recorded passed checks on
1 November 2026. No tests were rerun for commit delivery; normal commit hooks
remain enabled. No push, merge, release or user-world mutation was performed.
