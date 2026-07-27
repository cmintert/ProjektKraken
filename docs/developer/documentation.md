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

## Build locally

```text
python docs/generate_schema_docs.py --check
sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

Every Markdown file under `docs/` must be reachable from a toctree. Do not put
research notes or implementation diaries in the Sphinx source directory.

