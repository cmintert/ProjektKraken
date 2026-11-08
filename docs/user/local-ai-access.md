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

The default shares the current world's saved Entity/Event facts, calendar rules
and relationship inventory. Time-context reads also observe world Now and the live
playhead. Separate session options add Longform structure, map
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
| `get_world_overview` | Saved Entity/Event totals, revision-bound saved relationship counts and endpoint-kind breakdown, plus active-calendar metadata. |
| `list_calendars`, `read_calendar_section` | Saved calendar identities and exact month, week, leap-rule and year-variant definitions, with bounded continuation. |
| `get_time_context` | Saved world Now, displayed Now, observed live playhead, calendar identity, view version and a separate system UTC clock. |
| `browse_relationships` | World-wide saved edge identities and predicates, including Event→Event and unresolved endpoints; excludes attribute bodies and date filtering. |
| `search_world` | Matching names and description excerpts around literal matches. |
| `browse_world` | Saved objects filtered by kind, type, tags or an Event date range, with description excerpts and Event timing. |
| `get_object` | Full saved description, public attributes, tags, timestamps, source identity and Event timing. |
| `get_objects` | Between 1 and 25 selected Entity/Event reads, in request order, under one world/revision envelope. Missing IDs have individual `NOT_FOUND` results. |
| `get_context` | Bounded Entity/Event context, including available historical sources, qualified timing and omissions. |
| `list_connections` | Relationships touching one selected Entity, with endpoint identities and temporal evidence; not a world-wide edge inventory. |
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

### Recover from a failed read

Failures have `data: null`, a status, a safe `reason_code` and a specific
`suggested_action`. Tool failures retain MCP's error flag. Do not treat a failed
read as an empty successful result.

| Status/reason | Recovery |
| --- | --- |
| `STALE_CURSOR` / `INVALID_CURSOR`, `CURSOR_EXPIRED` or `CURSOR_BINDING_MISMATCH` | Restart the query from its first page with consistent arguments. |
| `INVALID_DATE` / `LORE_DAY_REQUIRED` | Supply `lore_day`; `required_fields` identifies it. Obtain a coordinate from `get_time_context` if the intended date is world Now or the playhead. |
| `TRANSIENT_FAILURE` | Retry with bounded backoff and the same world/revision preconditions. |
| `BUSY` | Queue the read and retry after `retry_after_ms`; reduce concurrent calls. |
| `TIMEOUT` | Retry after waiting, or reduce the request. Queue time counts toward the deadline. |
| `UNAVAILABLE` | Follow the reason-specific recovery below; do not assume sharing is disabled. |
| `PROTOCOL_ERROR` or `INTERNAL_ERROR` | Check the matching connector installation or report the local error; repeatedly enabling sharing is not a general repair. |

`retryable: true` means an unchanged read can recover after waiting. It does not
authorize an endless retry loop. Bad cursors and missing dates need correction,
not repeated identical calls. `restart_required` means previously gathered
investigation/page state must be re-established.

For `UNAVAILABLE`, `NO_ACTIVE_SESSION` means discovery could not find a current
session. It cannot establish whether Kraken is closed, sharing is off or no world
is open: open Kraken, select a world and enable sharing. When trusted local state
identifies `SHARING_DISABLED`, `SESSION_ENDED` or `NO_WORLD_SELECTED`, the recovery
names that action directly. `APP_UNREACHABLE` means a protected session descriptor
exists but its endpoint cannot be reached; check Kraken and rediscover before
retrying. It does not prove the app is closed.
`WORLD_NOT_READY` identifies a selected world whose database is still loading;
wait for it to finish before enabling sharing again.

`AUTH_REQUIRED` calls for rediscovery of the local session.
`UNSAFE_DISCOVERY`, `INVALID_DISCOVERY` and `LOCAL_RUNTIME_UNAVAILABLE` call for
checking local permissions, restarting local sharing or checking the connector
installation respectively. Never put credentials in chat, weaken permission
checks or expose the endpoint to the internet to repair these errors.

