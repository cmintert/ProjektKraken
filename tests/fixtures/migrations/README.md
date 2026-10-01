# Historical schema fixtures

These SQL snapshots were extracted directly from committed
`src/services/db_service.py::_init_schema` string constants. Each SQL file names
its source commit. They contain schema only; tests add deterministic synthetic
records without private user data.

| Fixture | Source commit | Historical coverage |
| --- | --- | --- |
| early.sql | 74700706 | Core metadata, entities, events, relations |
| trajectories.sql | 264edbd6 | Maps, attachments, tags, legacy trajectory storage |
| history.sql | 8790447e | Persistent command history and edit sessions |
| pre_relations.sql | 3d913b55 | Map geometry and pre-normalization relations |
| pre_ledger.sql | f394e2d6 | Current pre-ledger tables, dated geometry |

Do not regenerate these from the current initializer. Add a new committed schema
snapshot when compatibility changes. Explicit partial-migration tests additionally
remove the supported color and timestamp columns before upgrading.
