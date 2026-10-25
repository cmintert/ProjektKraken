# Search, AI, and Analysis

## What this does

ProjektKraken can index world content for semantic search, ask a configured
local model to help revise descriptions, and analyze the world's internal
consistency.

Generation and semantic search need their configured providers; deterministic
World Context does not call a model. Start with an open world and the relevant
model server available. See [World Context and AI interpretation](world-context-model.md)
before treating generated text or search results as historical evidence.

(help-settings-ai)=

## Configure LM Studio

1. Open **Settings → Kraken → AI**.
2. Enter the LM Studio server address, such as `http://localhost:1234`.
3. Choose **Refresh Models** for the relevant provider.
4. Choose a generation model and, when needed, a separate embedding model.
5. Check the connection result and choose **Apply** or **OK**. Edits remain
   pending until applied; **Cancel** discards unapplied changes.

Enter the server address, not a `/completions` or `/embeddings` endpoint.
Cloud-provider controls remain unavailable until their adapters are enabled.

(help-ai-search)=

## Search the world

1. Open **Settings → Kraken → AI**.
   Choose **Rebuild Index** when the index needs rebuilding and wait for
   completion.
2. Open **View → Panels → AI Search**.
3. Enter a natural-language query and choose **Search**.
4. Review the returned entries and open the intended result.

Results can include Events and Entities ranked by relevance. Search does not
rewrite their content. If the expected entry is absent, check index status and
provider settings before concluding that the world has no matching record.

Search quality depends on the selected embedding model and the freshness of the
index.

(help-writing-ai)=

## Generate or revise a description

1. Select an event or entity.
2. Open its generation section.
3. Choose Create, Revise, Expand, or Condense.
4. Apply the template to the editable prompt.
5. Generate and review the response.
6. Choose **Replace**, **Append**, or **Discard**.
7. Save the edited entry and reopen it to verify the accepted description.

Replace changes the description; Append adds the accepted response to it.
Discard rejects the proposed response. Review factual claims before either
accepting action, and use supported text/content Undo if an accepted edit is wrong.

Selecting a template does not overwrite the draft. Generated text is not
inserted until you explicitly apply it.

### World Context

An Event's **Overview → History & context** immediately shows persisted people, places,
mentions, nearby Events, relations, and active-map facts that Kraken can
determine at the date currently shown in the Event editor. This view is
read-only and deterministic: it does not call a model or infer story meaning.
Map facts use resolved point, path, and region geometry on north-up maps. They
describe geometric evidence such as proximity, containment, crossing, and
overlap, but do not infer access, political function, or narrative importance.
Each fact occupies its own row, with timing and source information beneath it.
Section headings count the loaded entries. A section initially shows up to three
rows; choose **Show all N** to reveal its remaining rows, or **Show fewer** to
return to the preview. **Expand all / Collapse all** controls all sections.
These controls reveal the loaded snapshot only. **Not included in this snapshot**
lists omitted facts; expanding does not retrieve them. Select a linked name to
navigate to it.

**World Context** is enabled by default when generating Event text. It sends
the same bounded factual snapshot to the model, evaluated at the Event's draft
date. **Retrieved Context** is separate: it uses similarity search against the
AI index and can be enabled or disabled independently. Event World Context
already includes map facts at the Event date, so Event prompts do not also use
the timeline-playhead spatial block. Entity spatial generation remains based
on the playhead.

After generation, choose **Show** beside World Context to inspect the exact
authoritative block sent to the provider. Disable **World Context** when you
want the model to receive only the Event itself and any independently enabled
retrieved context.

An Entity's **Overview → History & context** answers what Kraken durably knows about it:
public structured attributes and tags, incoming and outgoing relations, Event
appearances with their authored roles, explicit wiki-link references, temporal
history, map placement and ancestry, shared Event appearances, authored image
captions, and weaker shared-tag or shared-map associations. Weaker associations
are labelled as evidence rather than relationships. Private attributes whose
names begin with an underscore, sheet layout, generated summaries, raw image
data, and inferred prose associations are never included. Entity Context starts **At playhead**: it shows saved description and attribute
changes and the relationships applicable at the selected Timeline date. Possible
changes and unknown timing remain qualified, with links to supporting Events.
Undated baseline text, tags, captions and map placements do not establish a dated
state. Shared-tag and shared-map evidence does not establish a relationship.