Use **one tool call at a time** for consistent investigations. The local server's
admission ceiling is **four pending requests**, shared across clients and HTTP
setup traffic; it is not four parallel database workers. `get_capabilities.limits`
publishes this ceiling, the recommended concurrency of one and the ten-second
deadline. A separate desktop bridge may impose a lower limit; use the stricter
limit. Requests above capacity return retryable `BUSY` rather than claiming
sharing is unavailable.

### Read calendars and choose a lore time

Use `list_calendars` to enumerate saved definitions in the shared world.
`read_calendar_section` without `calendar_id` selects the active saved calendar;
an explicit ID can read an inactive definition without activating it. If no
calendar is active, the result is `NOT_FOUND` / `NO_ACTIVE_CALENDAR`, not an
invented Gregorian calendar. An empty leap-rule list is a valid saved definition.

The `summary`, `months`, `week`, `leap_year_rules` and `year_variants` sections
preserve saved values and ordering. Leap rules expose `interval`, `skip_interval`,
`reset_interval`, `month_index` and `extra_days`. Rule month indexes are zero-based;
calendar date month/day numbers are one-based. The first explicit variant matching
a year replaces its months and skips algorithmic leap rules. Otherwise, all
applicable leap rules add their changes in saved order, using Kraken's canonical
calendar behavior.

For a large definition, page `year_variant_summaries`, then read
`year_variant_months` with its `variant_index`. `week_day_names` and
`week_day_abbreviations` provide narrower week sections. Cursor/revision rules and
whole-record limits still apply; a single oversized value fails explicitly.

`get_time_context` distinguishes three meanings:

- `world_now` is the **saved** world current-time marker.
- `displayed_world_now` and `playhead` are **live view observations**. A displayed
  Now value can differ from its saved value while a queued save is pending.
- `system_time` is a separate real-world UTC observation with the observed local
  offset/timezone label. It is not a lore date or a calendar-rule definition.

Numeric `lore_day` values are authoritative coordinates; zero and negative values
are valid. Unavailable coordinates are null with a reason, never guessed zero.
Captions use the saved active calendar identified by `calendar_id`; without a
calendar, numeric coordinates remain usable and captions are null.
`observed_at_utc` and `view_version` identify the view snapshot: moving the playhead
alone does not change the database revision. The view is captured for the request,
not promised to remain unchanged until the response arrives.

`at_playhead` does not itself fetch the UI cursor. Read `get_time_context`, choose
the intended world Now/playhead coordinate and pass it explicitly as `lore_day`
to dated context/connection reads. These tools do not navigate or change time.

### Audit relationships and attachment access

`get_world_overview.counts.relationships.total_saved` counts saved relation rows
at the response's world/revision. Its endpoint-kind breakdown includes all four
Entity/Event direction pairs and an unresolved-or-ambiguous bucket. Each relation
ID counts once; self-links, parallel rows and reverse edges retain their identities.
These are not counts of date-active facts, inferred associations, WikiLinks or
dependencies stored only inside attributes.

At one unchanged revision, page `browse_relationships` to reconcile the saved edge
IDs, including Event-only edges. Optional `source_kind`, `target_kind` and
`predicate` filters narrow the inventory. Rows contain endpoint identities/kinds
and the saved predicate; attribute bodies are excluded by this inventory tool,
not counted as known absent. It applies no date filter. Continue to use dated
context and connection evidence to establish historical applicability. Do not
derive a global relationship total by summing Entity connection pages.

Context reads always omit attachments. `attachment_access.included_by_this_tool`
and its reason describe that **tool policy**; `session_metadata_scope_enabled`
and `session_attachment_images_enabled` describe the effective grants for this
session. `get_capabilities.scopes` remains the complete scope inventory.
The schema-v1 compatibility value `omitted_counts.attachment_access_disabled: 1`
is a deprecated boolean policy sentinel, **not an attachment count** or proof
that the session's attachment scope is off. It remains in this schema version;
new clients should use `attachment_access`.

Use `list_attachments` for saved metadata when its scope is enabled and
`get_image_preview` for an allowed image read. A scope grant establishes permission,
not that an attachment record or decodable asset exists. A metadata listing alone
does not verify file availability; preview failures must not be interpreted as
unavailable world sharing.

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
