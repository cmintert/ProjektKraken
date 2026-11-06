# KRT-119 verification

Feature: opt-in local read-only MCP access. This page records automated,
rendered and human evidence separately; it is not a compatibility certification.

## Contracts and boundaries

Contracts 2/4/5/6/7/8/9 apply. Settings has immediate Enable/Stop session actions,
independent of its preference drafts. A quiet status-bar action provides Stop.
Use shared secondary/quiet control roles and semantic theme/focus tokens.
Preserve authored drafts, caret, selection, scroll, playhead and undo history.

The SDK adapter and connector contain no world queries. A feature-owned queued
task borrows the existing worker connection. SQLite write denial and cancellation
guards exist only during MCP reads and are removed before ordinary commands.

## Evidence record

- Automated security, real local SDK protocol, SQLite guard, worker-thread,
  Settings, Help and package-contract acceptance set: **103 passed**. The
  repository smoke selector separately passed **21 tests**.
- Native Windows ACL/DPAPI discovery: exercised by transport tests.
- Legacy and modern SDK clients: tested against the real HTTP listener.
- Six-theme/narrow/focus/disabled offscreen renders: [capture manifest](renders/captures.json).
  Reviewed readable narrow/wide controls; these are not native or human evidence.
- Ruff, repository-wide mypy (617 source files), visual policy, complexity policy,
  inspection review, offline Help and Sphinx HTML builds passed at their recorded
  checkpoints. No complexity allowances or visual baselines were expanded.
- Complete test-discovery policy passed without regenerating its baseline:
  7,790 collected tests, including the explicitly marked new MCP coverage.
- Packaged full Windows application: incomplete. The first collector stalled and
  was interrupted; its partial runtime failed bootstrap and is not release evidence.
- Standalone console relay: built. Source-host interoperability initially failed
  because Microsoft Store Python virtualizes local application-data storage.
  The frozen verification host and frozen connector subsequently passed legacy
  and modern tool discovery and `get_active_world`, with only Windows system
  directories on `PATH`. See [packaged connector result](frozen-connector.json).
  This uses the actual queued database worker, not the complete Kraken shell.
- Claude `.mcpb` and ChatGPT plugin ZIP archives: generated and ZIP integrity
  checked from the standalone connector runtime. Installation is unverified.
- MCP Inspector CLI: source connector `tools/list` returned all five fixed tools.
  This is discovery evidence, not a successful desktop conversation.
- Claude Desktop and Codex conversations: pending.
- ChatGPT locally executing Desktop chat: unverified.
- Human UI review, prose/live Help approval and reader observation: pending.

## Documentation review and reader observation

### Richer read tools and compact responses — 6 November 2026

- Source MCP regression set: **63 passed** across read-service, richer-read,
  transport, queued-coordinator and architecture tests. Real HTTP and source
  stdio clients discover all eight tools and call the additions in legacy/auto
  SDK modes. Transport fixtures use isolated discovery and stub responses;
  worker/service tests separately verify real saved facts and thread ownership.
- Help bundle/inspection regressions: **43 passed, 1 skipped** in the combined
  verification run before the final three request-validation cases were added.
- Verified full/compact equality, byte savings with repeated facts, literal
  authored `$ref` values, different projections sharing an ID, public attributes,
  reconciled tags, provenance, custom-calendar and dependent timing, possible
  overlap, strict/disjoint boundaries, empty continuation, stale world/session
  cursors, missing batch records, timeout and response-size failures.
- Activity IDs now come from typed factual positions; authored attribute `id`
  values and missing batch records are excluded from that log.
- Repository-wide Ruff and mypy (**621 source files**), visual and complexity
  policies, Help inspection, strict Sphinx HTML and offline Help generation passed.
- Offscreen Chromium captures of the updated manual table/compact reference and
  generated offline content were inspected. Retained under ignored
  `artifacts/krt119/rich-mcp-reference/`; software rendering was required after
  the first GPU captures were blank. These are rendered-content checks, not
  human/live Help acceptance or a native theme/interaction review.
- The earlier frozen five-tool connector results above remain historical.
  This extension has **not** been rebuilt or verified in the Windows package or
  an independent desktop conversation. Human acceptance remains pending.

| Field | Record |
| --- | --- |
| Issue and purpose | KRT-119; connect a desktop assistant and stop sharing safely |
| Reader and assumed knowledge | Kraken user with a compatible desktop MCP client |
| Primary purpose | How-to, with a bounded client-setup reference |
| Canonical page and Help ID | `user/local-ai-access.md`; `integrations.mcp` |
| Behavior inspected | session coordinator, transport/discovery, read task/service, Settings form |
| Help preservation | New topic and enable/stop/activity excerpts; existing topic meanings retained |
| Review boundary | Source/automated/rendered checks only; human prose/live Help approval pending |
| Reader task | Configure client, enable, retrieve a known entry, stop and confirm no further access |
| Participants and observed outcome | Not tested; no completion-time or learnability claim |
| Follow-up | Native client conversations and full packaged-app verification before release |

## Implementation limits

Whole-world session authorization applies to configured clients under the current
OS user, not individual chat identities. It does not protect against same-user
malware or retract already delivered excerpts. Context calls refuse inputs above
5,000 records per major table; bounded search and connection paging remain.

## Retained artifacts

Ignored `artifacts/krt119/` retains the interrupted full-app build, initial failing
mixed-runtime reports and client archives, the successful standalone build and
frozen verification host, and `delivery-client-packages/`. Earlier attempts are
not release candidates. No artifact cleanup, installation or publication occurred.
