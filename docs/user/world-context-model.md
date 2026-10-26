# Understand World Context and AI interpretation

World Context presents facts Kraken can retrieve from saved world records.
Generated prose is a model's response to the prompt. A model may interpret or
invent connections, so its response needs review even when the factual input
is correct.

## Deterministic facts and retrieved passages

An Event's **Overview → History & context** provides a bounded, read-only snapshot of persisted
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
asserting them as current. **All history** shows saved connections across dates.
Context and Entity generation share a session-only mode choice; changing worlds
resets it. Undated baseline text and weaker shared-tag/shared-map associations
remain explicitly limited evidence.

Each displayed fact has its own row. Section counts describe loaded entries;
**Show all N** and **Expand all** reveal those entries without fetching more.
In Entity World Context, **Load more connections** retrieves the next batch of
saved direct connections. This includes either direction and custom connection
names; you do not need to choose a special name to make a saved link discoverable.
Recorded state changes remain separate from ordinary connections.

The browser reports how many connections are loaded. The total remains unknown
until it finishes checking the saved links for the selected mode and date.
Date-excluded links are counted separately. A failed read offers **Retry
connections**; a partial result never means that every eligible link was found.
Editing, undo/redo or a change to the world or viewing date restarts the browser.
Loading more preserves your description draft and does not change the playhead.

Other sections still use a bounded snapshot. **Not included in this snapshot**
names their omissions. These sections can overlap; their counts are not a unique
total for the world. Loading more direct connections does not expand the AI input
or change messages already prepared in Preview.

Entity attributes, including statblocks, stay in the Entity editor. They are not
shown as World Context facts or used to discover associations. Possible changes
to the written description remain visible with their uncertainty and source
Event. Description generation can still use relevant Entity attributes.

A connection to an Event records a saved link; it does not by itself prove that
the Event happened or that the Entity participated. An undated custom link can
refer to a future Event. All history does not claim that its links were true at
the same time.

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
