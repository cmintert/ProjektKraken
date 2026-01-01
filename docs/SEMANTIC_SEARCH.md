---
**Project:** ProjektKraken  
**Document:** Semantic Search Implementation Guide  
**Last Updated:** 2026-01-01  
**Commit:** `199b38b`  
---

# Semantic Search in ProjektKraken

## Overview

ProjektKraken includes a powerful local-first semantic search system that enables natural language queries across your world's entities and events. The system uses embeddings to understand the meaning of your content, allowing you to find related items even when they don't share exact keywords.

## Features

- **Local-First**: All embeddings are generated and stored locally, with no external services required
- **LM Studio Integration**: Primary support for LM Studio as the embedding provider
- **Flexible Provider Support**: Optional fallback to sentence-transformers
- **Deterministic Indexing**: Reproducible embeddings with text hashing to detect changes
- **Comprehensive Attribute Coverage**: Indexes all custom attributes, not just predefined fields
- **Efficient Storage**: Unit-normalized vectors with SQLite BLOB storage
- **Model Management**: Support for multiple models with proper filtering
- **CLI and Worker Integration**: Batch indexing via CLI or async indexing via background worker

## Architecture

### Data Model

The semantic search system adds a single `embeddings` table to the database:

```sql
CREATE TABLE embeddings (
  id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,        -- 'entity' | 'event'
  object_id TEXT NOT NULL,          -- FK to entities/events
  model TEXT NOT NULL,              -- e.g., 'lmstudio:bge-small-en'
  vector BLOB NOT NULL,             -- Normalized float32 vector
  vector_dim INTEGER NOT NULL,      -- Embedding dimension (384, 768, etc.)
  text_snippet TEXT,                -- Full text that was embedded
  text_hash TEXT,                   -- SHA-256 for change detection
  metadata JSON DEFAULT '{}',       -- name, type, tags, etc.
  created_at REAL NOT NULL
);

CREATE UNIQUE INDEX uq_embeddings_obj_model
  ON embeddings(object_type, object_id, model);
```

Key features:
- **UNIQUE constraint**: Prevents duplicate embeddings per object/model combination
- **text_hash**: Enables skip-on-unchanged optimization during reindexing
- **metadata JSON**: Stores rich context for query results without additional joins

### Text Extraction

Text is built deterministically from each object:

**For Entities:**
```
Name: <name>
Type: <type>
Tags: <tag1>, <tag2>, ... (sorted)
Description: <description>
<attr1>: <value1>
<attr2>: <value2>
...
```

**For Events:**
```
Name: <name>
Type: <type>
Date: <lore_date>
Duration: <lore_duration>
Tags: <tag1>, <tag2>, ... (sorted)
Description: <description>
<attr1>: <value1>
<attr2>: <value2>
...
```

**Attributes** are:
- Sorted alphabetically by key for determinism
- Nested dicts/lists are JSON-serialized with `sort_keys=True`
- Non-ASCII characters preserved (`ensure_ascii=False`)

### Attribute Exclusion

Attributes can be excluded from the search index to prevent internal metadata or sensitive information from affecting search results.

1.  **Internal Attributes**: Any attribute key starting with an underscore (`_`) is automatically excluded (e.g., `_longform`, `_internal_id`).
2.  **User-Configured Exclusions**: Users can specify a list of additional attribute keys to exclude via the "Excluded Attributes" field in the AI Search Panel.

### Embedding Providers

#### LM Studio Provider (Primary)

Uses the LM Studio API endpoint for embeddings:

**Configuration:**
```bash
export EMBED_PROVIDER="lmstudio"
export LMSTUDIO_EMBED_URL="http://localhost:8080/v1/embeddings"
export LMSTUDIO_MODEL="bge-small-en"
export LMSTUDIO_API_KEY="optional-key"  # Optional
```

**Request Format:**
```json
POST /v1/embeddings
{
  "input": ["text 1", "text 2"],
  "model": "bge-small-en"
}
```

**Response Format:**
```json
{
  "data": [
    {"embedding": [0.01, -0.02, ...]},
    {"embedding": [0.03, 0.07, ...]}
  ]
}
```

#### Sentence-Transformers Provider (Fallback)

