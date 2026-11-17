# A0 hierarchy integrity and persistent history

## Change and source review

| Field | Record |
| --- | --- |
| Issue and purpose | KRT-168, A0 of KRT-167; hierarchy integrity and restart-safe undo/redo |
| Reader | Existing creators upgrading worlds; contributors extending commands |
| Diátaxis purpose | Portability/recovery: explanation; commands/history and migrations: reference |
| Canonical pages | Existing portability, command-history, migration and architecture pages; no new Help topic |
| Source revision | 2be03afa plus the uncommitted KRT-168 worktree, 2026-11-16 |
| Sources inspected | Worker/coordinator history flow, transaction wrapper, asset stores, migration runner/recovery bundle and new integration regressions |
| Preserved destinations | Existing headings, topic IDs, excerpts and inspection declarations retained |
| User-visible change | Both stacks restore on reopening; upgrade starts fresh legacy history with a verified recovery bundle |
| Interaction contracts | 4/5/6/8/9: explicit recovery wording, preserved context and failure/undo semantics; native migration dialog retains its existing controls and theme |

## Verification boundaries

Integration tests exercise real worker/coordinator dispatch, SQL persistence,
reopen/undo/reopen/redo, divergent branches, history-write failures, asset rollback,
safe session boundaries, pruning and world identity. Upgrade fixtures verify
the previous database and artifacts in a recovery bundle, rollback after a reset
failure and non-mutating read-only opening. Dependency tests protect the pure
hierarchy and service boundaries. The hierarchy authoring UI remains A1 work.

Command-level tests and offscreen component tests are automated evidence. They
do not establish native rapid-scrubbing crash resolution, packaged acceptance,
unassisted usability or reader performance. KRT-166 remains separate.

## Documentation review and reader observation

Greptile review 42248930 inspected isolated snapshot
`1b3ffdc9e8c686d0f613493a71e51e65f33af06d` against `2be03afa`.
Its three findings were fixed locally: null map attributes, file recovery after
rollback-hook errors, and unbounded archived-history decoding. Added regressions
cover independent file replacement and indexed active-history queries. The
focused hierarchy/history/icon/migration group passed 113 tests after these fixes.
The fixes have not been re-reviewed remotely by Greptile.

Final implementation verification on 2026-11-16: 250 consolidated affected tests
passed offscreen; 45 icon/history/migration component tests passed with native
Windows Qt. Ruff, repository mypy (695 files), complexity/visual policy, generated
schema, Help inspection/build, strict Sphinx and 27 CLI contract tests passed.
Four legacy command Help fingerprints were individually reviewed. The test
inventory change only renames two existing reviewed migration cases to match
the agreed history reset; no suite membership was removed or regenerated.

The broad regression is **not** a clean single-process pass. After fixing the
icon compensation regression, a resumed process ended in a native access
violation during the menu-caret test. KRT-169 records that failure without a
causal claim. The seven menu cases and the adjacent 27-case MCP/menu group pass
in isolation. A subsequent segment exposed disconnected-history read behavior;
that was corrected and verified by the consolidated group. The final tail from
persistence-boundary tests passed 1,034 cases. These segmented results supplement
the preceding passed tests; they do not turn the interrupted preflight into a
passing push/release gate. No hook or policy was bypassed. Logs remain under
`artifacts/krt168`.

The recovery explanation describes opening the same saved world, the upgrade
notice and its recovery location, and the resulting stack boundary. No new
manual operation, inspector, shortcut or Help destination is introduced.

Build and inspection results are recorded in the KRT-168 Linear issue after
verification. The actual offline Help reader generated 12 offscreen captures at
360/640 pixels across six palettes, with the application font loaded. Dark/narrow
and light/normal captures were visually inspected for readable reset/recovery
wording, complete controls and scrolling. Local artifacts are under
`artifacts/krt168/help`; they are not tracked publication assets. Native Qt
history/migration component checks passed separately; they are not full-app Help
acceptance. Human prose/live Help approval remains **Pending**. A fresh reader's interpretation of
the history reset and recovery distinction is **Not tested**; no task-time or
reader-performance improvement is claimed. This is the observation record under
the existing documentation reader-testing protocol, not a completed reader round.
