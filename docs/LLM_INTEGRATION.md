---
**Project:** ProjektKraken  
**Document:** Multi-Provider LLM Integration Guide  
**Last Updated:** 2026-01-01  
**Commit:** `d9e3f83`  
---

# Multi-Provider LLM Integration Guide

## Overview

ProjektKraken now includes production-ready multi-provider LLM support for both embeddings and text generation. This guide covers setup, configuration, and usage of the LLM integration features.

## Supported Providers

### Local Providers

#### LM Studio (Default, Enabled by Default)
- **Embeddings**: ✅ Supported
- **Generation**: ✅ Supported
- **Streaming**: ✅ Supported
- **Setup**: Requires LM Studio running locally
- **Default URLs**:
  - Embeddings: `http://localhost:8080/v1/embeddings`
  - Generation: `http://localhost:8080/v1/completions`

### Remote Providers (Opt-in per World)

#### OpenAI
- **Embeddings**: ✅ Supported (text-embedding-ada-002)
- **Generation**: ✅ Supported (GPT-3.5-turbo, GPT-4, etc.)
- **Streaming**: ✅ Supported
- **Requires**: API key (starts with `sk-...`)

#### Google Vertex AI
- **Embeddings**: ✅ Supported (textembedding-gecko)
- **Generation**: ✅ Supported (text-bison, PaLM)
- **Streaming**: ⚠️ Limited support (fallback to non-streaming)
- **Requires**: GCP project ID, credentials