Choose **History to playhead** to include prior Events and ended relationships,
while excluding definitely future occurrences. Choose **All history** for the
durable overview across dates. The Context and Entity generation controls share
this choice while navigating between Entities. Switching worlds resets it to
At playhead. Choosing a mode does not move the playhead or edit your world.

To inspect a changing Entity:

1. Open **Overview → History & context** and choose **At playhead**.
2. Move to the Timeline date you want to inspect, completing any existing draft
   decision first. Check the date shown above the saved facts.
3. Follow a named supporting Event to inspect the source, using the normal
   navigation safeguards. Check **Possible changes — not established** and
   **Timing notices** when present. State-change records appear separately from
   ordinary relationships.
4. Use a history mode to inspect relationships absent from the current view.
   No current relationship means none is established by the available authored
   records; it does not prove that no relationship existed.

Entity generation uses the same mode and date policy. Its **Preview** prepares
World Context, optional retrieved passages and optional spatial context in the
background. **Generate** inside that preview sends the exact displayed messages.
If the context changes, **Refresh** prepares a new snapshot before Generate becomes
available again. Ordinary Generate prepares fresh context. Spatial context stays
separately labeled and uses the captured viewing date, even in All history mode.
The current description draft is author input, separate from saved World Context.
Missing date-scoped context reports an error instead of silently using history.

Generated Event and Entity descriptions cannot contain explicit dates. Kraken
still uses timeline dates to select and organize factual context, but the model
must express the stable fact without calendar dates, years, era-qualified years,
or raw lore-date numbers. If a generated response contains one, the review
window identifies it and keeps **Replace** and **Append** disabled until it is
removed. Relative wording such as “later” or “after the siege” remains allowed.
This guard applies only to AI-reviewed output; manually written descriptions are
not blocked.

(help-writing-summary)=

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

(help-writing-templates)=

## Manage task templates

Open **Settings → This World → AI** and find **World task templates**.
Bundled templates are read-only;
duplicate one into the active world before customizing it. World templates
travel with that world. **Update template draft** prepares a template change;
choose **Apply** to save it with the other world settings.

(help-analysis-review)=

## Use the Analysis Suite

Open **View → Panels → Analysis**. Its tabs can:

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
primary source. Lore rows show a compact title preview; select one to read its
complete suggestions in the scrollable **Suggestion Details** pane. Lore
suggestions are explicitly creative; they cite the two events bounding the gap.

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

(help-graph-exploring)=

## Explore connections in the Graph

The Graph displays relations between world entries. Search and filters change the
connections shown; they do not edit those relations. Viewed time and the selected
temporal mode determine which historical connections are visible. Use a deliberate
inspector navigation action to edit an entry.

1. Open **View → Panels → Graph**.
2. Choose the temporal mode appropriate to the question you are asking.
3. Search or filter to inspect the relevant connections, then clear the filter
   to restore the broader view.

Read direction and uncertainty labels before interpreting an edge. See
{ref}`relation timing in the Graph <help-relations-timing>` for the temporal
modes. A hidden edge has not been deleted.

## Interface control reference

These explanations describe the software operation. Inspecting a control does not run it or read your entered values.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-init-self-sidebar-list)=

**AI settings pages** — Choose text generation, knowledge-base, prompt or task-template
settings. Provider and indexing settings serve different purposes.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-init-cancel-btn)=

**Cancel** — Discard unapplied Settings Center changes and close. Changes acknowledged
by an earlier Apply remain saved.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-init-ok-btn)=

**OK** — Validate and apply pending Settings Center edits, then close after successful
persistence. Invalid or failed edits remain available for correction.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-gen-provider-combo)=

**Text generation provider** — Choose which configured provider generates text. This is
separate from the embedding provider used for search.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-lm-gen-enabled)=

