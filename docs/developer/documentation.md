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

```text
python docs/generate_schema_docs.py --check
sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

Every Markdown file under `docs/` must be reachable from a toctree. UX
contracts and verification evidence are indexed in [UX navigation](../ux/index.md).
Do not put unindexed research notes in the Sphinx source directory.

