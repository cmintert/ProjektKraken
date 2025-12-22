# Database Architecture and Best Practices

## Overview

ProjektKraken uses SQLite as its database engine with a hybrid schema approach that combines strict SQL columns for searchable/sortable fields with flexible JSON attributes for custom data.

## Architecture

### Database Service (`src/services/db_service.py`)

The `DatabaseService` class is the single point of interaction with the SQLite database. It implements:

- **Connection Management**: Persistent connection with lazy initialization
- **Transaction Safety**: Context manager for ACID compliance
- **Hybrid Schema**: SQL columns + JSON attributes
- **Parameterized Queries**: SQL injection prevention
- **Automatic Rollback**: Error handling with transaction rollback

### Schema Design

#### Core Tables

1. **events** - Timeline events (points or spans in time)
   - Strict columns: `id`, `type`, `name`, `lore_date`, `lore_duration`, `description`
   - Flexible: `attributes` (JSON)
   - Metadata: `created_at`, `modified_at`

2. **entities** - Timeless objects (characters, locations, artifacts)
   - Strict columns: `id`, `type`, `name`, `description`
   - Flexible: `attributes` (JSON)
   - Metadata: `created_at`, `modified_at`

3. **relations** - Directed relationships between objects
   - Columns: `id`, `source_id`, `target_id`, `rel_type`
   - Flexible: `attributes` (JSON)
   - Metadata: `created_at`

4. **system_meta** - Application metadata
   - Key-value store for settings

#### Indexes

Performance indexes are automatically created:
- `idx_events_date` - Chronological event queries
- `idx_relations_source` - Outgoing relation lookups
- `idx_relations_target` - Incoming relation lookups

### Connection Management

#### Connection Lifecycle

```python
# Automatic connection on first use
service = DatabaseService("path/to/world.kraken")
service.connect()  # Explicit connection

# Lazy connection on first query
event = service.get_event(event_id)  # Auto-connects if needed

# Cleanup
service.close()
```

#### Thread Safety

**Important**: SQLite connections are NOT thread-safe. The codebase uses a Worker thread pattern:

- Main thread: UI operations only
- Worker thread: All database operations via `DatabaseWorker`
- Communication: Qt signals/slots with queued connections

**Never** access the database service directly from the UI thread in production code.

### Transaction Management

All write operations use the transaction context manager:

```python
with db_service.transaction() as conn:
    conn.execute(sql, params)
    # Automatic commit on success
    # Automatic rollback on exception
```

#### Transaction Guarantees

- **Atomicity**: All operations succeed or all fail
- **Consistency**: Database constraints are enforced
- **Isolation**: Default SQLite isolation level
- **Durability**: Changes persisted to disk

#### Error Handling

```python
try:
    with db_service.transaction() as conn:
        # ... database operations ...
except sqlite3.Error as e:
    # Transaction automatically rolled back
    logger.error(f"Database error: {e}")
    # Handle error appropriately
```

### Performance Optimization

#### Bulk Operations

For inserting multiple records, use bulk methods:

```python
# Inefficient: Multiple transactions
for event in events:
    db_service.insert_event(event)

# Efficient: Single transaction with executemany
db_service.insert_events_bulk(events)
```

#### Query Optimization

1. **Use Indexes**: Queries on `lore_date`, `source_id`, `target_id` are indexed
2. **Limit Results**: Use SQL `LIMIT` for pagination when needed
3. **Avoid N+1 Queries**: Fetch related data in single query when possible

#### Database Locking

SQLite uses file-level locking:

- **Readers**: Multiple concurrent readers allowed
- **Writers**: Exclusive lock required
- **Busy Timeout**: Not explicitly set (uses SQLite defaults)

For high-concurrency scenarios, consider:
- Using WAL (Write-Ahead Logging) mode
- Implementing retry logic for locked database
- Keeping transactions short

## Security Best Practices

### SQL Injection Prevention

**All queries use parameterized statements:**

✅ **Correct** - Parameterized query:
```python
cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
```

❌ **Wrong** - String interpolation (SQL injection risk):
```python
cursor.execute(f"SELECT * FROM events WHERE id = '{event_id}'")
cursor.execute("SELECT * FROM events WHERE id = {}".format(event_id))
```