**Enable LM Studio generation** — Enable the local LM Studio text-generation
configuration. The server must be running with a suitable model loaded.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-lm-gen-use-chat-api)=

**Chat Mode:** — Use /v1/chat/completions with messages format. Recommended for modern
models.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-lm-gen-url-input)=

**Server URL:** — LM Studio server address. Kraken derives /v1/models and API endpoints.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-btn-test-lm-gen)=

**Refresh models** — Contact the configured LM Studio server and refresh its available
text-generation models. This does not generate prose.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-lm-gen-model-input)=

**Model:** — Choose the model used by AI settings. The available model must be supported
by the configured provider.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-openai-gen-enabled)=

**Enable OpenAI generation** — Enable the OpenAI text-generation configuration. Requests
use the configured credentials and model.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-openai-api-key-input)=

**API Key:** — Enter the credentials required by the selected service. Help never reads
or displays the credential value. Saving settings is separate from making a request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-openai-model-input)=

**Model:** — Choose the model used by AI settings. The available model must be supported
by the configured provider.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-google-gen-enabled)=

**Enable Google generation** — Enable the Google text-generation configuration. Requests
use the configured project, location, credentials and model.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-google-project-input)=

**Google project** — Enter the Google Cloud project used for generation requests.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-google-location-input)=

**Google location** — Enter the service region used for Google generation requests.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-google-model-input)=

**Model:** — Choose the model used by AI settings. The available model must be supported
by the configured provider.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-google-creds-input)=

**Credentials Path:** — Enter the credentials required by the selected service. Help
never reads or displays the credential value. Saving settings is separate from making a
request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-anthropic-gen-enabled)=

**Enable Anthropic generation** — Enable the Anthropic text-generation configuration.
Requests use the configured credentials and model.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-anthropic-api-key-input)=

**API Key:** — Enter the credentials required by the selected service. Help never reads
or displays the credential value. Saving settings is separate from making a request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-anthropic-model-input)=

**Model:** — Choose the model used by AI settings. The available model must be supported
by the configured provider.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-max-tokens-input)=

**Max Tokens:** — Maximum tokens to generate per request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-temperature-input)=

**Generation temperature** — Set generation randomness as a percentage: 100% means 1.0.
This setting does not start a request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-self-enable-audit-log)=

**Audit Log:** — Store structured prompts, raw responses, review decisions, feedback,
and edits in the active world folder.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-generative-ai-page-clear-btn)=

**Reset AI preferences** — Use Reset page in the Settings Center to stage eligible
AI defaults. This does not remove credentials, world templates or world policies.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-provider-combo)=

**Embedding provider** — Choose local Sentence Transformers or LM Studio embeddings for
semantic search. This is separate from text generation.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-st-model-input)=

**Local embedding model** — Choose the Sentence Transformers model used to index and
search world content. Its first use may download the model.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-lm-url-input)=

**Server URL:** — Uses the same LM Studio server as text generation.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-lm-model-input)=

**Embedding model** — Choose an embedding-capable LM Studio model for semantic search. A
text-generation model is not necessarily suitable.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-lm-api-key-input)=

**API Key:** — Enter the credentials required by the selected service. Help never reads
or displays the credential value. Saving settings is separate from making a request.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-btn-test-lm-embed)=

**Refresh embedding models** — Contact LM Studio and refresh its available embedding
models. This does not rebuild the world index.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-lm-timeout-input)=

**Embedding timeout** — Set how many seconds an LM Studio embedding request may take
before timing out.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-rebuild-combo)=

**Index rebuild scope** — Choose whether Rebuild Index processes all entries, Entities
only or Events only.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-btn-rebuild)=

**Rebuild index** — Recreate search embeddings for the chosen entry types using the
configured embedding provider. Saved lore remains unchanged.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-btn-refresh-status)=

**Refresh index status** — Reload the displayed model, indexed-entry count and last-
indexed information without rebuilding the index.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-chk-auto-index)=

**Auto-index on save** — Re-embed entities and events immediately after each save.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-knowledge-base-page-self-excluded-attrs-input)=

