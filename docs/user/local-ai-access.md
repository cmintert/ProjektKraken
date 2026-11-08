(help-local-ai-access)=

# Discuss your world with a local AI connector

Use **Settings Center → Kraken → Integrations → Local AI access (MCP)** to let
a compatible desktop assistant read saved facts from your current world.
Sharing starts off. It needs no Kraken API key, cloud account or local model.
Your assistant has its own account and availability requirements.

## Connect and enable sharing

1. Configure your client once to launch **KrakenMCP.exe** from your Kraken
   installation. Keep the executable beside its `_internal` runtime folder.
   The examples below use a placeholder installation path; replace it with yours.
2. Open the world you want to discuss in Kraken.
3. Open **Settings Center → Kraken → Integrations**. Read the sharing disclosure.
4. Choose **Enable for this session**. Wait for **Active** and the persistent
   **MCP sharing on** control in Kraken's status bar.
5. In your assistant, ask it to identify the shared world, then retrieve a known
   Entity or Event. Check the returned record IDs and dates against Kraken.

The default shares the current world's saved Entity/Event facts and their
contextual connections. Separate session options add Longform structure, map
facts, attachment captions, image previews and local semantic search. Unsaved
drafts, arbitrary file browsing, credentials and other registered worlds remain
excluded. No write tools exist.
Whole-world sharing can include sensitive information you wrote into ordinary
prose; Kraken cannot recognize every secret in authored text.

The endpoint is local to your computer. The assistant may send returned excerpts
to its AI provider. This is not an offline AI processing guarantee. Configured
clients under your operating-system account share the same authorization; this
does not defend against malicious software already running as that user.

## Client setup reference

For Claude Desktop, add this entry to its local MCP server configuration using
the client's supported configuration workflow, then restart the client:

```json
{
  "mcpServers": {
    "projektkraken": {
      "command": "C:\\Apps\\Kraken\\KrakenMCP.exe",
      "args": []
    }
  }
}
```

For Codex, add the equivalent entry to its MCP configuration:

```toml
[mcp_servers.projektkraken]
command = 'C:\Apps\Kraken\KrakenMCP.exe'
args = []
```

No credential belongs in either configuration. The connector discovers each
explicitly enabled Kraken session through protected local storage.

Maintainers can generate a Claude desktop extension and a ChatGPT desktop-only
plugin from a built Windows package with `python -m scripts.package_mcp_clients`.
These packages launch the same connector. ChatGPT support is unverified until
the installed plugin successfully calls a tool in a locally executing Desktop
chat. Public local-plugin distribution may require OpenAI approval; installation
does not make the connector available to web or mobile chats. No public server
or tunnel is provided.

Source-checkout users can configure the checkout's Python executable with
`-m src.integrations.mcp.connector`, using the repository root as the working
directory. Packaged users do not need Python or Node installed.
Use the same Python environment for a source host and its connector. Microsoft
Store Python can redirect application-data storage; mixing that source host with
the frozen connector can make the active session undiscoverable.

## Stop and recover

(help-mcp-stop)=

Choose **MCP sharing on → Stop sharing**, or **Stop sharing** in Integrations.
Kraken revokes the credential first, discards unfinished results and closes the
endpoint. Already returned content cannot be retracted. Settings Apply/Cancel
does not control these immediate actions; closing Settings leaves sharing on.

Restarting Kraken, changing worlds, restoring a database or closing the app
requires enabling access again. A close attempt also stops sharing even if you
cancel closing to keep editing a draft.

If access cannot start securely, stop sharing in another Kraken instance and try
again. Only one session can be published per user. If the assistant reports
**UNAVAILABLE**, confirm that Kraken shows **Active**; never fix this by adding
credentials to the chat or exposing the endpoint to the internet.

## Results and limits

### Available reads

| Tool | Returned information |
| --- | --- |
| `get_active_world` | Identity and name of the explicitly shared world. |
| `get_world_overview` | Saved Entity/Event totals and counts by type, plus the active calendar's name, ID, epoch, standard months and week. Flags identify calendars with year variants or leap rules. |
| `search_world` | Matching names and description excerpts around literal matches. |
| `browse_world` | Saved objects filtered by kind, type, tags or an Event date range, with description excerpts and Event timing. |
| `get_object` | Full saved description, public attributes, tags, timestamps, source identity and Event timing. |
| `get_objects` | Between 1 and 25 selected Entity/Event reads, in request order, under one world/revision envelope. Missing IDs have individual `NOT_FOUND` results. |
| `get_context` | Bounded Entity/Event context, including available historical sources, qualified timing and omissions. |
| `list_connections` | Directed relationships, endpoint identities and temporal evidence. |
| `get_capabilities` | Enabled scopes, available tools, limits and semantic preparation state. |
| `get_object_summary` | Identity, timing and sizes of saved sections, without full prose. |
| `read_object_section` | Exact description pages or whole public attributes/tags. |
| `read_context_section` | Historical context sections before the presentation budget, retaining sources and omissions. |
| `browse_facets` | Saved types and reconciled tags for filtering. |
| `read_longform` | Saved reading order, hierarchy, title overrides and underlying object IDs. |
| `browse_maps`, `read_map` | Map identities, descriptions, layers and features; optional date evaluation retains validity and geometry sources. |
| `list_attachments` | Saved captions, IDs, order and dimensions; original filenames and paths are excluded. |
| `search_shared_content` | Lexical search in enabled Longform text, map descriptions and attachment captions. |
| `get_image_preview` | A bounded raster preview or map crop with its saved variant identity. |
| `semantic_search` | Optional prepared local Entity/Event search; otherwise explicitly labelled lexical results. |

