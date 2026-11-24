# Relation vocabulary architecture decision

Status — proposed for review under [KRT-69](https://linear.app/projektkraken/issue/KRT-69).
The [current relation handling](relation-handling.md) documents the running app.

## Decision

A relation's stored type (`rel_type`) identifies its meaning to Kraken. A world
vocabulary definition supplies wording for that key. App-owned rules determine
whether a key contributes to lifecycle analysis, participant context, or another
feature. The relation itself retains its UUID, endpoints, direction, and
instance attributes, including timing, confidence, and provenance.

Without an explicit world definition, display the saved type. Someone who
entered `involved` should see `involved`. The current compatibility caption
“Participation” contains no evidence of an author choice. A new custom phrase
such as `sworn protector of` can be used without registering it. Generated
`mentions` retain their read-only Reference presentation.

An explicitly adopted label applies to every relation with that exact key in the
world. Before applying “Participation” to `involved`, show the affected
relations and their new wording. If someone enters `involved` after adoption,
preview “Participation” before saving. Provide the key in relation details and
qualify ambiguous labels in lists and pickers where a distinction is needed.
For example, show “Participation (involved)” and “Participation
(participated_in)” when both resolve to that label. A world-level definition
gives consistent wording without keeping a second label on every relation.

Explain app behavior where the author chooses a built-in type. The Birth choice
should say that it contributes to the character's lifecycle when supported by
date evidence. A world may label `birth` “Born at” without affecting that
calculation. Giving a custom key the label “Born at” only changes its wording.

## Version 1 schema

Use one JSON document under the `relation_vocabulary` key in the worker-owned
`system_meta` settings store. The top level has integer `version` (initially
1) and a `definitions` array. A definition has the following fields.

| Field | Contract |
| --- | --- |
| `key` | Nonblank stable string. Compare exact code points, including case. |
| `forward_label`, `reverse_label` | Required, nonblank compact strings. Forward reads from the stored source. Reverse reads from the stored target. |
| `description` | Required short string explaining meaning. |
| `enabled` | Boolean, with true as the default. |
| `category` | Optional nonblank string. Consumers use their normal fallback for unrecognized categories. |
| `preferred_source_kind`, `preferred_target_kind` | Optional `entity` or `event`. These guide suggestions. Existing endpoint validation still governs writes. |
| `symmetric` | Optional boolean, with false as the default. It records a declared meaning and creates no reciprocal row. |
| `forward_template`, `reverse_template` | Optional nonblank sentence templates. Only literal `{source}` and `{target}` substitutions are allowed. |

```json
{
  "version": 1,
  "definitions": [
    {
      "key": "member_of",
      "forward_label": "Member of",
      "reverse_label": "Members",
      "description": "Membership in a group.",
      "preferred_source_kind": "entity",
      "preferred_target_kind": "entity",
      "forward_template": "{source} is a member of {target}.",
      "reverse_template": "{target} has {source} as a member."
    }
  ]
}
```

Reject duplicate exact keys and invalid field values on write. Apply the existing
authoring trim at new text entry. Preserve existing relation keys exactly on read
and during vocabulary operations. Lookup does not case-fold, normalize Unicode,
or infer aliases from similar wording. Reserve generated keys and variants
recognized by system consumers when creating custom definitions or migrating
keys. Existing legacy variants remain readable. Built-in keys can receive
explicit wording overrides while retaining their app-owned behavior. Protect
generated `mentions` from authoring and vocabulary overrides.

Ship curated definitions in a versioned catalog of suggestions. Explicit
adoption copies the complete definition into the world. Read order is the
system Reference presentation, an enabled exact world definition, then the
saved type. Opening an unconfigured world requires no write. Disabling a
definition restores fallback wording and retains the definition for re-enabling.
Catalog upgrades leave adopted definitions in place.

Validate preset imports before writing. An exact-key conflict requires an
explicit keep-or-replace choice, and any label change previews the affected
relations. Apply the reviewed change atomically and reject it if the vocabulary
has changed since preview. An unsupported document version, invalid structure,
or duplicate key uses fallback and preserves the original payload. For a
structurally valid definition with an invalid template, use the compact label
on read and reject the template on save or import.

Keep settings reads and writes in the repository on the worker thread.
Publish detached vocabulary snapshots through existing application boundaries.
The full-world transfer uses SQLite backup and carries world-local metadata.
Verify backup/restore and transfer against effective wording. Treat row exchange
as a separate format that continues to carry the original relation keys.

## Shared read interface

Accept a detached relation snapshot, a vocabulary snapshot, and a source or
target perspective. Return UUID, exact key, canonical source and target IDs,
compact label, and optional rendered sentence. Preserve the original relation
snapshot for downstream consumers. For reverse wording, the template variables
still refer to the original stored endpoints. Reject unknown placeholders,
unmatched braces, attribute access, conversions, and format specifiers. Escape
interpolated names at the output boundary according to the rendering context.
When a reverse definition is absent, use the canonical source-to-target arrow
assertion. When only a sentence is unavailable, use the resolved compact label.

World Context, generation, RAG, and the Intelligence Analyzer can render the
same resolved wording while retaining the machine-readable key, direction,
UUID, timing, uncertainty, and provenance. A definition supplies presentation
data. Inverse wording and symmetry never create a new relation or inference.

## Reference-consumer audit

| Surface | Current key use | Identifier migration obligation |
| --- | --- | --- |
| Authoring, commands, repository, history | Relation forms and graph authoring submit keys. The repository persists and finds exact keys. Command and scoped-history snapshots carry keys. Exact `mentions` is protected in authored relation writes and database triggers. Some history and graph paths also recognize normalized variants. | Preserve relation UUIDs, endpoints and attributes. Handle replayable history and undo snapshots before allowing a rename. Exclude generated keys and protected variants. |
| Connections, timeline and detail snapshots | Connections uses exact caption and grouping tables. Timeline shows relation types and detail snapshots recognize normalized lifecycle keys. | Resolve presentation by key. Reject a rename that changes classification or lifecycle behavior without an agreed compatibility rule. |
| Lifecycle, temporal analyzer and dependencies | Lifecycle and lifespan analysis recognize trimmed, case-folded `birth`, `death` and `revival`. Temporal binding and dependency calculations use relation IDs and attributes. | Protect lifecycle keys and aliases recognized by normalization. Preserve relation IDs, event anchors, timing and payloads. |
| Graph, lexicon and settings | Edge text and lexicon style use the stored key. Graph filtering has exact and case-insensitive paths. Settings snapshots expose saved types. | Audit and update persisted lexicon keys and any persisted type filters or settings that reference the renamed key. Refresh projected data after commit. |
| World Context, MCP, RAG and Intelligence Analyzer | Authoring context uses exact sets such as `involved`, `participated_in`, and `member_of` for participant selection in applicable paths. MCP queries and structured/indexed context carry predicates. RAG and analyzer text can include the raw key. | Preserve app-owned classification, rebuild or invalidate derived context and indexes, and retain the canonical key in structured output alongside captions. |
| CLI, import/export and validation | CLI operates on saved keys. Row exchange includes `rel_type`, import identity compares it exactly, and world validation groups duplicates by endpoint IDs and type. Markdown and native notes can carry relation text. | Keep external snapshots as historical exports. Review mapping and collisions when importing them later. Do not treat arbitrary prose as a key reference. |
| World backup and full transfer | Database snapshots carry relation rows and `system_meta`. | Include vocabulary and rename history in the world snapshot. Past backups keep their original world revision. |

The migration preview in [KRT-76](https://linear.app/projektkraken/issue/KRT-76)
must identify affected rows, writable key references, any replayable history,
and semantic consumers before applying a rename. Reject a protected source or
destination, an occupied exact destination, any collision under a consumer's
normalization that changes behavior, and any migration whose live references
cannot be updated safely. Recheck the preview on the worker and update durable
references and world-local rename history together in one transaction. Record
old and new keys and the applied revision or timestamp. Publish invalidations
after commit. A failed or stale migration leaves the world intact.

## Compatibility matrix

| Case | Required evidence for downstream implementation |
| --- | --- |
| Open a legacy world with both `involved` and `participated_in` | Both original keys display and remain distinct. No vocabulary data is written on open. |
| Adopt “Participation” for `involved` | Review contains the affected key, relations and wording. A later authoring preview matches the saved display. Reopening and editing notes preserve the key. Duplicate labels remain distinguishable. |
| Enter an unregistered custom phrase | The exact saved phrase is shown after save and reopen with no registration step. |
| Display `birth` as “Born at” | Identical relation and date evidence yield identical lifecycle results. A custom key with the same label adds no lifecycle behavior. Existing normalized legacy claims remain readable. |
| Browse `member_of` from both ends | Both views preserve UUID, canonical endpoints and timing. Missing reverse wording falls back to the canonical assertion. Invalid sentence templates fall back to compact wording. |
| Disable a definition or import a preset | Fallback is available immediately after disabling. Conflicts require review. A stale preview, invalid write, or transaction failure leaves the prior vocabulary intact. |
| Open malformed metadata or a newer schema | Safe fallback displays the relation keys. The saved vocabulary is preserved for recovery. |
| Restore a backup or transfer a full world after a catalog upgrade | Adopted definitions and effective wording round-trip. The destination's bundled catalog cannot change them. Row-only exchange preserves the raw keys. |
| Preview and apply a key migration | Protected or colliding migrations fail before writing. A successful migration updates all live key references and retains UUID and rename history. |

KRT-69 delivers this design and matrix for review. [KRT-70](https://linear.app/projektkraken/issue/KRT-70)
owns reciprocal relation semantics. [KRT-71](https://linear.app/projektkraken/issue/KRT-71)
implements shared resolution. [KRT-72](https://linear.app/projektkraken/issue/KRT-72)
owns wording previews during authoring. [KRT-73](https://linear.app/projektkraken/issue/KRT-73)
owns world definition editing and impact previews.
