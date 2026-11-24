# Relation handling boundaries — KRT-98

This guide records current relation behavior and the boundaries for
[KRT-69](https://linear.app/projektkraken/issue/KRT-69) vocabulary and
[KRT-71](https://linear.app/projektkraken/issue/KRT-71) directional wording.

## Ownership after preparation

`src/core/relation_presentation.py` owns the current overview captions, authoring
captions, full-form suggestion defaults and inline preview calculation. Its
helpers use exact stored keys and preserve unknown keys verbatim. Choice helpers
return fresh values, exclude generated `mentions`, and preserve each surface's
existing ordering. The frozen `RelationPreview` contains display text and an
assertion heading, not mutation intent or a persisted definition.

Different surfaces deliberately retain different output. For example, `involved`
is **Participation** in the overview and **Participant in** in authoring. The full
form still previews raw `source --key--> target`. An inline source event with a
date of `0.0` remains an event; reversing its preview does not infer a new fact.

`src/core/relation_policy.py` owns the endpoint change assessment used in the
inline editor and on the worker. A state-change payload protects both endpoints.
Source-bound timing and unrecognized temporal structure protect the source.
The assessment checks both the saved and proposed attributes. Clear or revise
the protected metadata in a separate, deliberate edit before changing endpoints.

Both core modules stay independent of Qt and storage. Dependency-direction tests
guard that boundary. Widgets retain groups, temporal summaries, UUID deduplication,
editable-caption/key adaptation, draft guards, focus, selection and signals.
`AuthoredRelationService` still owns authored mutation preparation; repositories
own SQL/transactions. Worker ownership and queued command delivery do not change.
Exact undo restoration remains separate from forward validation.

## Reciprocal compatibility — KRT-70

One authoring action saves one directed assertion. The same UUID is reachable
from both endpoints, and GraphView can choose either direction before saving.
A symmetric relation such as `sibling_of` needs one row. If two directed facts
are true, author each independently, for example `A knows B` and
`B trusts A`. Existing reciprocal pairs remain separate rows and can be
selected, edited, transferred and counted by UUID.

The retired CLI flag exits with code 2. To record the two example facts, use
`relation add -d world.kraken -s A -t B --type knows` and
`relation add -d world.kraken -s B -t A --type trusts`, replacing A and B with
the saved endpoint IDs.

Legacy reciprocal adds can replay only from a command snapshot containing both
recorded IDs. Recorded endpoint edits can replay against their original
snapshot. Undo restores the exact saved state. No schema migration is needed.
KRT-71 can render the incoming perspective over the same canonical assertion
and temporal evidence.

## Consumer inventory

| Consumer / code owner | Current inputs and meaning | Future integration boundary |
| --- | --- | --- |
| Connections (`connection_presentation`, `connections_overview`) | Stored UUID/key/endpoints, incoming/outgoing snapshots, attributes and viewed-time context; overview captions, explicit category mappings, temporal summaries | Resolve wording without changing group rules or filtering. Deduplicate the same UUID only; preserve separate reciprocal rows. |
| Inline authoring (`relation_authoring`) | Authoring captions, stored-key item data, original endpoint names, source-event availability, advanced attributes | Replace display resolution without turning captions into keys, dropping drafts or changing mutation intent. |
| Full form and type picker (`relation_form`, `relation_type_picker`) | Full form defaults plus observed raw types; picker retains its own observed-type sorting and generic `related` choice | Keep raw keys, custom types, full-form preview, validation and generated-mentions protection. The generic picker is not converted to vocabulary captions here. |
| GraphView (`graph_data_service`, `graph_view/graph_builder`, `graph_projection`) | Exact key filters, UUID and original direction; raw edge labels/tooltips, temporal status, lexical style keyed by predicate | Display forward wording along the stored edge; retain key-based filters/styles and time modes. Never manufacture an inverse edge. |
| World Context (`authoring_context_builder`, `core/authoring_context`) | Key, endpoints, UUID, traversal hop, temporal window/status; raw formatted assertions; explicit participant/location roles | Add presentation beside machine identity. Preserve current historical Entity context, qualification and traversal. |
| RAG (`rag_service`) | Structured stored relation endpoints and raw keys formatted as arrows | Adopt wording separately from indexing, retrieval ranking and semantic comparisons. |
| Temporal analysis (`temporal_analyzer`, temporal conflict/dependency services) | Stored keys, direction, temporal attributes and event anchors | Preserve analytical rules independently of captions. Lifespan analysis currently recognizes case-insensitive `birth`/`death` **substrings**, not vocabulary labels. |
| Intelligence analysis (`intelligence_analyzer`) | Detached relation snapshots, endpoint evidence and analysis context; proposed relations are distinct from stored assertions | A label does not establish an inferred assertion. Keep analysis inputs and review/mutation routes separate from wording. |
| WikiLink mentions (`wiki_commands`, `relation_repository`) | Generated `mentions`, source/target UUIDs and occurrence metadata; reconciliation and exact snapshots for replay | Keep generated references outside authored vocabulary mutation and reciprocal assertion creation. |
| CLI (`cli/relation`) | Raw keys, direction and metadata | Run `relation add` once for each intended direction. The retired `--bidirectional` flag fails before opening the database. |
| Transfer/import/export (`transfer_exchange`, `import_service`, `obsidian_exporter`) | Serialized keys/endpoints/attributes; Obsidian related sections currently expose raw relation types | Audit each format before vocabulary integration or identifier migration. Display-label changes cannot silently rewrite exported keys. |
| Commands/history (`relation_commands`, `base_command`) | Exact UUIDs, endpoints, keys, attributes and timestamps; expected snapshots, transactions, serialized undo/redo state | New adds create one row. Legacy reciprocal commands replay both recorded identities as one operation. |

### Known classification differences

Connections' Event groups classify explicit `involved`/`participated_in` as
Participants and leave `member_of` in Other connections. World Context's
`PARTICIPANT_REL_TYPES` still includes `member_of`. These are separate current
consumer contracts, not a rule unified by this extraction. Characterize both
before deliberately changing either. Target object kind alone does not establish
relation meaning. Likewise, display renaming must not change lifespan substring
analysis, graph filters or generated-mentions policy.

## Future resolver contract

Resolution will receive the canonical stored assertion, an explicit viewing
perspective and detached effective vocabulary definitions. This is an integration
boundary, not a new wire format or approved definition-storage schema.

Preserve relation UUID, stable predicate key, original source/target and instance
metadata alongside any presentation. Temporal validity, event bindings, confidence,
payload, provenance and evidence belong to the instance. Consumers whose current
projection omits some metadata need an explicit projection review before claiming
that it is available to a new resolver or AI consumer.

Compact captions, optional full-sentence previews, inspector categories and
analytical classification are distinct outputs/consumers. Incoming wording is
another perspective on one assertion, not a second stored fact. Unknown predicates
must remain legible without fabricated inverse grammar. Identifier migration,
schema/precedence, templates and world-local storage remain KRT-69/70/71/76 work.

## Verification scope

The extraction preserves authoring Contracts 2/4/5/6/8/9 and action-label Contract
11. Visible routes remain Connections → Edit, inline Reverse/Apply/Cancel, drop
capture and Full relation editor. Qt controls, keyboard ownership, drafts, caret,
selection, scroll and playhead remain with their current owners. Existing primary,
secondary, quiet, disabled, selection and focus theme roles remain unchanged; no
new QSS, colors, theme variants or policy exceptions are introduced.

Pure compatibility tests cover captions, suggestions, preview direction and both
reversal assessments; widget/command regressions cover stored-key adaptation,
advanced attributes, stale edits, drafts, UUIDs, rollback and undo/redo. Rendered
offscreen evidence is presentation evidence only, not native DPI readability or
human acceptance of KRT-93 or future vocabulary UX.

See [KRT-98 verification evidence](../ux/evidence/krt98/README.md) for the focused
checks, before/after complexity and reproducible baseline/current captures.