Object fields describe the saved record. Use date-scoped context to establish
historical state. Saved-field `provenance` identifies the source object; resolved
context attributes retain their available Event/relation sources. A source marked
`unavailable` means provenance was not supplied, not that a supporting Event exists.
Private metadata and credential/path-bearing attributes remain excluded. Image
previews require separate consent. Ordinary authored prose is returned as written.
`omitted_counts.restricted_fields` counts filtered fields without revealing their
names or values. Ordinary attribute names such as **Telepathy** remain visible.

Event reads retain numeric lore dates alongside calendar-aware `temporal` captions,
bounds, precision, qualifiers and unresolved status. `start`, independent `end`,
`authored_duration` and `presence` remain separate. `authored_timing` contains the
typed timing definition, including followed Event IDs and offset units. No active
calendar is invented when one is unavailable. Dependent Event timing uses the
existing solver, bounded to 5,000 relevant Events per request; above that limit,
saved fields remain readable but timing reports `TIMING_LIMIT` as unresolved.

### Browse without a search term

For example, a client can request Events with both tags in a lore-day range:

```json
{
  "kinds": ["event"],
  "types": ["battle", "siege"],
  "tags": ["Northwatch", "Campaign"],
  "date_from": 120,
  "date_to": 180,
  "limit": 25
}
```

Kind and type alternatives use **OR**; requested tags use **AND**, with
case-insensitive tag-name matching. Filter categories combine with **AND**.
Omitted type/tag filters impose no restriction. Date filters require
`kinds: ["event"]`; Entities have no occurrence date. One date bound may be
omitted. The query endpoints are inclusive; authored timing's strict endpoints
remain strict.

Date browsing includes **possible overlap**, with `date_match` distinguishing
`possible` from `definite`. It does not treat an Event's stored representative
coordinate as its full occurrence range. Unresolved timing is excluded from
date matches and counted explicitly. `omitted_counts` and `evaluated_count`
describe only the current candidate batch, not totals for the world.

Browsing evaluates at most 100 candidates per call and returns up to 25 matching
rows in stable kind/ID order. Follow `next_cursor` until `done` is true, even if a
batch has no matching rows. Keep the same filters and limit on continuation.

### Optional lossless compact responses

Object, batch, context and connection tools accept `detail: "compact"`.
The default is `"full"`. Compact mode preserves the same public facts, descriptions,
list membership, timing evidence and omissions, while pooling identical repeated
records when doing so saves bytes. Different projections of the same ID remain
distinct.

Compact `data` has two fields: `content` and `references`. For example, these
illustrative connection endpoints share one referenced Entity:

```json
{
  "content": {
    "rows": [
      {"id": "relation-1", "source": {"$ref": "r1"}},
      {"id": "relation-2", "source": {"$ref": "r1"}}
    ]
  },
  "references": {
    "r1": {"id": "entity-1", "object_type": "entity", "name": "Northwatch"}
  }
}
```

This example omits other relation fields and the outer response envelope.
Reference keys last for one response only. Resolve `$ref` only at typed record
positions: object/batch results, context items, Events, relations, tags and source
records. Authored attribute dictionaries and attribute `value` fields are literal
JSON, including any `$ref` keys written by the author. Reference-table entries
contain expanded records. A response with no useful repetition still uses the
compact wrapper, with an empty reference table.

Malformed batches fail as a whole. Timeouts, world changes and oversized results
also fail the whole request rather than returning an apparently complete batch.

Search returns at most 25 records per page. Connection browsing uses bounded
candidate batches; follow its continuation even when a batch contains no rows.
Changed records invalidate continuation handles: restart the query rather than
combining different revisions. An omission is not evidence that a fact never
existed.

Date-scoped Entity context requires an explicit lore day and preserves Kraken's date
qualifications and source IDs. Saved object fields differ from an Entity's
resolved state at a date. The assistant must retrieve historical context for
historical claims.
Event context uses the Event's recorded date unless an evaluation date is supplied.

