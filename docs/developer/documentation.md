# Documentation Maintenance

## Canonical locations

- User behaviour: `docs/user/`
- Developer contracts: `docs/developer/`
- Generated and command reference: `docs/reference/`
- Historical material: `archive/documentation/`
- Proposals and research: `planning/`

Only current, implemented, supported behaviour belongs under `docs/`.

## Update rules

Update documentation when a change affects:

- menus, dialogs, labels, shortcuts, or workflows;
- persisted world data or portability;
- commands, undo, threading, or coordinator contracts;
- setup, testing, packaging, or release steps;
- CLI commands or configuration.

Verify UI wording against code rather than copying an older guide. User pages
should describe outcomes and steps without exposing implementation classes.
Developer pages may name classes when they explain a current contract.

## Authoring Help checklist for feature changes

- Identify the code behavior and visible routes affected by the change, including
  keyboard ownership and preserved authoring context (Contracts 1–9 and 11).
- Update the existing canonical task under `docs/user/`; keep detailed procedures
  there rather than introducing widget prose or another manual copy. State which
  independent attributes, relations, mentions, dates or geometry remain unchanged.
- Check the topic ID, explicit task target, optional control-excerpt target and
  related-topic links in `docs/help-topics.json`. Preserve stable destinations;
  adding inspection meanings requires an explicit inventory decision.
- Build Help with `python -m scripts.build_help`, run strict Sphinx, and inspect
  the generated task, excerpt, search result and links in the companion.
- Record human reviewer, source revision, topics/scenarios, corrections and
  approval before publishing new reference prose. Automated structure checks do
  not establish semantic accuracy or independent human workflow acceptance.

## Build locally

### Maintaining interface inspection

The inspection controller owns both explanation chords: Shift+F1 hit-tests the
pointer without falling back to keyboard focus; Ctrl+Shift+F1 explains focus or
the active menu action. Claim shortcut overrides in that dispatcher, without
additional QAction/QShortcut bindings. Retain native What's This pointer mode,
popup rendering and task links. Test complete chords through window-level input
so releases, modal blocking and Escape cannot leak into authoring operations.

`docs/help-inspection.json` is the finite inspection inventory. Each declaration
names its source symbol, semantic control identity, canonical excerpt target and
task topic. Feature constructors attach only `meaning|topic|excerpt` metadata with
`declare_inspection`; widgets never contain the explanation prose. Shared menu
descriptors use operation IDs, and default actions/overflow proxies retain their
original control meaning. Form labels use field associations, never text matching.

When behavior, a handler, field, action or visible wording changes:

1. Read the affected control and its connected operation. Update its short
   canonical paragraph and task if the purpose or consequences changed.
2. Check equivalent instances, labels, menu/overflow routes and intentional
   exemptions. Add a declaration or a reasoned factory exemption for new controls.
3. Run `python -m scripts.check_help_inspection`. A changed reviewed symbol must
   receive a Help-impact review. Record the reviewed source fingerprint and a
   specific explanation of corrections, or why the existing prose remains true.
   Do not refresh fingerprints in bulk merely to pass the check.
4. Build Help and inspect the generated paragraph, direct search destination and
   task link. Record human prose approval before publishing new reference text.

Fingerprints use normalized Python syntax, ignoring comments and layout. They
are change prompts, not proof that prose matches behavior. The native-factory
scan covers the enumerated Qt input constructors; custom widgets, JavaScript
controls and new domain dependencies still need explicit feature review. The
checker is read-only and is included in preflight and the static CI gate.

### Commands

```text
python docs/generate_schema_docs.py --check
sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

Every Markdown file under `docs/` must be reachable from a toctree. UX
contracts and verification evidence are indexed in [UX navigation](../ux/index.md).
Do not put unindexed research notes in the Sphinx source directory.

