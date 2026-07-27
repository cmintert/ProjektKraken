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

## Manage task templates

Open the Task Templates area in AI settings. Bundled templates are read-only;
duplicate one into the active world before customizing it. World templates
travel with that world.

## Use the Analysis Suite

Open **Analysis Suite** from **View**. Its tabs can:

- validate references and world consistency;
- inspect temporal relationships and character lifespans;
- identify intelligence or lore gaps for further review.

Analysis results are advisory. Review the underlying events and relations
before changing established lore.

