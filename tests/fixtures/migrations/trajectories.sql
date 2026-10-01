-- Source: 264edbd6 src/services/db_service.py::_init_schema
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

-- Calendar Configuration Table
CREATE TABLE IF NOT EXISTS calendar_config (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    created_at REAL,
    modified_at REAL
);

-- Map Table
CREATE TABLE IF NOT EXISTS maps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    image_path TEXT NOT NULL,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);

-- Marker Table
CREATE TABLE IF NOT EXISTS markers (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    label TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL,
    UNIQUE(map_id, object_id, object_type),
    FOREIGN KEY(map_id) REFERENCES maps(id) ON DELETE CASCADE
);

-- Indexes for markers
CREATE INDEX IF NOT EXISTS idx_markers_map ON markers(map_id);
CREATE INDEX IF NOT EXISTS idx_markers_object
    ON markers(object_id, object_type);

-- Moving Features Table (Temporal Trajectories)
CREATE TABLE IF NOT EXISTS moving_features (
    id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    trajectory JSON NOT NULL, -- List of [t, x, y]
    properties JSON DEFAULT '{}', -- Changing properties over time
    created_at REAL,
    FOREIGN KEY(marker_id) REFERENCES markers(id) ON DELETE CASCADE
);

-- Indexes for temporal queries
CREATE INDEX IF NOT EXISTS idx_moving_features_marker
    ON moving_features(marker_id);
CREATE INDEX IF NOT EXISTS idx_moving_features_time
    ON moving_features(t_start, t_end);

-- Image Attachments Table
CREATE TABLE IF NOT EXISTS image_attachments (
    id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    image_rel_path TEXT NOT NULL,
    thumb_rel_path TEXT,
    caption TEXT,
    order_index INTEGER DEFAULT 0,
    created_at REAL,
    -- Stored as "widthxheight" or JSON [w, h]
    resolution TEXT,
    source TEXT
);

-- Indexes for image attachments
CREATE INDEX IF NOT EXISTS idx_attachments_owner
    ON image_attachments(owner_type, owner_id);

-- Normalized Tags Tables
-- Tags table: stores unique tag names
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    created_at REAL NOT NULL
);

-- Create index on tag name for fast lookups
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);

-- Event-Tag association table
CREATE TABLE IF NOT EXISTS event_tags (
    event_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);
CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag_id);

-- Entity-Tag association table
CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (entity_id, tag_id),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_entity_tags_entity ON entity_tags(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_tags_tag ON entity_tags(tag_id);

-- Embeddings Table (for semantic search)
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    vector_dim INTEGER NOT NULL,
    text_snippet TEXT,
    text_hash TEXT,
    metadata JSON DEFAULT '{}',
    created_at REAL NOT NULL
);

-- Upsert-friendly unique constraint to avoid duplicate rows per object/model
CREATE UNIQUE INDEX IF NOT EXISTS uq_embeddings_obj_model
    ON embeddings(object_type, object_id, model);

-- Useful indexes for query filtering and status
CREATE INDEX IF NOT EXISTS idx_embeddings_model_dim
    ON embeddings(model, vector_dim);

CREATE INDEX IF NOT EXISTS idx_embeddings_object
    ON embeddings(object_type, object_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_created_at
    ON embeddings(created_at);