### Data Validation

1. **Input Validation**: Validate data before database operations
2. **Type Safety**: Use type hints and dataclasses
3. **Constraint Enforcement**: Database constraints (PRIMARY KEY, NOT NULL, etc.)

### Sensitive Data

1. **No Passwords in Database**: Not applicable for this app
2. **No API Keys in Code**: Use environment variables
3. **File Permissions**: Database files should have appropriate OS permissions

### Backup and Recovery

1. **File-based Backup**: Copy `.kraken` file when app is closed
2. **Export**: Implement JSON export for data portability
3. **Version Control**: Never commit `.kraken` files to git (see `.gitignore`)

## Testing Best Practices

### In-Memory Testing

Always use `:memory:` for tests:

```python
@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()
```

### Test Coverage

Ensure tests cover:
- ✅ CRUD operations (Create, Read, Update, Delete)
- ✅ Transaction rollback on errors
- ✅ Edge cases (empty data, nonexistent IDs)
- ✅ Bulk operations
- ✅ Concurrent access (if applicable)
- ✅ Data integrity (foreign keys, constraints)

### Example Test

```python
def test_transaction_rollback(db_service):
    """Test that failed transactions rollback changes."""
    event = Event(name="Test", lore_date=1.0)
    db_service.insert_event(event)
    
    try:
        with db_service.transaction() as conn:
            conn.execute("INSERT INTO events ...")  # Valid
            conn.execute("INVALID SQL")  # Causes rollback
    except sqlite3.Error:
        pass
    
    # First insert should still exist
    assert db_service.get_event(event.id) is not None
```

## Common Patterns

### CRUD Operations

```python
# Create
event = Event(name="Battle", lore_date=1066.0)
db_service.insert_event(event)

# Read
event = db_service.get_event(event_id)
events = db_service.get_all_events()

# Update (via upsert)
event.name = "Updated Name"
db_service.insert_event(event)

# Delete
db_service.delete_event(event_id)
```

### Relations

```python
# Create relation
rel_id = db_service.insert_relation(
    source_id=event1.id,
    target_id=event2.id,
    rel_type="caused",
    attributes={"certainty": 0.9}
)

# Query relations
outgoing = db_service.get_relations(source_id)
incoming = db_service.get_incoming_relations(target_id)

# Update relation
db_service.update_relation(
    rel_id=rel_id,
    target_id=new_target.id,
    rel_type="prevented",
    attributes={}
)

# Delete relation
db_service.delete_relation(rel_id)
```

## Migration Strategy

For schema changes:

1. **Version System Metadata**: Track schema version in `system_meta` table
2. **Migration Scripts**: Create upgrade functions
3. **Backup First**: Always backup before migration
4. **Test Migration**: Test on copy of production data

Example:
```python
def migrate_v1_to_v2(db_service):
    """Migrate database from v1 to v2."""
    with db_service.transaction() as conn:
        # Add new column
        conn.execute("ALTER TABLE events ADD COLUMN new_field TEXT")
        # Update version
        conn.execute(
            "INSERT OR REPLACE INTO system_meta VALUES (?, ?)",
            ("schema_version", "2")
        )
```

## Troubleshooting

### Database Locked

**Symptom**: `sqlite3.OperationalError: database is locked`

**Solutions**:
1. Ensure transactions are short
2. Close connections properly
3. Use WAL mode for better concurrency
4. Implement retry logic with exponential backoff

### Disk Full

**Symptom**: `sqlite3.OperationalError: disk I/O error`

**Solutions**:
1. Check available disk space
2. Implement size monitoring
3. Regular cleanup of old data

### Corrupted Database

**Symptom**: `sqlite3.DatabaseError: database disk image is malformed`

**Solutions**:
1. Restore from backup
2. Use SQLite's `PRAGMA integrity_check`
3. Export data if partially readable

## References

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [SQLite Best Practices](https://www.sqlite.org/bestpractice.html)
- [Python sqlite3 Module](https://docs.python.org/3/library/sqlite3.html)
