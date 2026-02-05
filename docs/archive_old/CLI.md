---
project: ProjektKraken
document: CLI Tools Overview
last_updated: 2026-01-25
---

# Command-Line Interface (CLI) Tools

ProjektKraken provides a comprehensive command-line interface for managing your worlds without the GUI. All CLI tools share the same command classes and database service as the GUI, ensuring **100% feature parity**.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# List all events in a world
python -m src.cli.event list --database world.kraken

# Create an entity
python -m src.cli.entity create \
  --database world.kraken \
  --name "Gandalf" \
  --type character

# Rebuild semantic search index
python -m src.cli.index rebuild --database world.kraken
```

## Available CLI Modules

ProjektKraken includes **16 CLI modules** covering all core functionality:

| Module | Purpose | Example Command |
|--------|---------|-----------------|
| **event** | Event management (CRUD) | `python -m src.cli.event list --database world.kraken` |
| **entity** | Entity management (CRUD) | `python -m src.cli.entity create --database world.kraken --name "Frodo"` |
| **relation** | Relation management | `python -m src.cli.relation add --database world.kraken --source <id> --target <id>` |
| **attachment** | Image attachments | `python -m src.cli.attachment add --database world.kraken --file image.png` |
| **calendar** | Custom calendars | `python -m src.cli.calendar create --database world.kraken --name "Lunar"` |
| **timeline** | Timeline settings | `python -m src.cli.timeline group --database world.kraken --tags "Type"` |
| **map** | Map and marker management | `python -m src.cli.map create --database world.kraken --name "Middle Earth"` |
| **wiki** | Wiki link scanning | `python -m src.cli.wiki scan --database world.kraken` |
| **index** | Semantic search indexing | `python -m src.cli.index rebuild --database world.kraken` |
| **longform** | Document export | `python -m src.cli.longform export --database world.kraken --output world.md` |
| **obsidian** | Obsidian vault export | `python -m src.cli.obsidian export --database world.kraken --vault-path ./vault` |
| **graph** | Graph generation | `python -m src.cli.graph generate --database world.kraken` |
| **backup** | Backup management | `python -m src.cli.backup create --database world.kraken` |
| **importer** | Import from JSON | `python -m src.cli.importer import --database world.kraken --file data.json` |
| **utils** | Utility commands | `python -m src.cli.utils validate --database world.kraken` |

## Key Features

### ✅ Feature Parity with GUI

All CLI tools use the same:
- **Command classes** from `src/commands/`
- **Database service** from `src/services/db_service.py`
- **Data models** from `src/core/`

This ensures that any operation you can do in the GUI can be done via CLI.

### ✅ Headless Operation

CLI tools are **completely headless**:
- No Qt/PySide6 dependencies required
- Can run on servers without GUI
- Perfect for automation and CI/CD

### ✅ Scripting-Friendly

All CLI tools:
- Return appropriate exit codes (`0` = success, `1` = failure)
- Support JSON output for parsing
- Support batch operations
- Can be chained in shell scripts

### ✅ Automation-Ready

Perfect for:
- Automated testing
- Batch imports/exports
- Database migrations
- Backup automation
- CI/CD pipelines
- Pre-commit hooks

## Common Patterns

### JSON Output

Most commands support `--json` for machine-readable output:

```bash
# List events as JSON
python -m src.cli.event list --database world.kraken --json

# Capture entity ID in variable
ENTITY_ID=$(python -m src.cli.entity create \
  --database world.kraken \
  --name "Test" \
  --json | jq -r '.id')
```

### Verbose Logging

Use `--verbose` or `-v` for debugging:

```bash
python -m src.cli.event list --database world.kraken --verbose
```

### Force Operations

Skip confirmations with `--force` or `-f`:

```bash
# Delete without confirmation
python -m src.cli.event delete \
  --database world.kraken \
  --id <event-id> \
  --force
```

## Common Use Cases

### 1. Batch Entity Creation

```bash
#!/bin/bash
DATABASE="world.kraken"

# Create entities from CSV
cat entities.csv | while IFS=, read name type description; do
  python -m src.cli.entity create \
    -d $DATABASE \
    --name "$name" \
    --type "$type" \
    --description "$description"
done
```

### 2. Automated Backups

```bash
#!/bin/bash
DATABASE="world.kraken"
BACKUP_DIR="backups/$(date +%Y-%m-%d)"

# Create backup
mkdir -p "$BACKUP_DIR"
python -m src.cli.backup create \
  --database $DATABASE \
  --output "$BACKUP_DIR/world.backup"
```

### 3. Semantic Search Indexing

```bash
#!/bin/bash
DATABASE="world.kraken"

# Rebuild index with LM Studio
export EMBED_PROVIDER="lmstudio"
export LMSTUDIO_EMBED_URL="http://localhost:8080/v1/embeddings"

python -m src.cli.index rebuild \
  --database $DATABASE \
  --provider lmstudio
```

### 4. Export Workflows

```bash
#!/bin/bash
DATABASE="world.kraken"
OUTPUT_DIR="exports"

