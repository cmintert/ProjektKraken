# Understand World Context and AI interpretation

World Context presents facts Kraken can retrieve from saved world records.
Generated prose is a model's response to the prompt. A model may interpret or
invent connections, so its response needs review even when the factual input
is correct.

## Deterministic facts and retrieved passages

An Event's **Context** tab provides a bounded, read-only snapshot of persisted
people, places, references, nearby Events, relations and active-map facts at
the date shown in the editor. It does not ask a model to infer story meaning.
For example, a path crossing a region establishes geometric overlap, not
political permission to cross it.

**World Context** supplies that factual snapshot to Event generation at the
draft Event date. **Retrieved Context** separately uses similarity search
against the AI index. Relevant-looking text is not independent verification of
a historical claim. These options can be enabled independently.

## Entity history and viewed location

Entity Context summarizes durable evidence about the Entity, including authored
attributes, relations, Event appearances, references and history. It is not a
current-state projection at the Timeline playhead. Date-bounded relations are
shown as history. Optional Entity spatial context is a separate source evaluated
at the playhead. Weak shared-tag or shared-map associations remain evidence,
not asserted relationships.

## Review before applying

Inspect the exact World Context block with **Show** after generation, then
review the proposed prose. **Replace** and **Append** deliberately apply the
response; generation alone does not insert it. Explicit dates in AI-reviewed
descriptions must be removed before those actions become available. Manually
written dates are not subject to that AI-output guard.

Use {ref}`generation <help-writing-ai>`, {ref}`search <help-ai-search>` and
{ref}`analysis <help-analysis-review>` for operational steps and current limits.