Uses the `sentence-transformers` library for local embeddings without an external server:

**Configuration:**
```bash
export EMBED_PROVIDER="sentence-transformers"
export LMSTUDIO_MODEL="all-MiniLM-L6-v2"  # Reuses env var
```

Requires: `pip install sentence-transformers`

### Vector Operations

**Normalization:**
All vectors are normalized to unit length before storage, enabling:
- Fast dot-product similarity (equivalent to cosine similarity)
- Simpler query math
- Consistent scoring

**Serialization:**
Vectors are stored as float32 BLOB for:
- Compact storage (4 bytes per dimension)
- Fast deserialization with `numpy.frombuffer`
- Native NumPy compatibility

**Similarity Search:**
Uses dot product on normalized vectors:
```python
similarity = query_vector · document_vector
```

**Top-K Selection:**
Streaming min-heap approach to limit peak memory during queries.

## Usage

### CLI

#### Rebuild Index

```bash
# Rebuild entire index
python -m src.cli.index rebuild --database world.kraken

# Index only entities
python -m src.cli.index rebuild --database world.kraken --type entity

# Use specific provider and model
python -m src.cli.index rebuild \
  --database world.kraken \
  --provider lmstudio \
  --model bge-small-en
```

#### Index Single Object

```bash
# Index an entity
python -m src.cli.index index-object \
  --database world.kraken \
  --type entity \
  --id <entity-uuid>

# Index an event
python -m src.cli.index index-object \
  --database world.kraken \
  --type event \
  --id <event-uuid>
```

#### Query

```bash
# Basic query
python -m src.cli.index query \
  --database world.kraken \
  --text "find the wizard king"

# Filter by type
python -m src.cli.index query \
  --database world.kraken \
  --text "ancient elven cities" \
  --type entity

# Limit results
python -m src.cli.index query \
  --database world.kraken \
  --text "battles and conflicts" \
  --top-k 5

# JSON output
python -m src.cli.index query \
  --database world.kraken \
  --text "magical artifacts" \
  --json
```

### Background Worker

The `DatabaseWorker` includes an `index_object` slot for async indexing:

```python
# In your Qt application
worker.index_object.emit("entity", entity_id, "lmstudio", None)
```

This keeps the GUI responsive during embedding generation.

### Python API

```python
from src.services.db_service import DatabaseService
from src.services.search_service import create_search_service

# Connect to database
db = DatabaseService("world.kraken")
db.connect()

# Create search service
service = create_search_service(
    db._connection,
    provider_name="lmstudio",
    model="bge-small-en"
)

# Index objects
service.index_entity(entity_id)
service.index_event(event_id)

# Rebuild entire index
counts = service.rebuild_index(object_types=["entity", "event"])

# Query
results = service.query("wizard", object_type="entity", top_k=10)

# Results format:
# [
#   {
#     "id": "<embedding-id>",
#     "object_type": "entity",
#     "object_id": "<entity-uuid>",
#     "score": 0.85,
#     "name": "Gandalf",
#     "type": "character",
#     "metadata": {...}
#   },
#   ...
# ]
```

## Performance Considerations

### Indexing Performance

- **Batch Processing**: The rebuild command processes all objects sequentially
- **Skip Unchanged**: Objects with the same `text_hash` are skipped during reindex
- **Network Latency**: LM Studio requests are the primary bottleneck
- **Database Writes**: Uses upsert with UNIQUE constraint for efficiency

**Typical Performance:**
- ~100-500ms per embedding (depends on model and LM Studio config)
- ~1000 objects in 2-10 minutes for initial index
- Subsequent reindexes are faster due to skip-on-unchanged

### Query Performance

- **Linear Scan**: Current implementation uses linear scan for similarity
- **Streaming Top-K**: Limits peak memory usage
- **Model Filtering**: Only compares against embeddings with matching model/dimension

**Typical Performance:**
- <100ms for 1000 embeddings
- <1s for 10,000 embeddings
- Scales linearly with index size

### Future Optimizations

For larger worlds (>10,000 objects), consider:
- **FAISS**: Approximate nearest neighbor search with GPU acceleration
- **Annoy**: Memory-efficient ANN index for CPU
- **Chunking**: Split large attributes into multiple embeddings