# Export longform to markdown
python -m src.cli.longform export \
  --database $DATABASE \
  --output "$OUTPUT_DIR/world.md"

# Export to Obsidian vault
python -m src.cli.obsidian export \
  --database $DATABASE \
  --vault-path "$OUTPUT_DIR/obsidian"
```

### 5. Testing and Validation

```bash
#!/bin/bash
DATABASE="world.kraken"

# Run validation checks
python -m src.cli.utils validate --database $DATABASE

# Exit on error
if [ $? -ne 0 ]; then
  echo "Validation failed!"
  exit 1
fi

echo "Validation passed!"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Validate World Database
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: List events
        run: |
          python -m src.cli.event list \
            --database world.kraken \
            --json > events.json
      
      - name: Export longform
        run: |
          python -m src.cli.longform export \
            --database world.kraken \
            --output world.md
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: exports
          path: |
            events.json
            world.md
```

## Requirements

### Python Dependencies

All dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Note:** Qt/PySide6 dependencies are included but not used by CLI tools.

### System Requirements

- Python 3.11+
- SQLite 3.35+
- No GUI required (headless operation supported)

## Architecture

CLI tools follow the **Command Pattern**:

```
CLI Tool → Command Class → Database Service → SQLite
```

**Example:**

```python
# src/cli/event.py
from src.commands.create_event import CreateEventCommand
from src.services.db_service import DatabaseService

# Create command
db_service = DatabaseService(database_path)
command = CreateEventCommand(
    db_service=db_service,
    name="Battle",
    lore_date=1000.0
)

# Execute
result = command.execute()
if result.success:
    print(f"Created event: {result.data['id']}")
```

This ensures:
- ✅ 100% feature parity with GUI
- ✅ Shared validation logic
- ✅ Consistent error handling
- ✅ Undo/redo support (when applicable)

## Detailed Documentation

For comprehensive command reference and examples, see:

**[src/cli/README.md](../src/cli/README.md)** - Complete CLI documentation with:
- Detailed command syntax for all 16 modules
- Parameter descriptions
- Usage examples
- Common workflows
- Troubleshooting guide

## Quick Reference

### Event Management

```bash
# Create
python -m src.cli.event create -d world.kraken --name "Battle" --date 1000

# List
python -m src.cli.event list -d world.kraken --type historical

# Show
python -m src.cli.event show -d world.kraken --id <event-id>

# Update
python -m src.cli.event update -d world.kraken --id <event-id> --name "New Name"

# Delete
python -m src.cli.event delete -d world.kraken --id <event-id> --force
```

### Entity Management

```bash
# Create
python -m src.cli.entity create -d world.kraken --name "Gandalf" --type character

# List
python -m src.cli.entity list -d world.kraken --type character

# Show with relations
python -m src.cli.entity show -d world.kraken --id <entity-id> --relations

# Update
python -m src.cli.entity update -d world.kraken --id <entity-id> --name "New Name"

# Delete
python -m src.cli.entity delete -d world.kraken --id <entity-id> --force
```

### Semantic Search

```bash
# Rebuild index
python -m src.cli.index rebuild -d world.kraken --provider lmstudio

# Query
python -m src.cli.index query -d world.kraken --text "find the wizard" --top-k 5

# Index single object
python -m src.cli.index index-object -d world.kraken --type entity --id <entity-id>

# Delete object index
python -m src.cli.index delete-object -d world.kraken --type entity --id <entity-id>
```

### Export

```bash
# Longform to markdown
python -m src.cli.longform export -d world.kraken --output world.md

# Obsidian vault
python -m src.cli.obsidian export -d world.kraken --vault-path ./vault
```

## Troubleshooting

### Import Errors

If you get import errors:

```bash
# Ensure you're in repository root
cd /path/to/ProjektKraken

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Database Not Found

If database file not found:

```bash
# Database is created automatically for create operations
python -m src.cli.entity create -d new_world.kraken --name "Test"

# For other operations, ensure path is correct
python -m src.cli.event list -d /absolute/path/to/world.kraken
```

### Permission Errors

If database is locked:

```bash
# Close GUI application first
# Or use a different database file
python -m src.cli.event list -d world_copy.kraken
```

## Related Documentation

- **[src/cli/README.md](../src/cli/README.md)** - Complete CLI command reference
- **[Design.md](../Design.md)** - Architecture specification
- **[DATABASE.md](DATABASE.md)** - Database architecture
- **[SEMANTIC_SEARCH.md](SEMANTIC_SEARCH.md)** - Semantic search setup
- **[LONGFORM.md](LONGFORM.md)** - Longform document feature

## Support

For issues or questions:
- Check detailed documentation in `src/cli/README.md`
- Use `--verbose` flag for debugging
- Run `--help` on any command for usage information
- Report bugs via GitHub issues

---

**Status:** 16 CLI modules fully functional  
**Feature Parity:** 100% with GUI for core operations  
**Python Version:** 3.11+
