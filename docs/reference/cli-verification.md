# CLI verification: KRT-104

The CLI contract suite is `tests/cli/test_cli_contract.py`. It runs as the
named **CLI contract** step in local push and release preflight. Every group is
invoked through both Python module entry points for help; executable examples
in the root README, CLI README, and [canonical reference](cli.md) have their
module and flags checked against real parsers. Mutation tests use disposable
world folders and local backup directories.

| Group | Documented invocation | Verified behavior | Limit |
| --- | --- | --- | --- |
| `entity` | `entity <action> -d <db>` | Empty JSON, create/show/update/delete roundtrip | Desktop session must be closed |
| `event` | `event <action> -d <db>` | Empty JSON, create/update/delete roundtrip | Numeric lore date only |
| `relation` | `relation <action> -d <db>` | Add/list/update/delete roundtrip | No temporal expression authoring |
| `map` | `map <action> -d <db>` | Create/list/update/delete and marker add/list/update/delete; invalid coordinates rejected | No dated geometry/raster editor |
| `attachment` | `attachment <action> -d <db>` | Add/list/caption/reorder/remove, partial failure, singular readback, legacy preview/backup/repair | Legacy assets retain their original referenced paths |
| `calendar` | `calendar <action> -d <db>` | Create/list/show/set-active/delete roundtrip | Custom calendar definition only |
| `timeline` | `timeline <action> -d <db>` | Group/clear/tag-color roundtrip | No advanced chronology authoring |
| `wiki` | `wiki scan -d <db>` | Scan on a real world | Stored source field only |
| `index` | `index <action> -d <db>` | Four handlers from both parsers, with provider boundary stubbed | Real provider availability is environment dependent |
| `longform` | `longform export -d <db>` | Markdown export on a real world | Structure mutations covered by focused existing tests |
| `obsidian` | `obsidian export -d <db>` | Vault export on a real world | Export only |
| `backup` | `backup <action> -d <db>` | Create/list/restore to new target | Restore requires all target clients closed |
| `graph` | `graph export -d <db>` | JSON export on a real world | No time filter |
| `info` | `info show -d <db>` | JSON statistics and failed-gathering exit behavior | Missing asset metadata fails instead of reporting partial size |
| JSON importer | `python -m src.app.main import --file <json> -d <db>` | Import only into selected world; active-world resolver tested | Qt source entry; no `--mode` option |

The legacy attachment test creates a disposable plural-typed record and its
old asset path, confirms preview does not mutate it, rejects repair when the
asset is missing, and verifies that `--apply --force` creates a recovery backup
before normalizing the record. No release, demo, or user world was modified.

No outstanding defect was reproduced in the covered paths. Provider-backed
semantic search and native desktop behavior are separate acceptance checks.