**Excluded attributes** — List attribute keys to omit from embedding input. Keys
beginning with an underscore are already excluded.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-prompts-page-self-summary-max-tokens-input)=

**Summary Max Tokens:** — Set the token limit for the corresponding AI operation. This
is a generation/retrieval limit, not a character count.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-prompts-page-self-summary-temperature-input)=

**Summary Temperature:** — Adjust generation randomness. Higher values allow more
variation; changing the setting does not generate or accept text.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-prompts-page-self-filter-reasoning-cb)=

**Filter reasoning tags (&lt;think&gt;, &lt;reasoning&gt;)** — Remove supported
reasoning-tag blocks from model responses before they are used as generated text. This
does not change the request sent to the provider.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-template-list)=

**Task templates** — Select a reusable AI task to view or edit its name, purpose, intent
and prompt. Built-in and world templates have different editing permissions.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-btn-new-template)=

**New task template** — Create a world task template that can be selected in the
generation controls.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-btn-refresh-templates)=

**Refresh templates** — Reload available task templates from their configured locations.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-template-name-edit)=

**Template name** — Name this reusable generation task so you can identify it in the
template chooser.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-template-description-edit)=

**Description:** — Explain when this task is useful.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-template-intent-combo)=

**Template intent** — Choose the task's intent classification. This describes the
intended kind of generated output.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-btn-delete-template)=

**Delete template** — Delete the selected editable task template. Built-in templates
cannot be deleted here.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-btn-duplicate-template)=

**Duplicate to world** — Copy the selected template into this world's editable
templates, leaving the original available.

(help-inspect-src-gui-dialogs-ai-settings-dialog-aisettingsdialog-create-templates-page-self-btn-save-template)=

**Update template draft** — Prepare edits to this world task template. Apply in the
Settings Center persists them; Cancel discards unapplied changes. This does not
generate or accept prose.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-scope-combo)=

**Analysis scope** — Choose which entries the AI analysis may inspect: the whole world,
current item, selected IDs, selected tags or an inclusive date range.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-selection-edit)=

**Selection IDs** — Enter comma-separated entry IDs for the multi-selection analysis
scope. The dialog requires a valid selection before starting.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-tags-edit)=

**Analysis tags** — Enter comma-separated tags. The tag scope includes entries carrying
any selected tag.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-preset-combo)=

**Analysis preset** — Choose the analysis request preset. The displayed coverage summary
shows the resulting scope and limits.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-plot-holes)=

**Plot holes** — Include advisory plot-hole findings in this AI analysis. Findings do
not rewrite world content.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-relations)=

**Relation gaps** — Include advisory findings about missing or inconsistent connections.
Suggestions do not create relations.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-lore)=

**Lore suggestions** — Include advisory lore suggestions. Review them before making any
separate authored change.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-build-ui-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-analysis-run-dialog-analysisrundialog-date-spin-spin)=

**Analysis date range** — Set a boundary of the inclusive lore-date range, measured in
lore days. These values limit analysis; they do not move the Timeline.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-text-edit)=

**Generated proposal** — Review or edit the generated proposal before choosing Append,
Replace or Discard.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-thumbs-up-btn)=

**Positive feedback** — Record that this generated proposal was useful. Feedback does
not accept it into the description.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-thumbs-down-btn)=

**Negative feedback** — Record that this generated proposal was unhelpful. Feedback does
not replace or discard the description.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-comment-edit)=

**Generation feedback** — Optionally describe what worked or needs correction in this
proposal. This is feedback, not the entry's description.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-discard-btn)=

**Discard** — Discard the generated proposal without accepting it into the description.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-append-btn)=

**Append** — Append the reviewed generated text to the description. Generation alone
does not require you to accept this text.

(help-inspect-src-gui-dialogs-generation-review-dialog-generationreviewdialog-setup-ui-self-replace-btn)=

**Replace** — Replace the description with the reviewed generated text. Review the
replacement before accepting it.

(help-inspect-src-gui-dialogs-graph-filter-dialog-graphfilterdialog-init-self-buttons)=

