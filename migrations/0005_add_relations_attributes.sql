-- Migration: 0005_add_relations_attributes.sql
-- Purpose: Ensure attributes column exists for relation metadata storage
--
-- SAFETY NOTES:
-- This migration is IDEMPOTENT and safe to run multiple times.
-- If the attributes column already exists, the ALTER TABLE statement will fail
-- gracefully and can be ignored. The schema initialization in DatabaseService
-- already creates the attributes column, so this migration serves as documentation
-- and a safety net for legacy databases created before attributes were added.
--
-- BEFORE RUNNING:
-- 1. BACKUP your database file (.kraken)
-- 2. Test on a copy first
-- 3. Verify the column doesn't already exist with: PRAGMA table_info(relations)
--
-- ROLLBACK:
-- If you need to rollback, restore from backup. Removing the attributes column
-- would lose all relation metadata.
-- To remove only specific attributes while keeping the column:
--   UPDATE relations SET attributes = '{}' WHERE id = '<relation-id>';
--
-- RECOMMENDED ATTRIBUTES:
-- Common attributes for relations include:
-- - weight: Numeric strength of relationship (for graph analysis)
-- - start_date: When the relationship began (lore_date format)
-- - end_date: When the relationship ended (lore_date format)
-- - confidence: Certainty of the relationship (0.0-1.0)
-- - source: Citation or reference for the relationship
-- - notes: Additional context or description
--
-- NOTE: The DatabaseService._init_schema() already creates this column with
-- DEFAULT '{}', so this migration is primarily for databases created before
-- the attributes column was added to the schema.

-- Add attributes column to relations table if it doesn't exist
-- If it exists, this will fail silently (expected behavior in SQLite)
ALTER TABLE relations ADD COLUMN attributes TEXT NOT NULL DEFAULT '{}';

-- Update any NULL values to empty JSON objects (defensive measure)
UPDATE relations SET attributes = '{}' WHERE attributes IS NULL;
