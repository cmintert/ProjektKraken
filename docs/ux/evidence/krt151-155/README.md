# MCP errors, calendar/time reference and relationship audit

Primary purpose: maintainer verification reference. Scope: KRT-151 through KRT-155,
base `0fd0580ed53dbf071dbd209ccbe51a10d3c9043c`, uncommitted implementation dated
2026-11-08. These results do not certify a new Windows package or independent
desktop-client acceptance.

## Implemented contracts

- **KRT-151:** error envelopes preserve status, safe reason, recovery action and
  retry/restart metadata through SDK/HTTP/stdio. Cursor/date failures remain
  distinct. Identified transport interruptions, SDK connection closure, overload
  and deadlines are retryable; malformed bridge output remains a protocol error.
  No exception prose, paths or credentials are published. Missing discovery means
  NO_ACTIVE_SESSION, not a guessed closed app, disabled sharing or unselected
  world. Trusted local lifecycle state distinguishes those causes and loading.
- **KRT-152:** context attachment omission is an explicit tool policy, separate
  from session metadata/image grants. The schema-v1 legacy sentinel remains
  documented as a boolean flag, not a count or proof of asset presence.
- **KRT-153:** `list_calendars` and `read_calendar_section` expose exact saved
  definitions, active/inactive identity, leap parameters and explicit variants.
  Month indexes/precedence are documented. Large variants have summary and nested
  month-page routes; absent calendars never create a Gregorian fallback.
- **KRT-154:** `get_time_context` distinguishes saved Now, displayed Now, playhead
  and system UTC observation. GUI providers capture view coordinates; worker reads
  supply saved Now and canonical calendar captions, including fractional days.
  View movement has a separate version and does not invalidate the semantic index.
- **KRT-155:** overview counts partition canonical saved relation IDs across all
  four Entity/Event direction pairs plus unresolved/ambiguous endpoints.
  `browse_relationships` pages saved identities/predicates, including Event-only
  links. Attribute bodies and temporal filtering are explicitly excluded; no
  inferred, WikiLink or attribute-only temporal dependencies are counted as rows.

All reads retain world/session/revision checks, opaque bound cursors, 25-row and
byte limits, queued DB ownership and revocation. No new responsibility was added
to DatabaseService, DatabaseWorker, MainWindow or ConnectionManager.

## Automated and source evidence

- Final focused MCP/shared context/temporal/architecture/package-source selection:
  **277 passed**. Tests include real HTTP and stdio errors in both SDK modes,
  connection interruption/recovery, 1/2/4/5 concurrent calls, DB-busy classification,
  discovery reason privacy, exact calendar reconstruction, oversized variant
  recovery, inactive calendar reads, all endpoint-kind pairs, self/parallel edges,
  legacy unresolved/colliding identities and revision changes during paging.
- A real queued-worker test confirms view providers run on the GUI thread while
  saved reads run on the DB worker. Playhead zero/negative/fractional values are
  preserved; view changes keep DB revision unchanged. Trusted Stop/no-world/loading
  causes are tested separately from absent discovery.
- Final coordinator and Help bundle/search/inspection regression selection:
  **87 passed, 1 skipped**. This overlaps the focused MCP selection above and is
  recorded separately rather than added to its count.
- [Baseline comparison](error-baseline.json) reproduces two controlled failures
  against the previous committed relay: SDK invalid parameters and interrupted
  reads became UNAVAILABLE/check_local_sharing. The current classifier preserves
  INVALID_INPUT and TRANSIENT_FAILURE. This is a controlled comparison, not proof
  of the exact cause in the external desktop bridge reported by the owner.
- [Source connector](source-connector.json) verifies all **24 tools** in both SDK
  modes against a disposable world, a real queued worker and isolated encrypted,
  ACL-protected discovery. It records invalid-cursor and missing-lore-day envelopes
  followed by healthy reads, exact text paging, native images, saved calendar rules,
  world/playhead coordinates and reconciled saved/Event-only relation counts.
  The source harness uses a synthetic GUI observation provider and the installed
  offline model; it does not inspect or restart a user's active world/client.
- Four is the local HTTP/session admission ceiling, including setup traffic and
  all clients; one is the recommended tool concurrency. There is no claim that a
  separate bridge supports four simultaneous tool investigations.

Reproduce focused tests with the checkout Python and QT_QPA_PLATFORM=offscreen.
Protocol harness and full logs remain in ignored `artifacts/krt139/audit-*`;
the source probe is `audit_source_final.py`. The normal verification script requires
fresh fixture paths. Its isolated-discovery wrapper is verification-only and does
not relax production authentication, path or permission rules.

## Documentation and presentation review

The canonical guide is [Local AI access](../../../user/local-ai-access.md), with
reference additions for failures/recovery, concurrency, calendars, time and audit
semantics. Existing topic/heading anchors and Help entry points are retained.
Use the [documentation review](../../../developer/documentation-review.md) and
[reader observation](../../../developer/documentation-reader-testing.md) forms.

The Settings disclosure now names calendar/relationship reads and live time
observations. Authoring contracts 1/2/4/5/6/7/8/9 retain the same local Enable/Stop
routes, keyboard ownership and surrounding draft/selection/caret/playhead/undo
context. Shared neutral labels, wrapping and existing secondary/disclosure controls
remain; no local colors or new presentation variant was added. Source/policy,
offscreen theme and rendered Help results are recorded separately from human review.

Strict Sphinx (`-n -W --keep-going`) and offline Help generation passed. Validated
offline Help was rendered in Qt at 390 and 960 pixels and inspected for recovery,
calendar/time and relationship/attachment reference text. Narrow prose wraps;
the recovery table retains horizontal scrolling and wraps long reason codes.
This is an automated offscreen render inspection, not a reader-performance test.

Settings captures cover six themes and 360/640/960-pixel widths, including Off,
Active, semantic preparation, readiness and unavailability. Inspected examples:
[light narrow disclosure](sharing-light-narrow.png) and
[dark active disclosure](sharing-dark-active.png). The narrow panel scrolls to
its existing controls; the updated disclosure stays readable without overlapping
the surrounding Settings actions. Captures do not establish native-DPI or human
acceptance.

| Review field | Record |
| --- | --- |
| Reader and purpose | Users configuring local clients; maintainers auditing recovery and read completeness |
| Diátaxis purpose | Existing setup how-to retained; new API/error material is reference |
| Behavior inspected | Coordinator/session, protected discovery, typed bridge errors, audit readers, repository SQL and real protocol fixtures |
| Save/apply consequence | Read-only tools; local sharing controls still act immediately independently of Settings Apply/Cancel |
| Source revision | Base 0fd0580e plus this uncommitted five-issue implementation |
| Operational evidence | Focused/protocol tests above; build/policy results recorded at delivery |
| Human/live Help/native DPI and reader observations | Pending; no participant/reviewer approval inferred from automation |

## Remaining acceptance boundaries

No Windows package was rebuilt for this follow-up. Previous binary hashes certify
the earlier implementation only. Independent Codex, Claude Desktop and locally
executing ChatGPT Desktop conversations remain pending, particularly replay of the
owner's failure cases through the actual affected bridge. No production deployment,
commit, merge or push is part of this verification record.