**Buttons** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-widgets-ai-search-panel-aisearchpanelwidget-init-self-search-input)=

**Search input** — Find matching items in world search. Searching changes the displayed
matches without editing their content.

(help-inspect-src-gui-widgets-ai-search-panel-aisearchpanelwidget-init-self-btn-search)=

**Search** — Find matching items in world search. Searching changes the displayed
matches without editing their content.

(help-inspect-src-gui-widgets-ai-search-panel-aisearchpanelwidget-init-self-filter-combo)=

**Filter combo** — Choose which items are shown in world search. Filtering leaves the
saved world entries and connections unchanged.

(help-inspect-src-gui-widgets-ai-search-panel-aisearchpanelwidget-init-self-top-k-spin)=

**Search result limit** — Set the maximum number of world-search matches to return. This
does not limit the offline Help manual search.

(help-inspect-src-gui-widgets-ai-search-panel-aisearchpanelwidget-init-self-results-list)=

**World-search results** — Choose a search match to open its world entry. Search results
are separate from offline Help results.

(help-inspect-src-gui-widgets-analysis-analysis-panel-analysispanel-init-ui-self-open-source-btn)=

**Open Source** — Open the selected item or resource from Analysis. Review any
unfinished-edit prompt before leaving the current work.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-category-filter)=

**Category filter** — Choose which items are shown in Intelligence. Filtering leaves the
saved world entries and connections unchanged.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-severity-filter)=

**Severity filter** — Choose which items are shown in Intelligence. Filtering leaves the
saved world entries and connections unchanged.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-status-filter)=

**Status filter** — Choose which items are shown in Intelligence. Filtering leaves the
saved world entries and connections unchanged.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-show-dismissed)=

**Show dismissed** — Enable or select show dismissed for Intelligence. Review the
surrounding action before applying this choice.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-dismiss-btn)=

**Dismiss finding** — Mark this advisory finding as dismissed. This does not repair or
delete the referenced world entries.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-open-source-btn)=

**Open Source** — Open the selected item or resource from Intelligence. Review any
unfinished-edit prompt before leaving the current work.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-export-scope)=

**Finding export scope** — Choose which advisory findings to include in the export.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-export-markdown-btn)=

**Export findings as Markdown** — Save the selected scope of advisory findings as a
Markdown report. World content remains unchanged.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-export-json-btn)=

**Export JSON** — Choose the destination and options for exporting the selected content.
Export produces a separate output; it does not delete the source entries.

(help-inspect-src-gui-widgets-analysis-intelligence-panel-intelligencepanel-init-ui-self-evidence-list)=

**Finding evidence** — Review evidence associated with the selected advisory finding
before deciding whether to act on it.

(help-inspect-src-gui-widgets-analysis-main-analysis-panel-mainanalysispanel-init-ui-self-validate-btn)=

**Validate world** — Check saved world data for supported integrity problems. Reading
the findings does not apply repairs.

(help-inspect-src-gui-widgets-analysis-main-analysis-panel-mainanalysispanel-init-ui-self-temporal-btn)=

**Analyze Timeline** — Check temporal constraints and report conflicts. Analysis does
not rewrite Event dates.

(help-inspect-src-gui-widgets-analysis-main-analysis-panel-mainanalysispanel-init-ui-self-intelligence-btn)=

**Run AI analysis** — Choose the scope and categories for advisory AI analysis. Its
results do not automatically modify lore.

(help-inspect-src-gui-widgets-analysis-main-analysis-panel-mainanalysispanel-init-ui-self-cancel-intelligence-btn)=

**Cancel AI analysis** — Request cancellation of the active AI analysis. This does not
discard saved world edits.

(help-inspect-src-gui-widgets-analysis-main-analysis-panel-mainanalysispanel-init-ui-self-editorial-checks)=

**Editorial checks** — Include completeness, sparse-description, isolation, and tag-use
advice.

(help-inspect-src-gui-widgets-analysis-temporal-panel-temporalpanel-init-ui-self-open-conflict-source-btn)=

