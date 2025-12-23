-- Migration: 0004_normalize_tags.sql
-- Purpose: Normalize tags from JSON attributes to dedicated tables
--
-- SAFETY NOTES:
-- This migration is IDEMPOTENT and safe to run multiple times.
-- If the tables already exist, the CREATE TABLE IF NOT EXISTS statements
-- will succeed without modification.
--
-- BEFORE RUNNING:
-- 1. BACKUP your database file (.kraken)
-- 2. Test on a copy first
-- 3. Ensure you have read the rollback plan below
--
-- WHAT THIS MIGRATION DOES:
-- 1. Creates `tags` table to store unique tag names
-- 2. Creates `event_tags` join table for event-tag associations
-- 3. Creates `entity_tags` join table for entity-tag associations
-- 4. Extracts tags from events.attributes JSON and populates normalized tables
-- 5. Extracts tags from entities.attributes JSON and populates normalized tables
-- 6. Does NOT remove tags from attributes (for safety and backward compatibility)
--
-- ROLLBACK PLAN:
-- To rollback this migration:
-- 1. Restore from backup (safest option), OR
-- 2. Run the rollback script below:
--
-- ROLLBACK SCRIPT:
-- -- Drop the normalized tables
-- -- DROP TABLE IF EXISTS event_tags;
-- -- DROP TABLE IF EXISTS entity_tags;
-- -- DROP TABLE IF EXISTS tags;
-- 
-- Note: Tags remain in attributes JSON, so application will continue to work
-- with denormalized data after rollback.

-- ============================================================================
-- Step 1: Create normalized tables
-- ============================================================================

-- Tags table: stores unique tag names
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
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

-- ============================================================================
-- Step 2: Migration data from attributes JSON to normalized tables
-- ============================================================================
-- Note: This part will be executed by the Python migration script
-- (migrate_tags.py) because SQLite's JSON functions are limited for
-- complex array processing. The script will:
-- 1. Extract all unique tags from events.attributes._tags
-- 2. Extract all unique tags from entities.attributes._tags
-- 3. Insert unique tags into the tags table
-- 4. Create associations in event_tags and entity_tags tables
-- 5. Verify data integrity
--
-- The SQL tables above are ready to receive the migrated data.
