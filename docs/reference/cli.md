# Command-Line Interface

The source CLI provides offline world maintenance, import and export, and
diagnostics. Run it from the repository root with Python 3.13 or newer and the
installed project dependencies, including PySide6. Close ProjektKraken before
mutating a world: direct CLI writes do not synchronize the open desktop session.
The Windows package is a desktop application; these Python module commands are
not a separate packaged CLI executable.

## Entry points and targets

Use `python -m src.cli.cli <group> <action> [options]`. The corresponding
`python -m src.cli.<group> <action> [options]` form also works. Put
`--database/-d` **after the action**; it names an existing `.kraken` file in a
world folder. Content `create` actions do not create a new world or database.
Use the desktop World Manager to create a world first. Back up a world and keep
the desktop app closed before destructive operations.

Exit status is `0` on completed success, `2` for argparse usage errors, and
`1` for operational failure or a partial attachment import. `--json` output
is written to stdout; diagnostics are written to stderr. JSON flags exist only
on the actions listed below. An empty entity or event JSON list is `[]`.

| Group | Existing actions | JSON actions |
| --- | --- | --- |
| `entity` | `create`, `list`, `show`, `update`, `delete` | `create`, `list`, `show` |
| `event` | `create`, `list`, `show`, `update`, `delete` | `create`, `list`, `show` |
| `relation` | `add`, `list`, `update`, `delete` | `list` |
| `map` | `create`, `list`, `update`, `delete`, `marker-add`, `marker-list`, `marker-update`, `marker-delete` | `list`, `marker-list` |
| `attachment` | `add`, `list`, `caption`, `reorder`, `remove`, `repair-legacy` | `list` |
| `calendar` | `create`, `list`, `show`, `set-active`, `delete` | `list`, `show` |
| `timeline` | `group`, `clear`, `tag-color` | none |
| `wiki` | `scan` | none |
| `index` | `rebuild`, `index-object`, `query`, `delete-object` | `query` |
| `longform` | `export`, `move`, `remove`, `add`, `promote`, `demote`, `reindex` | none |
| `obsidian` | `export` | none |
| `backup` | `create`, `list`, `restore` | none |
| `graph` | `export` | none |
| `info` | `show` | `show` |

Use `<group> <action> --help` for the complete flag list. Entity, event,
relation, map, marker, calendar, and attachment deletion and backup restore
ask for confirmation unless `--force` is provided. `--force` skips the
prompt; use it only with a checked target. Longform `remove` changes document
membership and does not prompt.

## Common examples

These commands assume `worlds/My World/My World.kraken` already exists.
Replace IDs with values returned by a create command or JSON list.

```text
python -m src.cli.cli entity create --database "worlds/My World/My World.kraken" --name Mara --type character --json
python -m src.cli.cli event create --database "worlds/My World/My World.kraken" --name Arrival --date 100.5 --json
python -m src.cli.cli entity list --database "worlds/My World/My World.kraken" --json
python -m src.cli.cli info show --database "worlds/My World/My World.kraken" --json
python -m src.cli.cli map marker-add --database "worlds/My World/My World.kraken" --map-id <map-id> --object-type entity --object-id <entity-id> --x 0.25 --y 0.75
python -m src.cli.cli attachment add --database "worlds/My World/My World.kraken" --type entity --id <entity-id> portrait.png
python -m src.cli.cli attachment list --database "worlds/My World/My World.kraken" --type entity --id <entity-id> --json
python -m src.cli.cli index query --database "worlds/My World/My World.kraken" --text "find Mara" --json
python -m src.cli.cli graph export --database "worlds/My World/My World.kraken" --out-file graph.json
python -m src.cli.cli longform export --database "worlds/My World/My World.kraken" --output manuscript.md
python -m src.cli.cli obsidian export --database "worlds/My World/My World.kraken" --out-dir vault
```

Entity and event `create --json` return one object with `id`, `name`, and
`type` or `lore_date`, respectively. Map marker `x` and `y` are normalized
coordinates in the inclusive range `0.0–1.0`. Attachment owner types are
`entity` or `event`; the old plural spellings are accepted at the CLI boundary
and normalized before storage. An attachment batch can keep successful images
while reporting failed source paths and returning status `1`.

Older CLI versions could store plural owner types and assets under an extra
pluralized folder. `attachment repair-legacy --database <world.kraken>` previews
affected records and checks referenced files without changing them. Add
`--apply` to back up the database and normalize those record types; it asks for
confirmation unless `--force` is supplied. The repair keeps asset paths and
files in place, so the database backup reverses its only change. It aborts if
any referenced asset is missing or unsafe. Inspect the preview and recovery
backup path before applying it to a copied world.

The four index actions accept `--database` after the action. Rebuild and
index-object require an embedding provider (`sentence-transformers` by default,
or `lmstudio`); query also uses a provider, while delete-object does not.
Install or configure the chosen provider before running those actions.

## Import and backup

The JSON importer is separate from the unified CLI:

```text
python -m src.app.main import --file data.json --database "worlds/My World/My World.kraken"
```

`--database` must identify an existing, discoverable world. If omitted, import
uses the desktop application's registered active world path, falling back to
its saved active world name. It announces the resolved world and path before
writing and fails when selection or approval is invalid. This source entry
loads Qt. The importer has no `--mode` flag; its current default import mode
applies. Import a disposable copy first when checking an unfamiliar file.

`backup restore --file <backup> --database <target> [--force]` permits a new
target path. The backup must be inside the configured backup directory and
passes BackupService validation. Close all clients of the target database
before restoring. A restore can overwrite the target; verify both paths first.

## Current limits

The CLI does not author historical expressions, dated map geometry, rasters,
trajectories, AI workflows, or other GUI-only interactions. Graph export is not
time filtered. It does not provide a synchronized live-control interface for an
open desktop session.
