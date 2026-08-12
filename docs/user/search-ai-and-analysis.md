# Search, AI, and Analysis

## What this does

ProjektKraken can index world content for semantic search, ask a configured
local model to help revise descriptions, and analyze the world's internal
consistency.

## Configure LM Studio

1. Open **Settings → AI Search Index and Settings…**.
2. Enter the LM Studio server address, such as `http://localhost:1234`.
3. Refresh the available models.
4. Choose a generation model and, when needed, a separate embedding model.
5. Test the connection and save the settings for the world.

Enter the server address, not a `/completions` or `/embeddings` endpoint.
Cloud-provider controls remain unavailable until their adapters are enabled.

## Search the world

Open the **AI Search** dock, build or refresh the index, and enter a natural
language query. Results can include events and entities ranked by relevance.

Search quality depends on the selected embedding model and the freshness of the
index.

## Generate or revise a description

1. Select an event or entity.
2. Open its generation section.
3. Choose Create, Revise, Expand, or Condense.
4. Apply the template to the editable prompt.
5. Generate and review the response.
6. Choose **Replace**, **Append**, or **Discard**.

Selecting a template does not overwrite the draft. Generated text is not
inserted until you explicitly apply it.

## Manage item summaries

Expand **Summary** in an event or entity editor to generate a compact overview.
For descriptions of 50 words or more, AI summaries target 22% of the source
with a hard limit of 30% and at most 150 words. Shorter descriptions use one
sentence of at most 20 words that must remain shorter than the source.
Summary text uses ordinary prose; wiki-link markup is not preserved. If a
compression retry narrowly exceeds the hard limit, complete trailing sentences
may be removed to produce a valid summary.

Use **Edit** to revise a summary inline. Once edited, it is identified as a
manual summary rather than attributed to the model. Use **Delete** to stage its
removal. Edits, regeneration, and deletion are persisted only when you save the
event or entity; discarding changes restores the stored summary.

## Manage task templates

Open the Task Templates area in AI settings. Bundled templates are read-only;
duplicate one into the active world before customizing it. World templates
travel with that world.

## Use the Analysis Suite

Open **Analysis Suite** from **View**. Its tabs can:

- validate references and world consistency;
- inspect temporal relationships and character lifespans;
- identify intelligence or lore gaps for further review.

World validation always checks objective integrity: broken relation endpoints,
attachments and asset paths, duplicate directed relations, wiki links, dates,
temporal windows, and character lifespans. **Editorial checks** is off by
default; enable it when you also want documentation completeness, minimal
description, isolation, and low-use-tag advice. Documentation completeness is
a transparent 100-point profile. Hover a score to see the earned and available
points for every component.

Choose **Run AI Analysis** to select an explicit scope: the whole world, the
current item, a multi-selection, any of several tags, or an inclusive lore-date
range. Current-item and selection scopes include one-hop context. Date scopes
include events in range and their directly connected objects. Then select Plot
Holes, Relation Gaps, Lore Suggestions, and a Quick, Balanced, or Thorough
request budget. A malformed model response may receive one repair request.

Each AI finding lists deterministic **Strong**, **Moderate**, or **Weak**
evidence strength. Select a row to read its full text and evidence, select the
specific source you want, and choose **Open Source**. Double-clicking opens the
primary source. Lore suggestions are explicitly creative; they cite the two
events bounding the gap.

Section states distinguish complete, partial, failed, skipped, and cancelled
runs. A section reports “no findings” only if at least one candidate completed;
provider failures remain visible with request counts and summaries.

Reports, comparisons, dismissals, and optional dismissal notes live only in the
current application session. Successful edits, imports, restores, calendar or
attachment changes, and external reloads mark reports **stale**. Switching
worlds clears them. Comparisons use stable source fingerprints rather than
generated prose. Reports can be exported as Markdown or JSON.

Analysis is advisory and navigation-only. It never changes world data or opens
a prefilled edit operation.

### Instant temporal relations

**Only valid at Event** is an instant, not an invalid zero-length interval. It
matches the current source-event date to within `0.000000001` lore days and
continues to follow that event when it moves. Manually entered equal start and
end bounds remain invalid; omitted interval ends remain open.
