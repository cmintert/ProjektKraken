# Extract source material into lore

Use an external AI assistant to draft Entities, Events and Relations from a
located source, then review the result in Kraken. This workflow uses Lore JSON
exchange version 2. It is a prompt and review procedure, not an automatic
document-reading feature inside Kraken.

## Prepare one extraction

1. Choose the scope. Start with one named subject in one chapter, for example
   “Everything this chapter establishes about Frederick II.” Include all details
   within that scope, including everyday activities, attributed opinions and
   unresolved claims. Include connected subjects only far enough to explain their
   connection; do not expand into their unrelated histories.
2. Prepare readable source text with stable segment labels. For a PDF, check
   column order, headings and sidebars against the pages. Keep the original
   document, edition, page references and any extraction corrections. Mark the
   packet `PARTIAL_SOURCE` unless it contains the complete source.
3. Export **All lore** as **Lore JSON** from the intended world using
   [Export Lore](import-export-and-backups.md#export-lore). Keep its `context`
   object as the trusted calendar context. Exports contain calendars referenced
   by exported timing, so an empty world can export an empty calendar list. If
   the intended calendar is absent, create a dated Event in a disposable world
   configured with that calendar and export it to obtain the native definition.
   Keep that temporary Event out of the extraction registry and output.
   Supply the relevant existing records
   and UUIDs as the canonical registry. For an empty world, the registry is empty.
   Have your preparation tool allocate a fresh pool of UUIDs for new records;
   use a different unused pool for each independent extraction.
4. Supply the [extraction prompt](source-extraction-prompt.md), its input packet
   and the scope instruction below to the external assistant. Set the required
   granularity explicitly. Do not ask the assistant to infer the calendar from
   the source's publication date. A calendar mapping for historical dates must
   be a deliberate choice recorded in the packet.
5. Save the first JSON response unchanged. Keep a separate review ledger for
   unresolved identities, undated material, omitted passages and possible
   extraction errors. The prompt returns only importable lore, so ask for this
   ledger separately after saving the first response.

Use this scope instruction with the prompt, replacing the bracketed text:

```text
Extract everything the supplied passages establish about [subject]. Preserve
all information about this subject, regardless of perceived importance.
Include connected people, places, organizations, objects and events only as
needed to explain those connections. Resolve aliases only from supplied
evidence. Do not include connected subjects' unrelated histories. Preserve
attribution, uncertainty, contradictions and the source's temporal perspective.
```

The prompt's input list is a preparation contract for the assistant and caller,
not another JSON format that Kraken imports. Copy `context` from a native export
instead of reconstructing its calendar by hand. If no verified advanced timing
templates are available, supply an empty template collection: keep unsupported
timing in sourced notes and the review ledger.

## Check and import the result

1. Compare the draft against the source before accepting its claims. Check each
   statement, its locator, aliases and missing details. A valid page label can
   still point to a neighboring passage that does not support the claim.
2. Check time separately: year versus day precision, occurrence versus duration,
   testimony versus the event testified about, and the date of a revelation
   versus the earlier fact it reveals. Check changing offices and affiliations
   before and after their dated changes. A prose note saying “not timeless” does
   not itself give a Relation native temporal boundaries.
3. Use a disposable world with the intended calendar for the first import.
   Follow [Import Lore](import-export-and-backups.md#import-lore), inspect the
   review and resolve errors before **Import reviewed changes**. Review does not
   establish whether a claim is true to the source.
4. Inspect the imported records and relevant Timeline positions. Confirm that
   **Edit → Undo** removes the import and redo restores it. Correct extraction
   errors in a separate revision, retaining the original response and review
   record. Import the approved revision into the intended world through the same
   reviewed route.

Import success establishes compatibility with Kraken, not source completeness.
Descriptions and custom fields such as `claim_status` preserve readable evidence;
they do not enforce truth, event ordering or temporal validity.

## Continue across chapters

Give each chapter an ownership span and use neighboring passages only as context.
Carry forward the canonical registry, evidence-backed alias decisions and unused
UUIDs. Reuse a UUID for the same established identity or occurrence; similar names
alone do not prove a match. Keep separate Relations when they represent separate
facts, even if their endpoints and predicate match.

After chapter extraction, reconcile against all supplied chapters. Revisit
concealed identities, testimony contradicted later, repeated retellings,
conflicting dates and unresolved claims. Preserve the evidence for both earlier
claims and later revelations. Produce one canonical snapshot and review ledger.
If only some chapters are available, retain `PARTIAL_SOURCE` and state that limit.

An import does not delete records missing from that snapshot. Review duplicate or
superseded provisional records separately. Never combine independently generated
files that reused the same UUID pool without reconciling their identities first.

## What has been tested

Prompt v4.0 was exercised on a full chapter and, separately, in an isolated
Frederick II extraction from the same chapter. The targeted first response
contained 20 Entities, 8 Events and 35 Relations. It passed native import checks
and exact undo/redo checks against KRT-121 revision
`b2064f1fd1563b27d5ff24187b6c847b09655ee0`. Selected source checks found the
ordinary details, attributed concerns and distinct future account preserved.

This is limited test evidence, not an exhaustive completeness benchmark. The
full-chapter review found incorrect neighboring source locators and temporal
problems despite successful import. Those findings motivate the separate source
and timeline checks above. The named-subject instruction was supplied alongside
the unchanged v4.0 prompt; it is not a claim that a revised prompt was benchmarked.
