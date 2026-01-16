# Prompt Templates

This directory contains prompt templates for LLM text generation in ProjektKraken.

## Template Format

Each template file consists of two parts:

1. **YAML Metadata Header** (enclosed in `---` markers)
2. **Prompt Content** (the actual system prompt text)

### Example Template Structure

```
---
version: 1.0
template_id: fantasy_worldbuilder
name: Fantasy World-Builder
description: Default system prompt for fantasy worldbuilding assistance
author: ProjektKraken Team
created: 2026-01-16
tags: [fantasy, worldbuilding, default]
---

You are an expert fantasy world-builder assisting a user...
```

### Metadata Fields

- `version` (required): Semantic version number (e.g., "1.0", "2.0")
- `template_id` (required): Unique identifier for the template family
- `name` (required): Human-readable name
- `description` (optional): Brief description of the template's purpose
- `author` (optional): Template author/maintainer
- `created` (optional): Creation date (YYYY-MM-DD)
- `tags` (optional): List of tags for categorization

### File Naming Convention

Template files should follow this pattern:
```
{template_id}_v{version}.txt
```

Examples:
- `fantasy_worldbuilder_v1.txt`
- `fantasy_worldbuilder_v2.txt`
- `scifi_worldbuilder_v1.txt`

## Directory Structure

```
templates/
└── system_prompts/
    ├── fantasy_worldbuilder_v1.txt
    ├── fantasy_worldbuilder_v2.txt
    └── README.md (this file)
```

## Usage

Templates are loaded via the `PromptLoader` class in `src/services/prompt_loader.py`:

```python
from src.services.prompt_loader import PromptLoader

loader = PromptLoader()

# Load latest version of a template
template = loader.load_template("fantasy_worldbuilder")

# Load specific version
template = loader.load_template("fantasy_worldbuilder", version="1.0")

# List all available templates
templates = loader.list_templates()
```

## Version Management

- Each template ID can have multiple versions
- The system automatically detects the latest version
- Users can specify a version explicitly or use the default (latest)
- Version numbers should follow semantic versioning principles

## Adding New Templates

1. Create a new file following the naming convention
2. Include proper YAML metadata
3. Write the prompt content below the metadata
4. Test the template with `PromptLoader.validate_template()`
5. Update this README if adding a new template family
