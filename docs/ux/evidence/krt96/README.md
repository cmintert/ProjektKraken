# KRT-96 verification

This implementation adds three session-only Entity World Context modes and frozen
Entity prompt preparation. Source facts are read-only; Entity state resolution and
Graph relationship timing remain the shared authorities. The builder's reviewed
complexity falls from 19 to 13, removing its C901 allowance. The worker delegates
the existing Entity context read transaction to a feature service.

## Automated and rendered evidence

The deterministic fixture matrix lives in `test_entity_temporal_context.py`.
It covers both relation endpoints, exact reign transitions, event-bound sources
and rescheduling, custom calendars, uncertain appearances, unordered state
changes, open versus unknown boundaries, historical facts versus occurrences,
privacy and bounded projections. Prepared-generation tests cover off-GUI-thread
preparation, provider-message equality without another lookup, stale previews,
source-change guards and missing context. Coordinator tests cover immediate
invalidation, synchronized modes and world resets.

Run `python -m scripts.capture_entity_context_evidence` with
`QT_QPA_PLATFORM=offscreen`. Captures and their manifest are retained locally in
`docs/_build/krt96/rendered/`; these reproducible generated artifacts are not
committed. The script isolates settings and opens no world or model provider.
It captures all six themes at requested widths 360 and 800, all three modes,
source links, expanded uncertainty, focused selectors, and ready/stale preview
states. Actual sizes and device pixel ratios are recorded in the manifest.

Presentation uses shared input controls, neutral captions, typed Entity/Event
link roles and primary/secondary/quiet actions. Contracts 1–9/11 apply, including
KRT-94 local Tab ownership. Mode changes and same-object refresh preserve author
drafts, selection, caret, playhead and undo. No interaction exception is proposed.

## Verification recorded on 2026-10-25

- `ci_fast`: **2,621 passed, 3 skipped**, 359.19 seconds. A final compatibility
  correction retaining legacy public `_tags` classification was then checked
  against the complete temporal matrix (26 passing cases).
- Focused context/generation/temporal/dependency/architecture suite: 169 passing
  before the final tag and mode-toggle cases; the final focused rerun passes
  all **171 cases**, including immediate enabled/disabled synchronization.
- Repository-wide mypy: clean across 515 source files. Ruff, complexity, visual,
  Help inspection and test-inventory checks pass. The C901 allowance was removed
  only after measuring the builder's strict 19-to-13 reduction.
- Strict Sphinx, offline Help and generated-schema checks pass. The evidence
  page is indexed in UX navigation.
- Final action-label matrix: **3,072 records, zero failures**, across four scale
  factors, six themes, text scales and states on the Context, mode-selector,
  generation and prepared-preview surfaces. Reports are retained locally under
  `docs/_build/krt96/action-labels-final/`. Subsequent preparation changes make
  cross-thread delivery explicitly queued and serialize the prepared snapshot;
  they do not change the audited presentation.
- Six-theme, 360/800-width Context/preview captures are retained under
  `docs/_build/krt96/rendered/`. Inspection found and corrected narrow source-name
  clipping caused by document `adjustSize`; a regression now checks constrained
  reflow and retained same-Entity scroll/disclosure.
- Generated Context mode, Generate from preview and Refresh explanations were
  rendered in the production Help viewer at 360 px in dark/light themes. Captures
  and extracted text are under `docs/_build/krt96/help/`. Offline search resolves
  “Context mode” to `help-entity-world-context-mode`.

Initial integration verification exposed early generation-context access during
Entity construction. The final fallback is At playhead until the Context widget
exists. Entity/editor and guarded wiki-navigation regressions pass after the fix.
No world data, package, commit, push or release was changed by this verification.

## Owner acceptance — 2026-10-25

The owner concluded the guided review with **“All is accepted.”** KRT-96's
feature and guidance are owner-accepted under the reviewed conditions. This
supersedes the earlier pending owner-acceptance status. The implementation
was uncommitted at acceptance time. The owner subsequently authorized commit and
push separately; no release was requested.

The session used the running Northwatch Demo, with title-bar revision
`444af08c`. Evidence consists of participant reports, supplied cropped screenshots
and pasted preview/used-context text. It was guided and used a maintained sample;
it was not an unfamiliar-world, uncoached or timed benchmark. No participant
completion times, hesitation measurements or independent persistence checks were
collected.

