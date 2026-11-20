# KRT-18 sample verification — 2026-10-08

Implemented the editable **Northwatch Demo (Illustrated)** portable world:
four named events, seven connected entities, eighteen relations, one map,
one changing kingdom region, and one travelling army with a bridge waypoint.
The ruler, offices, keep allegiance and descriptions change at the succession.
The disputed surrender remains month-precision and uncertain, with no invented
exact occurrence bound. Longform contains all eleven authored items.

## Completed checks

- Five focused integration tests passed after the final content and art changes:
  cold database reload; historical state, geometry and location; event-linked
  reign boundary; uncertain partial date; one repairable validation finding;
  Longform membership; refusal to overwrite; and atomic failure behavior.
- Ruff passed for the generator and new tests. Mypy passed for the generator.
- Visual policy and complexity policy passed. No production UI source or
  reviewed complexity hotspot was modified.
- The production map widget was rendered offscreen using software rendering,
  the production stylesheet and an explicitly loaded Segoe UI font.
  [Before](before.png) and [after](after.png) show the expanding border and
  moving sword marker. Persisted geometry was resolved through the production
  resolver and applied through the map widget; these captures do not establish
  a full asynchronous application navigation test or newcomer discoverability.
- The portable ZIP uses SQLite's backup API for a consistent database snapshot.
  The ZIP was extracted at a different location and checked independently:
  archive CRCs, database integrity, relative map asset, historical ruler change
  and the single intended incomplete-description finding all passed.

## Durable and generated artifacts

Reproducible source is `scripts/create_demo_world.py`,
`assets/demo/northwatch.png`, and `docs/ux/northwatch-demo.md`.
The five tests are in `tests/integration/test_demo_world.py`.
This directory retains the final rendered evidence and the image-generation
prompt. No application package or executable build was performed.

The editable world is in `worlds/Northwatch Demo (Illustrated)/`; the distributable
archive is `artifacts/krt18/Northwatch Demo (Illustrated).zip`.
An extracted verification copy is retained in `artifacts/krt18/portable-check/`.
These generated directories are ignored by Git.

The earlier sample's database was locked during a folder replacement attempt.
Its moved manifest, guide and assets were restored, with its database untouched.
The finished version was placed in its own directory. The early sample remains
in `worlds/Northwatch Demo/`; its supporting-file recovery copy and an explicitly
named incomplete early ZIP remain under ignored `artifacts/krt18/`.
Final archive creation and independent verification succeeded; temporary package
cleanup encountered a Windows directory lock. That is separate from archive
validity, and no broad cleanup was attempted.

## Remaining acceptance

The five observed first-session runs and two-minute uncoached first-value target
are pending. The route contains a recording table for them. Run the validation,
Longform and built-in backup/export steps during those sessions; the generated
Markdown and verified portable ZIP do not prove those application interactions.
KRT-18 remains In Progress until the observed newcomer acceptance is complete.
The user authorized a source/evidence commit; publication details are recorded
in KRT-18. Future world-content changes
by the owner should be preserved and used as the next working baseline.

## Supplied army icon — 2026-10-08

Added the owner's PNG unchanged as `assets/demo/army.png`. Its RGBA transparency
was verified. Each generated world includes a canonical custom-icon asset;
the illustrated world's army marker now uses that icon at 72 screen pixels
(existing non-default sizing would be preserved). Only the army marker's icon
and its unchanged original demo sizing were updated using the existing marker
attribute command. Other fields, unrelated attributes and the trajectory were
checked for preservation; a SQLite recovery snapshot is retained at
`artifacts/krt18/before-army-icon.kraken`.

The five focused tests passed again, including custom catalog discovery and
asset existence; Ruff passed. Actual map-widget captures are
[before](army-before.png) and [after](army-after.png).
The updated portable archive is `artifacts/krt18/Northwatch Demo (Army Icon).zip`;
it was read back, extracted, and validated independently by the package check.
The earlier ZIP remains available as the previous version.
