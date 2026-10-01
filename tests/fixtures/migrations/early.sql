-- Source: 74700706 src/services/db_service.py::_init_schema
CREATE TABLE IF NOT EXISTS system_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    lore_date REAL NOT NULL,
    lore_duration REAL DEFAULT 0.0,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);

-- Generic Relation Table
CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    attributes JSON DEFAULT '{}',
    created_at REAL
);
-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_date ON events(lore_date);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