| Guided check | Evidence and outcome |
| --- | --- |
| Ruler at 1 January, year 1 NS | Owner reported Queen Mara; the pasted authoritative preview and used-context block identify Mara at 1 January, 12:00. |
| Ruler after succession | Owner identified Captain Ilyra; screenshot shows Ilyra and the named succession source at 20 January. |
| Source navigation | Owner confirmed the succession link opens its Event while retaining the viewing date. |
| History versus active state | Screenshot in History to playhead labels Mara's rules relationship Not active; subsequent At playhead screenshot excludes it while retaining Ilyra's active relationship. |
| All history | Screenshot shows both rulers' dated relationships, with the playhead at 1 January. |
| Shared mode | Owner confirmed synchronization from World Context to Draft with AI and back. |
| Captured date | An initial preview at 10 January matched the owner's reported playhead. After moving to 1 January, the pasted preview changed to Mara and the corresponding saved facts. |
| Generate from preview and used context | Owner generated from Preview and reached the review dialog. Following the instruction to discard, the supplied World Context Used block matches the preview's authoritative block at 1 January. Generated prose was not scored for factual accuracy. |
| Narrow layout | Owner confirmed complete mode/Generate/Preview wording after being asked to narrow to approximately 360 px. Exact width, client geometry and scaling were not measured. |
| Keyboard | Owner confirmed visible Tab focus and successful arrow-key mode changes. |
| Contextual Help | Owner confirmed F1 from Context mode opens relevant AI/World Context guidance covering the three modes. |

Assistance and discovery limits: the initial route was incorrectly described as
Details; the owner corrected it to **Description → Draft with AI**. Finding
World Context used / Show required scrolling inside the AI panel, outside the
prompt textbox. The History & context disclosure is separate. An early cropped
history image lacked the requested status, but the later screenshot explicitly
showed History to playhead and the expected Not active label. These are guided
results, not evidence of unassisted discovery. No workflow fixes were inferred
solely from those intermediate images.

### Coverage limits retained with acceptance

Offscreen captures do not establish native Windows DPI or text-scale behavior.
The exhaustive native Windows display-scale/text-scale matrix was not performed
in this session. The owner accepts the feature with this evidence boundary;
automated results and bounded native reports are not an independently observed
complete UI-GATE-01 matrix or release sign-off.

For a future independent KRT-96 human task, use an unfamiliar populated disposable world. Ask the
participant to identify the ruler at two dates and trace the supporting Events,
without showing internal IDs or naming the controls to use. Record correctness,
elapsed time, hesitation, assistance, theme, client size and scaling. This bounded
populated-world task is distinct from the full empty-world authoring benchmark.
No human performance improvement is claimed.

## Documentation review

Reader: creators inspecting historical state or generating Entity descriptions.
The existing generation chapter supplies the how-to; the World Context model page
supplies explanation. Existing semantic Help targets are retained and new controls
have explicit targets. Source and build verification are recorded separately from
rendered inspection. The owner accepted the feature and relevant guidance after
the F1 check. Independent reader testing remains unperformed under the
documentation review and reader-testing protocols.


Documentation review record:

| Field | Record |
| --- | --- |
| Issue/purpose | KRT-96: inspect saved Entity state and understand exact generation input |
| Reader/knowledge | Creators familiar with Entities, the Timeline and optional generation |
| Diátaxis | Generation chapter: how-to; World Context model: explanation |
| Source identity | Reviewed worktree based on `444af08c6d37931a11021838557c1ed914729c09` |
| Labels/behavior checked | Context selector, accepted viewing date, named source links, More, frozen preview and stale Refresh, guarded response application |
| Persistence | Read-only context; generation still requires explicit reviewed Replace/Append |
| Help identities | Existing IDs/anchors retained; added Context mode and prepared text/Generate/Refresh/Close bindings under `writing.ai` |
| Rendered corrections | Explicit evidence fonts; constrained Context document width; retained scroll/disclosure |
| Human reviewer/approval | Owner accepted the feature and relevant guidance on 2026-10-25 after the bounded guided review |
| Native Windows scaling/live Help review | Guided narrow-layout, keyboard and F1 checks accepted; full scale/text-scale matrix not performed |
| Reader-round owner/cohort/date/outcomes | No independent reader cohort or timed study; guided outcomes recorded above |
