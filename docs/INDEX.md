---
**Project:** ProjektKraken  
**Document:** Documentation Index  
**Last Updated:** 2026-01-25  
---

# Documentation Index

This document provides an organized overview of all ProjektKraken documentation.

## Quick Start

- **[README.md](../README.md)** - Project overview, installation, and basic usage
- **[USER_WORKFLOWS.md](USER_WORKFLOWS.md)** - Step-by-step workflows for common worldbuilding tasks
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development environment setup
- **[CLI.md](CLI.md)** - Command-line tools overview and quick reference

## Architecture & Design

- **[Design.md](../Design.md)** - Comprehensive design specification covering:
  - Product vision and philosophy
  - Technical architecture (SOA, Command Pattern)
  - Data architecture (Hybrid SQLite model)
  - Time system (Float storage, custom calendars)
  - UI/UX specification
  - CLI tools overview

- **[DATABASE.md](DATABASE.md)** - Database architecture and best practices:
  - DatabaseService architecture
  - Schema design (core tables, indexes)
  - Connection and transaction management
  - Performance optimization
  - Security best practices
  - Testing patterns
  - Common CRUD patterns
  - Migration strategy

- **[SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md)** - Auto-generated database schema reference with ER diagrams
- **[QT_THREADING_SAFETY.md](QT_THREADING_SAFETY.md)** - Qt threading patterns and safety guidelines

## Security & Production Readiness

- **[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)** - Comprehensive production readiness assessment
  - Code quality metrics and reviews
  - Architecture and threading safety
  - Security scan results
  - Performance assessment
  - Risk assessment and recommendations

## Security

- **[SECURITY.md](SECURITY.md)** - Security best practices:
  - SQL injection prevention
  - Data validation
  - Input sanitization
  - Secure file handling
  - Authentication considerations

## Features Documentation

### Core Features

- **[WIKI_LINKING.md](WIKI_LINKING.md)** - ID-based wiki-style linking system:
  - Link format (ID-based and legacy)
  - Autocomplete functionality
  - Broken link detection
  - Navigation and name change propagation
  - Quick start demo with sample data
  - Architecture and API reference

- **[MAP_USAGE_EXAMPLES.md](MAP_USAGE_EXAMPLES.md)** - Interactive map system:
  - Maps and markers
  - Normalized coordinate system
  - Drag-and-drop functionality
  - Marker customization
  - CLI usage examples

- **[LONGFORM.md](LONGFORM.md)** - Longform document feature:
  - Hierarchical document structure
  - Position system and ordering
  - Parent-child relationships
  - Title overrides
  - Markdown export
  - Service and CLI usage

### Advanced Features

- **[SEMANTIC_SEARCH.md](SEMANTIC_SEARCH.md)** - Local semantic search system:
  - LM Studio integration
  - Embedding generation and storage
  - Text extraction and indexing
  - Natural language queries
  - Performance considerations

- **[LLM_INTEGRATION.md](LLM_INTEGRATION.md)** - Multi-provider LLM support:
  - Supported providers (LM Studio, OpenAI, Google Vertex AI, Anthropic)
  - Configuration via UI and environment variables
  - Embeddings and text generation
  - Streaming support
  - Security and privacy

- **[WEBSERVER.md](WEBSERVER.md)** - Embedded FastAPI webserver:
  - REST API endpoints (V1: read-only)
  - Longform document serving
  - Threading model and integration
  - Security considerations
  - Usage examples

## CLI Tools

- **[CLI.md](CLI.md)** - Command-line interface overview:
  - 16 CLI modules for headless operation
  - 100% feature parity with GUI
  - Automation and scripting examples
  - CI/CD integration

- **[src/cli/README.md](../src/cli/README.md)** - Complete CLI command reference:
  - Detailed command syntax for all modules
  - Event, entity, relation management
  - Semantic search indexing
  - Map, calendar, timeline tools
  - Export and backup commands

## Migration Guides

- **[TAG_MIGRATION_GUIDE.md](TAG_MIGRATION_GUIDE.md)** - Tag normalization migration:
  - Schema changes (denormalized → normalized tables)
  - Migration process
  - Backward compatibility
  - Performance improvements

## Specialized Documentation

- **[BACKUP_STRATEGY.md](BACKUP_STRATEGY.md)** - Backup system documentation
- **[RELEASE_POLICY.md](RELEASE_POLICY.md)** - Release process and versioning
- **[PYVIS_INTEGRATION_GUIDE.md](PYVIS_INTEGRATION_GUIDE.md)** - Graph visualization integration
- **[TEMPORAL_MAPS_CONCEPT.md](TEMPORAL_MAPS_CONCEPT.md)** - Temporal maps and 4D visualization
- **[RELATION_ATTRIBUTES_UI_PLAN.md](RELATION_ATTRIBUTES_UI_PLAN.md)** - Relation attributes UI design

## LLM & AI Documentation

- **[LLM_REVIEW.md](LLM_REVIEW.md)** - Detailed LLM integration review (516 lines)
- **[LLM_REVIEW_SUMMARY.md](LLM_REVIEW_SUMMARY.md)** - Quick reference for LLM assessment
- **[COVERAGE_IMPROVEMENT_SUMMARY.md](COVERAGE_IMPROVEMENT_SUMMARY.md)** - Testing coverage metrics

## Project Information

- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and notable changes
- **[LICENSE.md](LICENSE.md)** - GNU Affero General Public License v3.0 (AGPLv3)
- **[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)** - Production readiness status

## API Documentation (Sphinx)

The project uses Sphinx for auto-generated API documentation from code docstrings:

