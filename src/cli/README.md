# ProjektKraken CLI Tools

Command-line interface tools for managing ProjektKraken databases without the GUI.

## Overview

The CLI tools provide headless access to all core ProjektKraken functionality:
- Event management (create, list, show, update, delete)
- Entity management (create, list, show, update, delete)
- Relation management (add, list, delete)
- Longform document export

## Requirements

- Python 3.10+
- ProjektKraken dependencies (see `requirements.txt`)
- No GUI/Qt dependencies required for CLI tools

## Event Management

### Create an Event

```bash
python -m src.cli.event create \
  --database world.kraken \
  --name "The Great Battle" \
  --date 1000.5 \
  --type historical \
  --description "A pivotal moment in history"
```

### List Events

```bash
# List all events
python -m src.cli.event list --database world.kraken

# Filter by type
python -m src.cli.event list --database world.kraken --type historical

# JSON output
python -m src.cli.event list --database world.kraken --json
```

### Show Event Details

```bash
python -m src.cli.event show --database world.kraken --id <event-id>

# JSON output
python -m src.cli.event show --database world.kraken --id <event-id> --json
```

### Update an Event

```bash
python -m src.cli.event update \
  --database world.kraken \
  --id <event-id> \
  --name "New Event Name" \
  --date 2000.0
```

### Delete an Event

```bash
# Interactive confirmation
python -m src.cli.event delete --database world.kraken --id <event-id>

# Force delete (no confirmation)
python -m src.cli.event delete --database world.kraken --id <event-id> --force
```

## Entity Management

### Create an Entity

```bash
python -m src.cli.entity create \
  --database world.kraken \
  --name "Gandalf" \
  --type character \
  --description "A wise wizard"
```

### List Entities

```bash
# List all entities
python -m src.cli.entity list --database world.kraken

# Filter by type
python -m src.cli.entity list --database world.kraken --type character

# JSON output
python -m src.cli.entity list --database world.kraken --json
```

### Show Entity Details

```bash
# Basic details
python -m src.cli.entity show --database world.kraken --id <entity-id>

# Include relations
python -m src.cli.entity show --database world.kraken --id <entity-id> --relations

# JSON output
python -m src.cli.entity show --database world.kraken --id <entity-id> --json
```

### Update an Entity

```bash
python -m src.cli.entity update \
  --database world.kraken \
  --id <entity-id> \
  --name "New Name" \
  --type location
```

### Delete an Entity

```bash
# Interactive confirmation
python -m src.cli.entity delete --database world.kraken --id <entity-id>

# Force delete (no confirmation)
python -m src.cli.entity delete --database world.kraken --id <entity-id> --force
```

## Relation Management

### Add a Relation

```bash
# Unidirectional relation
python -m src.cli.relation add \
  --database world.kraken \
  --source <source-id> \
  --target <target-id> \
  --type "participated_in"

# Bidirectional relation
python -m src.cli.relation add \
  --database world.kraken \
  --source <source-id> \
  --target <target-id> \
  --type "allies" \
  --bidirectional
```

### List Relations

```bash
# List all relations for an entity/event
python -m src.cli.relation list --database world.kraken --source <source-id>

# JSON output
python -m src.cli.relation list --database world.kraken --source <source-id> --json
```

### Delete a Relation

```bash
# Interactive confirmation
python -m src.cli.relation delete --database world.kraken --id <relation-id>

# Force delete (no confirmation)
python -m src.cli.relation delete --database world.kraken --id <relation-id> --force
```

## Longform Export

```bash
# Export to stdout
python -m src.cli.export_longform world.kraken

# Export to file
python -m src.cli.export_longform world.kraken output.md

# Export specific document
python -m src.cli.export_longform world.kraken --doc-id custom
```

## Common Options

All CLI tools support:

- `--verbose` or `-v`: Enable verbose logging
- `--json`: Output as JSON (where applicable)
- `--force` or `-f`: Skip confirmation prompts (for delete operations)

## Examples

### Complete Workflow

```bash
# Create a database (happens automatically on first use)
DATABASE="myworld.kraken"

# Create an event
EVENT_ID=$(python -m src.cli.event create \
  -d $DATABASE \
  --name "The Battle of Five Armies" \
  --date 1500.0 \
  --type combat \
  --json | jq -r '.id')

# Create entities
GANDALF_ID=$(python -m src.cli.entity create \
  -d $DATABASE \
  --name "Gandalf" \
  --type character \
  --description "The Grey Wizard" \
  --json | jq -r '.id')

THORIN_ID=$(python -m src.cli.entity create \
  -d $DATABASE \
  --name "Thorin" \
  --type character \
  --description "King under the Mountain" \
  --json | jq -r '.id')

# Link entities to event
python -m src.cli.relation add \
  -d $DATABASE \
  --source $GANDALF_ID \
  --target $EVENT_ID \
  --type "participated_in"

python -m src.cli.relation add \
  -d $DATABASE \
  --source $THORIN_ID \
  --target $EVENT_ID \
  --type "participated_in"

# View results
python -m src.cli.event show -d $DATABASE --id $EVENT_ID
python -m src.cli.entity show -d $DATABASE --id $GANDALF_ID --relations
```

### Scripting and Automation

The CLI tools return appropriate exit codes:
- `0`: Success
- `1`: Failure

This makes them suitable for scripts and automation:

```bash
#!/bin/bash
set -e  # Exit on error

DATABASE="world.kraken"

# Batch create entities
cat entities.csv | while IFS=, read name type description; do
  python -m src.cli.entity create \
    -d $DATABASE \
    --name "$name" \
    --type "$type" \
    --description "$description"
done

echo "✓ All entities created successfully"
```

## Integration with CI/CD

The CLI tools are ideal for:
- Automated testing of worldbuilding consistency
- Batch imports/exports
- Database migrations
- Automated backup and restore
- Pre-commit hooks for validation

Example GitHub Actions workflow:

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
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Validate events
        run: |
          python -m src.cli.event list --database world.kraken --json > events.json
          # Add custom validation here
      - name: Export longform
        run: python -m src.cli.export_longform world.kraken world.md
```

## Architecture

All CLI tools:
- Reuse the same command classes as the GUI (`src/commands/`)
- Use the same database service (`src/services/db_service.py`)
- Are completely headless (no Qt/GUI dependencies)
- Return structured CommandResult objects
- Support both human-readable and JSON output

This ensures 100% feature parity between CLI and GUI for core operations.

## Troubleshooting

### Database Not Found

If you get a "Database file not found" error:
- Ensure the path is correct
- The database will be created automatically on first use for create operations
- For other operations, create the database first or use an existing one

### Import Errors

If you get import errors:
- Ensure you're running from the repository root
- Activate your virtual environment
- Install dependencies: `pip install -r requirements.txt`

### Verbose Logging

For debugging, use the `--verbose` flag:

```bash
python -m src.cli.event list --database world.kraken --verbose
```

This will show detailed logging information about database operations.