**Open Source** — Open the selected item or resource from Temporal. Review any
unfinished-edit prompt before leaving the current work.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-search-input)=

**Search input** — Find matching items in Graph. Searching changes the displayed matches
without editing their content.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-adv-filter-btn)=

**Filter...** — Choose which items are shown in Graph. Filtering leaves the saved world
entries and connections unchanged.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-tag-combo)=

**Tag combo** — Show only graph nodes with the selected tag. Tags are not changed.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-rel-type-combo)=

**Rel type combo** — Show only graph edges with the selected relation type.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-lexicon-btn)=

**Graph styles** — Configure node and relation styles under **Settings →
This World → Graph**. Choose Apply to update the graph.

(help-inspect-src-gui-widgets-graph-view-graph-filter-bar-graphfilterbar-setup-ui-self-refresh-btn)=

**Refresh** — Reload graph data using the selected filters.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-template-combo)=

**Template combo** — Choose a reusable task. It is copied only when you select Use
Template and does not change the configured Persona.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-use-template-btn)=

**Use Template** — Copy the selected task into the editable prompt.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-provider-combo)=

**Provider combo** — LM Studio is supported. Cloud providers are planned but disabled.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-max-tokens-spin)=

**Max tokens spin** — Set the token limit for the corresponding AI operation. This is a
generation/retrieval limit, not a character count.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-temperature-spin)=

**Temperature spin** — Temperature (0-200%, where 100% = 1.0).

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-rag-cb)=

**Retrieved context** — Include relevant world passages retrieved for this generation
task. This is separate from deterministic World Context.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-rag-limit-input)=

**Rag limit input** — Number of context items to retrieve (1-20).

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-spatial-cb)=

**Include spatial context** — Include map placement, layer notes, raster classes, and
nearby named entities when available on the active map.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-world-context-cb)=

**Use World Context** — Include deterministic persisted facts known about this item.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-cancel-btn)=

**Cancel generation** — Request cancellation of the active text-generation request.
Saved entry content is not discarded.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-preview-btn)=

**Preview generation input** — Show the assembled prompt and context before generation.
Previewing does not accept generated prose into the description.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-generate-btn)=

**Generate description** — Send the configured prompt and context to the selected
provider. Review the generated proposal before accepting it.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-init-self-spatial-show-btn)=

**Show spatial context** — Read the available map context that can be included in the
generation request.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-build-world-context-status-row-self-world-context-show-btn)=

**Show World Context** — Read the persisted facts prepared as World Context for this
entry.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-show-spatial-context-clicked-text-edit)=

**Spatial context preview** — Read the map placement, layer notes and nearby context
prepared for generation. This preview is read-only.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-show-spatial-context-clicked-close-btn)=

**Close spatial preview** — Close the spatial-context preview without starting
generation.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-show-world-context-clicked-text-edit)=

**World Context preview** — Read the persisted facts prepared for generation. This
preview is read-only.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-show-world-context-clicked-close-btn)=

**Close World Context preview** — Close this preview without starting generation.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-preview-clicked-text-edit)=

**Generation input preview** — Read the assembled generation input, including the chosen
prompt and context. This preview is read-only.

(help-inspect-src-gui-widgets-llm-generation-widget-llmgenerationwidget-on-preview-clicked-close-btn)=

**Close generation preview** — Close the input preview without sending a generation
request.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-init-self-var-combo)=

**Prompt variable** — Insert the chosen supported placeholder into the prompt. Its value
is filled when the request is assembled.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-init-self-btn-restore)=

**Restore prompt** — Restore the prompt's default text. This changes the prompt, not the
entry's description.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-init-self-btn-popout)=

**Expand prompt editor** — Edit this prompt in a larger window. Apply returns the edited
prompt; Cancel retains the previous text.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-init-self-editor)=

**Generation prompt** — Edit instructions sent for this generation task. The prompt is
separate from the entry's authored description.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-open-popout-pop-editor)=

**Expanded prompt** — Edit the generation prompt, then Apply to return it to the
requesting field.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-open-popout-btn-cancel)=