- **[index.rst](index.rst)** - Sphinx documentation index
- **[modules.rst](modules.rst)** - Auto-generated module reference
- **API Modules:**
  - [app.rst](app.rst) - Application entry point and MainWindow
  - [cli.rst](cli.rst) - Command-line tools
  - [commands.rst](commands.rst) - Command pattern implementations
  - [core.rst](core.rst) - Business logic and data models
  - [gui.rst](gui.rst) - PySide6 widgets and UI components
  - [gui.dialogs.rst](gui.dialogs.rst) - Dialog windows
  - [gui.widgets.rst](gui.widgets.rst) - Custom widgets
  - [services.rst](services.rst) - Data access and background workers

### Building API Documentation

```bash
cd docs
sphinx-build -b html . _build
```

## Documentation Standards

All documentation follows these standards:

1. **Metadata Header**: Each document includes project name, document title, last updated date, and commit hash
2. **Markdown Format**: Using GitHub Flavored Markdown (GFM)
3. **Code Examples**: Include language identifiers for syntax highlighting
4. **Links**: Use relative paths for internal documentation links
5. **Structure**: Clear hierarchy with H2 and H3 headings

## File Organization

```
ProjektKraken/
├── README.md                          # Main project overview
├── Design.md                          # Architecture specification
├── CHANGELOG.md                       # Version history
└── docs/
    ├── INDEX.md                       # This file
    │
    ├── User Documentation
    │   └── USER_WORKFLOWS.md          # Step-by-step workflows for users
    │
    ├── Core Documentation
    │   ├── DATABASE.md                # Database architecture
    │   ├── DEVELOPMENT.md             # Development setup
    │   ├── TESTING.md                 # Testing guide
    │   ├── SECURITY.md                # Security practices
    │   ├── QT_THREADING_SAFETY.md     # Threading patterns
    │   ├── PRODUCTION_READINESS.md    # Production readiness assessment
    │   └── SCHEMA_REFERENCE.md        # Auto-generated schema
    │
    ├── Feature Documentation
    │   ├── WIKI_LINKING.md            # Wiki linking feature
    │   ├── MAP_USAGE_EXAMPLES.md      # Map system feature
    │   ├── LONGFORM.md                # Longform document feature
    │   ├── SEMANTIC_SEARCH.md         # Semantic search feature
    │   ├── LLM_INTEGRATION.md         # LLM integration feature
    │   ├── WEBSERVER.md               # Embedded API server
    │   └── CLI.md                     # CLI tools overview
    │
    ├── Specialized Guides
    │   ├── TAG_MIGRATION_GUIDE.md     # Tag migration guide
    │   ├── BACKUP_STRATEGY.md         # Backup system
    │   ├── RELEASE_POLICY.md          # Release process
    │   ├── PYVIS_INTEGRATION_GUIDE.md # Graph visualization
    │   ├── TEMPORAL_MAPS_CONCEPT.md   # 4D maps concept
    │   └── RELATION_ATTRIBUTES_UI_PLAN.md  # UI planning
    │
    ├── LLM & AI Documentation
    │   ├── LLM_REVIEW.md              # Detailed LLM review
    │   ├── LLM_REVIEW_SUMMARY.md      # LLM review summary
    │   └── COVERAGE_IMPROVEMENT_SUMMARY.md
    │
    ├── Sphinx Documentation
    │   ├── index.rst                  # Sphinx index
    │   ├── conf.py                    # Sphinx configuration
    │   ├── generate_schema_docs.py    # Schema doc generator
    │   ├── modules.rst                # Module index
    │   ├── app.rst, cli.rst, etc.     # Auto-generated API docs
    │
    ├── archive/                       # Historical reports
    │   ├── README.md                  # Archive index
    │   ├── CODE_ANALYSIS_REPORT.md    # (Dec 2024)
    │   ├── CODE_IMPROVEMENTS_SUMMARY.md
    │   ├── PRODUCTION_READINESS_REPORT.md
    │   ├── REFACTORING_SUMMARY.md
    │   ├── ARCHITECTURE_DIAGRAMS.md
    │   ├── CODE_REVIEW_SUMMARY.md     # (Jan 2026, superseded)
    │   ├── CODE_REVIEW_EXTENDED.md    # (Jan 2026, superseded)
    │   ├── CODE_REVIEW_REPORT.md      # (Jan 2026, superseded)
    │   └── REVIEW_SUMMARY.md          # (Jan 2026, superseded)
    │
    └── LICENSE.md                     # License text
```

## Archive

Historical code analysis and review reports are preserved in **[docs/archive/](archive/)** for reference. These documents were created during development and refactoring efforts but are no longer actively maintained.

**Superseded Documents:**
- Code review reports from January 2026 have been consolidated into **[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)**
- Historical architecture reports from December 2024 - January 2025

See **[docs/archive/README.md](archive/README.md)** for complete archive index.

## Contributing to Documentation

When updating documentation:

1. **Add metadata header** to all new markdown files
2. **Update this INDEX.md** if adding/removing/renaming files
3. **Update index.rst** for Sphinx documentation structure changes
4. **Include code examples** where applicable
5. **Test links** to ensure they work
6. **Follow markdown conventions** (blank lines, proper headings)
7. **Update commit hash** in metadata headers after significant changes

## Version Information

- **Current Version:** 0.8.0 (Beta)
- **Python:** 3.11+
- **Database:** SQLite 3.35+
- **GUI Framework:** PySide6 (Qt 6)
- **Web Framework:** FastAPI (embedded webserver)
- **Documentation Generator:** Sphinx with Google Style docstrings
- **Production Status:** ✅ Production Ready (see [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md))

## Support

For issues or questions:
- Check relevant documentation sections above
- Review inline code docstrings (Google Style)
- Run tests with `pytest` to verify functionality
- Check [CHANGELOG.md](../CHANGELOG.md) for recent changes
