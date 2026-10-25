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

Entity Context defaults to **At playhead**, using saved state changes and the same
relationship timing policy as the graph. It keeps definite facts separate from
possible changes and unknown timing, and names the supporting Events. It cannot
recover dates that were never authored or infer historical truth from prose.

**History to playhead** adds prior occurrences and ended relationships without
asserting them as current. **All history** retains the complete durable overview.
Context and Entity generation share a session-only mode choice; changing worlds
resets it. Undated baseline text and weaker shared-tag/shared-map associations
remain explicitly limited evidence.

Optional Entity spatial context is separately evaluated at the captured viewing
date. All history is a historical overview, not a claim that every saved relation
and map placement was simultaneously true.

## Review before applying

For Entity generation, **Generate** inside **Preview** sends the exact prepared
messages. Changed context requires **Refresh** before sending. You can also inspect
the exact World Context block with **Show** after generation, then
review the proposed prose. **Replace** and **Append** deliberately apply the
response; generation alone does not insert it. Explicit dates in AI-reviewed
descriptions must be removed before those actions become available. Manually
written dates are not subject to that AI-output guard.

Use {ref}`generation <help-writing-ai>`, {ref}`search <help-ai-search>` and
{ref}`analysis <help-analysis-review>` for operational steps and current limits.
