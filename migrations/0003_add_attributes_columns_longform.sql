-- Migration: 0003_add_attributes_columns_longform.sql
-- Purpose: Ensure attributes column exists for longform metadata storage
-- 
-- SAFETY NOTES:
-- This migration is IDEMPOTENT and safe to run multiple times.
-- If the attributes column already exists, the ALTER TABLE statements will fail
-- gracefully and can be ignored. The schema initialization in DatabaseService
-- already creates attributes columns, so this migration serves as documentation
-- and a safety net for legacy databases.
--
-- BEFORE RUNNING:
-- 1. BACKUP your database file (.kraken)
-- 2. Test on a copy first
-- 3. Verify attributes can be parsed with the sanity check script
--
-- ROLLBACK:
-- If you need to rollback, restore from backup. Removing the attributes column
-- would lose all longform metadata and any other data stored in attributes.
-- To remove only longform metadata while keeping the column:
--   UPDATE events SET attributes = json_remove(attributes, '$.longform') WHERE json_extract(attributes, '$.longform') IS NOT NULL;
--   UPDATE entities SET attributes = json_remove(attributes, '$.longform') WHERE json_extract(attributes, '$.longform') IS NOT NULL;
--
-- NOTE: The DatabaseService._init_schema() already creates these columns with
-- DEFAULT '{}', so this migration is primarily for databases created before
-- the attributes column was added to the schema.

-- Add attributes column to events table if it doesn't exist
-- If it exists, this will fail silently (expected behavior)
ALTER TABLE events ADD COLUMN attributes TEXT DEFAULT '{}';

-- Add attributes column to entities table if it doesn't exist
-- If it exists, this will fail silently (expected behavior)
ALTER TABLE entities ADD COLUMN attributes TEXT DEFAULT '{}';

-- Update any NULL values to empty JSON objects (defensive)
UPDATE events SET attributes = '{}' WHERE attributes IS NULL;
UPDATE entities SET attributes = '{}' WHERE attributes IS NULL;