#### Anthropic Claude
- **Embeddings**: ❌ Not supported (Anthropic doesn't offer embeddings)
- **Generation**: ✅ Supported (Claude 3 Haiku, Sonnet, Opus)
- **Streaming**: ✅ Supported
- **Requires**: API key (starts with `sk-ant-...`)

## Configuration

### Via UI (Recommended)

1. Open **File → AI Settings** (or press `Ctrl+Shift+A`)
2. Navigate to the **Text Generation** tab
3. Select your desired provider from the dropdown
4. Enter provider-specific credentials
5. Click **Save Generation Settings**

### Via Environment Variables

Set these before launching ProjektKraken:

```bash
# LM Studio (Embeddings & Generation)
export LMSTUDIO_MODEL="nomic-embed-text-v1.5"
export LMSTUDIO_EMBED_URL="http://localhost:8080/v1/embeddings"
export LMSTUDIO_GENERATE_URL="http://localhost:8080/v1/completions"
export LMSTUDIO_API_KEY=""  # Optional

# OpenAI
export OPENAI_API_KEY="sk-your-key-here"

# Google Vertex AI
export GOOGLE_PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### Via QSettings (Persistent Storage)

Settings are automatically saved to QSettings when configured via the UI:

- **Linux**: `~/.config/ProjektKraken/ProjektKraken.conf`
- **Windows**: `HKEY_CURRENT_USER\Software\ProjektKraken\ProjektKraken`
- **macOS**: `~/Library/Preferences/com.ProjektKraken.ProjektKraken.plist`

## Architecture

### Provider Abstraction

```python
from src.services.llm_provider import Provider, create_provider

# Create a provider instance
provider = create_provider("lmstudio")  # or "openai", "google", "anthropic"

# Check capabilities
meta = provider.metadata()
print(meta["supports_embeddings"])  # True/False
print(meta["supports_generation"])   # True/False
print(meta["supports_streaming"])    # True/False

# Generate embeddings
embeddings = provider.embed(["Hello world", "Test text"])
# Returns: np.ndarray of shape (2, embedding_dimension)

# Generate text
result = provider.generate(
    prompt="Describe a fantasy world",
    max_tokens=512,
    temperature=0.7
)
print(result["text"])

# Stream generation
async for chunk in provider.stream_generate(
    prompt="Write a story",
    max_tokens=1000
):
    print(chunk["delta"], end="", flush=True)
```

### Embedding Service

```python
from src.services.embedding_service import create_embedding_service

# Create embedding service
service = create_embedding_service(
    db_connection,
    provider_id="lmstudio",
    world_id="my-world"  # Optional, for per-world configuration
)

# Generate and validate embeddings
embeddings = service.embed_batch(["text1", "text2"])

# Count embeddings in database
count = service.count_embeddings_by_model()

# Get embeddings filtered by model and dimension
results = service.get_embeddings_by_model(
    object_type="entity"  # Optional: 'entity' or 'event'
)

# Rebuild index
service.rebuild_index()
```

## Error Handling & Resilience

### Circuit Breaker Pattern

All providers implement a circuit breaker to prevent cascading failures:

```python
provider = create_provider("openai", api_key="...")

# Circuit breaker automatically opens after 5 consecutive failures
# Waits 60 seconds before attempting to close
try:
    result = provider.generate("Test")
except Exception as e:
    if "Circuit breaker is OPEN" in str(e):
        # Provider is temporarily unavailable
        # Try again after cooldown period
        pass
```

### Automatic Retries

Failed requests are automatically retried with exponential backoff:

- **Max retries**: 3 attempts
- **Backoff**: 2^attempt seconds (2s, 4s, 8s)
- **Timeout**: Configurable per provider (default 30s)

### Health Checks

Check provider availability before making requests:

```python
health = provider.health_check()
print(health["status"])      # "healthy", "degraded", or "unhealthy"
print(health["latency_ms"])  # Response time in milliseconds
print(health["message"])     # Human-readable status message
```

## Index Management

### Per-World, Per-Model Indexes

Embeddings are stored with model and dimension metadata, allowing multiple models to coexist:

```
indexes/
  └── my-world_lmstudio_nomic-embed-text-v1.5.index
  └── my-world_openai_text-embedding-ada-002.index
```

### Index Metadata

Each index stores metadata about the embeddings:

```json
{
  "model": "lmstudio:nomic-embed-text-v1.5",
  "dimension": 768,
  "count": 1523,
  "world_id": "my-world"
}
```

## Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
2. Use environment variables or QSettings for storage
3. Use the "Clear All Generation Settings" button to remove stored keys
4. API keys are stored as passwords (hidden in UI)

### Audit Logging (Opt-in)

Enable audit logging to track all LLM requests:

1. Open AI Settings → Text Generation tab
2. Check "Enable audit logging"
3. Logs are written to application log directory

Audit logs include:
- Timestamp
- Provider used
- Prompt text
- Generated response
- Token usage
- Request metadata

**Warning**: Audit logs may contain sensitive information. Secure appropriately.

## Usage Examples

### Example 1: Semantic Search with LM Studio

```python
import sqlite3
from src.services.embedding_service import create_embedding_service

# Connect to database
conn = sqlite3.connect("myworld.kraken")
conn.row_factory = sqlite3.Row

# Create service with LM Studio
service = create_embedding_service(
    conn,
    provider_id="lmstudio",
    model="nomic-embed-text-v1.5"
)

# Index an entity
from src.services.search_service import SearchService
search_service = SearchService(conn, service.provider)
search_service.index_entity(entity_id="...")

# Search
results = search_service.search(
    text="Find wizards",
    top_k=5
)

for result in results:
    print(f"{result['name']} - Score: {result['score']:.3f}")
```

### Example 2: Text Generation with OpenAI

```python
from src.services.llm_provider import create_provider

# Create provider with API key
provider = create_provider(
    "openai",
    api_key="sk-your-key-here",
    model="gpt-4"
)

# Generate text
result = provider.generate(
    prompt="""Describe the capital city of a fantasy empire.
    Include details about architecture, culture, and notable landmarks.""",
    max_tokens=500,
    temperature=0.8
)

print(result["text"])
print(f"Tokens used: {result['usage']['total_tokens']}")
```

### Example 3: Streaming with Anthropic

```python
import asyncio
from src.services.llm_provider import create_provider

async def stream_story():
    provider = create_provider(
        "anthropic",
        api_key="sk-ant-your-key-here",
        model="claude-3-sonnet-20240229"
    )
    
    print("Generating story...\n")
    
    async for chunk in provider.stream_generate(
        prompt="Write a short story about a dragon and a knight.",
        max_tokens=1000,
        temperature=0.9
    ):
        print(chunk["delta"], end="", flush=True)
        
        if chunk.get("finish_reason"):
            print(f"\n\nFinished: {chunk['finish_reason']}")
            break

asyncio.run(stream_story())
```

### Example 4: Multi-Provider Fallback

```python
from src.services.llm_provider import create_provider

def generate_with_fallback(prompt: str) -> str:
    """Try multiple providers with automatic fallback."""
    providers = ["lmstudio", "openai", "anthropic"]
    
    for provider_id in providers:
        try:
            print(f"Trying {provider_id}...")
            provider = create_provider(provider_id)
            
            # Check health first
            health = provider.health_check()
            if health["status"] != "healthy":
                continue
            
            # Generate
            result = provider.generate(prompt, max_tokens=256)
            print(f"Success with {provider_id}!")
            return result["text"]
            
        except Exception as e:
            print(f"{provider_id} failed: {e}")
            continue
    
    raise Exception("All providers failed")

# Usage
text = generate_with_fallback("Describe a magical artifact")
print(text)
```

## Troubleshooting

### LM Studio Connection Failed

**Error**: `Failed to connect to LM Studio at http://localhost:8080/v1/embeddings`

**Solutions**:
1. Ensure LM Studio is running
2. Verify the model is loaded in LM Studio
3. Check the API URL in settings (default port is 8080)
4. Ensure no firewall is blocking localhost connections

### OpenAI API Key Invalid

**Error**: `Failed to generate completion from OpenAI API`

**Solutions**:
1. Verify API key is correct (starts with `sk-`)
2. Check API key has sufficient credits
3. Ensure API key has permissions for the model you're using
4. Test with `curl` to verify key works:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

### Google Vertex AI Authentication Failed

**Error**: `Cannot connect to Vertex AI API`

**Solutions**:
1. Verify GCP project ID is correct
2. Ensure credentials file exists at specified path
3. Check credentials have Vertex AI permissions
4. Test with gcloud CLI:
   ```bash
   gcloud auth application-default login
   ```

### Dimension Mismatch

**Error**: `Embedding dimension mismatch: expected 768, got 1536`

**Solutions**:
1. Different models have different dimensions
2. Clear existing embeddings: AI Settings → Embeddings tab → Rebuild Index
3. Or use `EmbeddingService.delete_embeddings_by_model()` to remove old embeddings

### Circuit Breaker Open

**Error**: `Circuit breaker is OPEN - too many recent failures`

**Solutions**:
1. Wait 60 seconds for automatic reset
2. Check provider health: `provider.health_check()`
3. Verify network connectivity
4. Check provider service status

## Performance Optimization

### Batch Embedding Generation

Generate embeddings in batches for better performance:

```python
# Good: Batch processing
texts = [entity.description for entity in entities]
embeddings = provider.embed(texts)

# Avoid: One at a time
for entity in entities:
    embedding = provider.embed([entity.description])  # Inefficient
```

### Embedding Caching

The database automatically caches embeddings using content hash:

- Embeddings are only regenerated if text content changes
- Hash-based change detection is automatic
- No manual cache management needed

### Index Persistence

Rebuild indexes periodically, not on every query:

```python
# Rebuild after bulk imports
service.rebuild_index()

# Not needed for individual entity updates
# (indexes update automatically)
```

## Migration from Legacy Search

If you're upgrading from the old search system:

1. **Backup your database** before migrating
2. Old embeddings remain compatible
3. New providers can coexist with old embeddings
4. Rebuild index to use new provider:
   - Open AI Settings → Embeddings tab
   - Select your provider and model
   - Click "Rebuild Index"

## Support

For issues or questions:

1. Check this documentation
2. Review provider-specific docs:
   - [OpenAI API Docs](https://platform.openai.com/docs)
   - [Google Vertex AI Docs](https://cloud.google.com/vertex-ai/docs)
   - [Anthropic API Docs](https://docs.anthropic.com)
3. Open an issue on GitHub

## API Reference

Full API documentation is available in the docstrings:

```python
help(Provider)  # Provider interface
help(create_provider)  # Factory function
help(EmbeddingService)  # Embedding service
help(LMStudioProvider)  # LM Studio implementation
```

## License

This LLM integration is part of ProjektKraken and follows the same license terms.