**Cancel** — Cancel this PromptEditor operation without accepting its pending changes.
This is separate from applying or saving them.

(help-inspect-src-gui-widgets-prompt-editor-prompteditorwidget-open-popout-btn-ok)=

**Apply prompt edit** — Use the edited prompt in the requesting field. This does not
start generation or accept generated text.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-text-display)=

**Entry summary** — Read the saved summary, or edit it after choosing Edit. A summary is
separate from the full description.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-cancel-btn)=

**Cancel summary edit** — Discard the current summary edit and retain the saved summary.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-done-btn)=

**Save summary edit** — Save the edited summary and return to its read-only display.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-delete-btn)=

**Delete summary** — Remove this entry's saved summary after confirmation. The main
description is retained.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-edit-btn)=

**Edit summary** — Make the summary editable. Done saves the edit; Cancel retains the
saved summary.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-copy-btn)=

**Copy summary** — Copy the displayed summary text to the clipboard.

(help-inspect-src-gui-widgets-summary-widget-summarywidget-setup-ui-self-generate-btn)=

**Generate summary** — Request a generated summary of this entry using the configured AI
settings. This is separate from generating its full description.

(help-inspect-src-app-ui-manager-uimanager-create-settings-menu-search-settings-action)=

**AI configuration** — Open **Settings → Kraken → AI** for local provider
connections or **This World → AI** for world prompts and indexing exclusions.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-setup-ui-button-box)=

**Button box** — Review the dialog’s choices, then use its acceptance or cancellation
action. Inspecting a button never accepts or rejects the dialog.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-color-btn)=

**Node fill colour** — Choose the fill colour used for this Entity type in the Graph.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-border-color-btn)=

**Node outline colour** — Choose the outline colour used for this Entity type in the
Graph.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-border-width-spin)=

**Node outline width** — Set the Graph outline width for this Entity type.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-size-spin)=

**Node size** — Set the Graph node size for this Entity type.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-shape-combo)=

**Node shape** — Choose the Graph node shape for this Entity type.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-icon-btn)=

**Node icon** — Choose an icon for this Graph Entity type without changing the Entities
themselves.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-node-row-clear-btn)=

**Clear node icon** — Remove the icon override for this Graph Entity type and use its
ordinary shape styling.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-edge-row-color-btn)=

**Relation colour** — Choose the Graph line colour for this relation type.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-edge-row-width-spin)=

**Relation line width** — Set the Graph line width for this relation type.

(help-inspect-src-gui-dialogs-lexicon-editor-dialog-lexiconeditordialog-add-edge-row-dashes-cb)=

**Dashed relation line** — Draw this relation type with a dashed line in the Graph.

(help-inspect-view-src-gui-widgets-graph-view-graph-widget-graphwidget-init-self-web-view)=

**Relationship Graph** — Explore connections between world entries. Selecting a node may
navigate to its entry; inspection leaves selection and node positions unchanged.


(help-inspect-analysis-findings)=

**Analysis findings** — Read the reported findings and select a row to review its evidence or open its source. Findings do not automatically repair or rewrite lore.


(help-entity-world-context-mode)=

**Context mode** — Choose At playhead for saved state and applicable relationships,
History to playhead for knowledge up to that date, or All history for the durable
overview. Entity Context and generation share this session choice; it resets when
switching worlds. This control changes only the read-only context view.

(help-prepared-generation-text)=

**Exact prepared prompt** — Read the complete prepared messages, including the
qualified World Context and any enabled retrieved or spatial evidence.

(help-prepared-generation-generate-button)=

**Generate from preview** — Send the exact displayed messages for model generation.
Generation does not apply the result to your Entity. Review the response and choose
Replace or Append afterward. A stale or unfinished preview cannot be sent.

(help-prepared-generation-refresh-button)=

**Refresh preview** — Prepare new messages using the current saved facts, selected
context mode and viewing date. Wait for preparation to finish before generating.

(help-prepared-generation-close)=

**Close prompt preview** — Leave the preview without generating or changing lore.
