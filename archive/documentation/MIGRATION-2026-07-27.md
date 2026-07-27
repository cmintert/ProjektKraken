# Documentation Unification Manifest

Date: 2026-07-27

## Purpose

The previous `docs/` tree mixed current manuals, stale API stubs, implementation
reviews, generated research, archived documents, and active design proposals.
This migration makes `docs/` the source for current published documentation
only.

## Classification

| Previous material | Disposition |
| --- | --- |
| User Guide, Workflows, FAQ, Installation | Preserved in `pre-unification-2026-07-27/`; replaced by task-focused pages under `docs/user/` |
| Architecture, Development, Database, Testing, Contributing | Preserved in the snapshot; replaced by contract-focused pages under `docs/developer/` |
| API Reference and package `.rst` files | Preserved in the snapshot; removed from publication because their signatures and module lists were stale |
| Maps/Layers/Rasters guide | Preserved in the snapshot; current behaviour merged into `docs/user/maps.md` |
| Map architecture review and nesting strategy | Preserved in the snapshot; implemented behaviour documented separately from design history |
| `docs/archive*` | Moved under `archive/documentation/` |
| `docs/design_notes` | Moved under `planning/design-notes/` |
| Generated Gemini research | Excluded from Sphinx; existing user deletions were left untouched |

## Canonical destinations

- User manual: `docs/user/`
- Developer manual: `docs/developer/`
- Exact and generated reference: `docs/reference/`
- Historical documentation: `archive/documentation/`
- Non-authoritative plans: `planning/`

The root `README.md`, `CHANGELOG.md`, and `LICENSE` remain authoritative.