The `SearchService` is designed with a pluggable `VectorIndex` protocol to enable these optimizations without breaking changes.

## Best Practices

### Model Selection

**For General Use:**
- `bge-small-en-v1.5` (384d): Fast, good quality
- `all-MiniLM-L6-v2` (384d): Lightweight, sentence-transformers default

**For Better Quality:**
- `bge-base-en-v1.5` (768d): Larger but more accurate
- `e5-large-v2` (1024d): State-of-the-art quality (slower)

**Trade-offs:**
- Larger dimensions = better quality, more storage, slower queries
- Smaller dimensions = faster, less storage, lower quality

### When to Reindex

Reindex when:
- You change the embedding model
- You add significant amounts of new content (>100 objects)
- You update many object descriptions/attributes

You don't need to reindex for:
- Minor description edits (hash check will detect)
- Relation changes (not indexed)
- Name/type changes (automatically reindexed on next rebuild)

### Query Tips

- **Be Specific**: "elven city" better than "city"
- **Use Context**: "ancient battle wizard" better than "wizard"
- **Filter by Type**: Use `--type` to reduce noise
- **Increase top-k**: Default is 10, increase for broader results

## Troubleshooting

### LM Studio Connection Issues

**Error:** `Failed to connect to LM Studio`

**Solutions:**
1. Verify LM Studio is running: Check the app is open
2. Check the endpoint URL: Ensure `LMSTUDIO_EMBED_URL` is correct
3. Verify model supports embeddings: Not all models have embedding endpoints
4. Check firewall: Ensure localhost connections are allowed

**Test Connection:**
```bash
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["test"], "model": "bge-small-en"}'
```

### Model Dimension Mismatch

**Error:** Query returns no results after changing models

**Cause:** Old embeddings use different dimension than new model

**Solution:** Rebuild the index:
```bash
python -m src.cli.index rebuild --database world.kraken --model <new-model>
```

### Slow Indexing

**Symptoms:** Taking >1s per object

**Solutions:**
1. Check LM Studio GPU acceleration is enabled
2. Reduce batch size (implementation detail, currently single-request)
3. Use a smaller model (e.g., 384d vs 768d)
4. Consider sentence-transformers for local processing

### Out of Memory

**Symptoms:** Query crashes with large index

**Solutions:**
1. Reduce `top_k` parameter
2. Use model/type filtering to reduce search space
3. Upgrade to FAISS/Annoy for large indices (future enhancement)

## Security Considerations

- **Local-First**: No data leaves your machine
- **No Credentials**: LM Studio runs locally, no API keys required
- **Privacy**: Full control over model and data
- **Offline**: Works without internet connection

## Migration Guide

### Existing Databases

The embeddings table is created automatically via `_init_schema()` when you connect to an existing database. No manual migration required.

### Changing Models

To switch embedding models:

```bash
# Set new model
export LMSTUDIO_MODEL="new-model-name"

# Rebuild index (this will replace old embeddings)
python -m src.cli.index rebuild --database world.kraken
```

Old embeddings are automatically replaced due to the UNIQUE constraint on `(object_type, object_id, model)`.

### Backup Recommendation

Before major reindexing operations, backup your database:

```bash
cp world.kraken world.kraken.backup
```

The embeddings table is non-destructive and can be dropped/rebuilt without affecting core data.

## Future Enhancements

Planned improvements:
- [ ] GUI search panel with live results
- [ ] Relation embeddings for "who caused X" queries
- [ ] Chunked embeddings for large attribute payloads
- [ ] FAISS integration for large worlds
- [ ] Cross-object "Related items" suggestions
- [ ] Embedding cache for faster reindexing
- [ ] Parallel indexing for rebuild performance

## References

- **LM Studio**: https://lmstudio.ai/
- **BGE Models**: https://huggingface.co/BAAI/bge-small-en-v1.5
- **Sentence Transformers**: https://www.sbert.net/
- **Vector Search**: https://www.pinecone.io/learn/vector-search/

## Contributing

When adding semantic search features:
1. Keep the interface provider-agnostic
2. Add tests for new text building logic
3. Document new environment variables
4. Ensure deterministic behavior for reproducibility
5. Consider memory usage for large indices