Requests have a ten-second deadline and bounded payloads. Large worlds use relevant
context inputs rather than loading unrelated descriptions. **CONTEXT_LIMIT** means
the relevant input set or a connected timing component exceeds its 5,000-record
budget; use search, object reads and connection pages instead.
**RESULT_TOO_LARGE** means the result exceeds the 64 KiB tool-response limit;
use a summary and section reads to recover long descriptions. An indivisible
structured value that exceeds a page still fails explicitly. No apparently complete
shortened value is substituted.

### Keep one investigation consistent

Each tool accepts optional `expected_world_id`, `expected_revision` and
`expected_session_generation`. Begin with `get_active_world`, then pass its
identity, revision and generation to subsequent reads. If a precondition fails,
the tool returns **WORLD_CHANGED** without replacement-world facts. Restart the
investigation instead of combining old and new evidence.

Section tools return `done`, `next_cursor` and source identity. Follow continuations
with unchanged arguments. Text pages contain exact authored characters with
`offset`, `until` and `total_length`, measured in Unicode characters; a page contains
at most 8,000 characters and may be smaller to fit the byte budget. Historical
description pages retain their source on every page. `done` describes that section,
not the completeness of all world knowledge; inspect `omitted_counts` too.

`search_world` keeps stable identity ordering by default. Request
`ranking: "relevance"` for exact-name, prefix, name-substring and description-match
priority. Type alternatives use OR and tags use AND. Unicode matching preserves
original spelling; description excerpts include original character offsets.

`semantic_search` returns a bounded top-K result without continuation, including
when it falls back to lexical matching. Lexical fallback reports `truncated: true`
and `partial: true` when more matches exist; use `search_world` to page through
lexical matches. Its `done: true` means that top-K request has finished.

### Share additional saved content

Open **Additional sharing options** and select only the optional scopes you need
before enabling sharing. Stop sharing
before changing those choices, then enable a new session. Stopping clears the
options; they are never saved as preferences.
`search_shared_content` searches the enabled scopes by default. Explicitly asking
for a disabled content kind returns **SCOPE_DISABLED**.

Longform reads return saved structure and references to existing Entity/Event
text, rather than a second manuscript. Deliberately excluded entries stay excluded.
Map reads distinguish saved visibility, date-qualified validity and resolved
geometry or position. An uncertain or unresolved presence is not definite location
evidence. Read a map's `description` section for long notes.

Image access also requires map or attachment sharing. Previews are raster images,
at most 1,024 pixels on the longest edge; normalized map crops
`[left, top, right, bottom]` return tiles at most 512 pixels per edge. Map metadata
lists exact `variant_id` values for the base image and saved raster states. A preview
does not render vector overlays or promise the same raster colour treatment as
Kraken's map view. Original downloads and OCR are unavailable.
Use the map's paged `images` section when its metadata says the variant list is
incomplete.

Image results have a separate 512 KiB ceiling. Source assets above 64 MiB or
64 million pixels, unsupported formats, missing assets and files outside the world's
managed assets are unavailable. Previews strip embedded metadata and retain source
identity, dimensions, crop and an asset revision. They may be sent to the assistant's
AI provider just like text already returned.

### Prepare optional local semantic search

1. Open **Additional sharing options**, select **Enable local semantic search**,
   then choose **Enable for this session**.
2. Preparation starts automatically once sharing is active. Wait for
   **Semantic search: ready**, then request `semantic_search`.

Preparation uses the configured sentence-transformers model only when already
installed locally. It never downloads a model or uses an external embedding
provider. If preparation is unavailable, check the configured local model and
choose **Retry semantic preparation**. Lexical search remains available meanwhile.

Preparation copies public Entity/Event fields in bounded background steps. The
prepared index and local model stay in memory for this session so queries reuse
the loaded model. It supports up to 50,000 objects and
64 MiB of public text. Map notes, captions and document structure are not
semantically indexed. Saved changes trigger automatic preparation again after
edits settle; results use labelled lexical fallback until the updated index is ready.
Stop sharing to cancel preparation and release the index and model.

If the model is unavailable, the scope is disabled or the index is unprepared or
stale, results say `effective_search: "lexical"` and include a fallback reason.
Semantic scores express relevance, never confidence that a fact is true. Search
still works without a model. Installed-model and independent desktop-client
acceptance are recorded separately from mocked inference and protocol tests.

(help-mcp-enable)=

**Enable for this session** shares the current saved world with configured local
clients. Access lasts until you stop it or Kraken's world/session ends. It never
persists as an enabled preference. Optional scope choices apply to that session
only. Selecting semantic search also opts into automatic local preparation and
refresh for that session; tool calls cannot enable it or install models.

(help-mcp-activity)=

**Activity details** shows the latest 200 requests in memory: operation, returned
record IDs, outcome, elapsed time and byte count. It does not store query text,
returned prose or credentials. Closing Kraken clears this history.
