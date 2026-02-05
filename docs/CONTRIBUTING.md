# Contributing to ProjektKraken

Welcome to the ProjektKraken project! This guide will help you contribute effectively to this timeline-first worldbuilding application.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment](#development-environment)
3. [Finding Work](#finding-work)
4. [Code Standards](#code-standards)
5. [Submission Process](#submission-process)
6. [Review Expectations](#review-expectations)
7. [Community Guidelines](#community-guidelines)

---

## Getting Started

### First Steps

Before making changes:

1. **Explore the codebase** - Run the application, create events, build a timeline
2. **Read the documentation** - Familiarize yourself with:
   - [ARCHITECTURE.md](ARCHITECTURE.md) - Understanding the layered design
   - [DEVELOPMENT.md](DEVELOPMENT.md) - Setup and coding practices
   - [DATABASE.md](DATABASE.md) - Schema and data patterns
3. **Run the test suite** - Ensure everything passes on your machine
4. **Join discussions** - Introduce yourself in GitHub Discussions

### Understanding the Vision

ProjektKraken is designed for the "Architect" persona who thinks about worlds through their history. Key design principles:

- **Timeline-first workflow** - History is the primary organizing axis
- **Flexibility over rigidity** - Hybrid schema allows customization
- **Context-aware UI** - Trinity view (Editor, Timeline, Relations)
- **Command pattern** - Full undo/redo for all user actions

---

## Development Environment

### Setup Instructions

Complete setup steps are in [DEVELOPMENT.md](DEVELOPMENT.md), but here's the quick version:

```bash
git clone <repository-url>
cd ProjektKraken
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python launcher.py
```

### Verification Checklist

After setup, verify your environment:

- [ ] Application launches without errors
- [ ] Can create/edit events and entities
- [ ] Timeline displays correctly
- [ ] Tests pass: `pytest`
- [ ] Linter passes: `ruff check src/`
- [ ] Type checker passes: `mypy src/`

---

## Finding Work

### Issue Labels

Issues are organized by labels:

| Label | Description | Skill Level |
|-------|-------------|-------------|
| `good-first-issue` | Newcomer-friendly tasks | Beginner |
| `help-wanted` | Community contributions welcome | Intermediate |
| `bug` | Something isn't working | Any |
| `enhancement` | New feature requests | Intermediate+ |
| `documentation` | Docs improvements | Any |
| `testing` | Test coverage improvements | Intermediate |
| `performance` | Speed/memory optimization | Advanced |

### Suggested Starting Points

**For beginners:**
- Documentation improvements (typos, clarity, examples)
- Writing additional tests for existing features
- Small UI enhancements (tooltips, labels)

**For intermediate developers:**
- Implementing new command types
- Adding new widget functionality
- Database query optimization
- Import/export format support

**For advanced developers:**
- Architecture refactoring
- Performance optimization
- New major features (map system, graph visualization)
- Threading and concurrency improvements

### Self-Directed Contributions

Have an idea not listed in issues? Great! Please:

1. **Check existing issues and PRs** - Avoid duplicate work
2. **Open a discussion** - Share your idea for feedback
3. **Start small** - Prototype before full implementation
4. **Get consensus** - Major changes need maintainer approval

---

## Code Standards

### Architecture Requirements

ProjektKraken uses strict layered architecture. **Your changes must respect these boundaries:**

**Layer Dependency Rules:**
```
App Layer → Commands → Services → Core
GUI Layer → Core (types only, no business logic)
```

**Anti-patterns to avoid:**
- ❌ Business logic in GUI widgets
- ❌ Direct SQL in commands or GUI
- ❌ Qt imports in core modules
- ❌ Bypassing command pattern for state changes

**Correct patterns:**
- ✅ GUI emits signals → App layer handles → Executes command
- ✅ All database access through repositories
- ✅ Pure functions in core utilities
- ✅ Commands are reversible with undo()

### Python Coding Standards

**Mandatory practices:**

```python
# Type hints required
def process_timeline(events: list[Event], start: float) -> list[Event]:
    """Process events within timeline range.
    
    Args:
        events: List of Event objects to filter.
        start: Starting lore date for filtering.
    
    Returns:
        Filtered list of events after start date.
    """
    return [e for e in events if e.lore_date >= start]

# Google-style docstrings required for public APIs
# Use logging instead of print
import logging
logger = logging.getLogger(__name__)

# Dataclasses for data models
from dataclasses import dataclass, field

@dataclass
class MyModel:
    required_field: str
    optional_field: str = ""
    json_field: dict = field(default_factory=dict)
```

**Formatting:**
- Line length: 88 characters maximum
- Use Ruff for formatting: `ruff format src/`
- No trailing whitespace
- Unix line endings (LF)

### Testing Requirements

**Coverage targets:**
- Core modules: 100% required
- Services: 95% required  
- Commands: 95% required
- GUI widgets: 80% minimum

**Test structure:**

```python
def test_specific_behavior_under_conditions():
    """Test that X does Y when Z."""
    # Arrange - setup test data
    event = Event(name="Test", lore_date=100.0)
    
    # Act - perform operation
    result = process_event(event)
    
    # Assert - verify outcome
    assert result is not None
    assert result.processed is True
```

Run tests before submitting:

```bash
pytest --cov=src --cov-report=term-missing
```

### Documentation Requirements

**When to update docs:**
- New features → Update USER_GUIDE.md
- New APIs → Update API.md
- Architecture changes → Update ARCHITECTURE.md
- Schema changes → Update DATABASE.md

**Docstring checklist:**
- [ ] Brief one-line summary
- [ ] Args section with types
- [ ] Returns section with type
- [ ] Raises section (if applicable)
- [ ] Example usage (for complex functions)

---

## Submission Process

### Branch Strategy

Create feature branches from `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/descriptive-name
```

**Branch naming:**
- `feature/timeline-grouping` - New functionality
- `fix/event-date-validation` - Bug repairs
- `docs/api-examples` - Documentation work
- `refactor/repository-pattern` - Code reorganization
- `test/entity-editor-coverage` - Test additions

### Commit Guidelines

**Commit message structure:**

```
type: Brief description (50 chars max)

Optional detailed explanation of what changed and why.
Reference any related issues.

Fixes #123
```

**Types:**
- `feat:` - New feature implementation
- `fix:` - Bug correction
- `docs:` - Documentation changes only
- `test:` - Test additions or modifications
- `refactor:` - Code restructuring without behavior change
- `style:` - Formatting, whitespace changes
- `perf:` - Performance improvements
- `chore:` - Build scripts, dependencies

**Examples:**

```
feat: Add timeline event grouping by entity type

Implements TimelineGroupingCommand for organizing events by
the entities involved. Includes UI controls in timeline widget.

Related to #234
```

```
fix: Prevent duplicate wiki links in entity descriptions

The link parser was not deduplicating entity references,
causing multiple clickable regions for the same entity.

Fixes #156
```

### Pull Request Process

1. **Ensure quality checks pass:**

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check --fix src/ tests/

# Type checking
mypy src/

# Run tests
pytest --cov=src

# Verify docstrings
python scripts/check_docstrings.py
```

2. **Push your branch:**

```bash
git push origin feature/your-feature
```

3. **Open Pull Request on GitHub:**
   - Use descriptive title matching commit format
   - Fill out PR template completely
   - Link related issues
   - Add screenshots for UI changes
   - Mark as draft if work-in-progress

4. **PR Template Checklist:**

```markdown
## Description
Brief explanation of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Tests added/updated
- [ ] All tests pass locally
- [ ] Manual testing completed

## Documentation
- [ ] Docstrings updated
- [ ] User docs updated (if needed)
- [ ] CHANGELOG.md updated

## Screenshots (if UI change)
[Attach images]

## Related Issues
Fixes #123
```

---

## Review Expectations

### What Reviewers Check

Reviewers will evaluate:

**Functionality:**
- Does it work as intended?
- Are edge cases handled?
- Is error handling robust?

**Architecture:**
- Follows layer boundaries?
- Uses command pattern correctly?
- Respects separation of concerns?

**Code Quality:**
- Type hints present?
- Docstrings complete?
- Follows style guide?
- No code smells?

**Testing:**
- Adequate test coverage?
- Tests are meaningful?
- Edge cases tested?

**Documentation:**
- User-facing changes documented?
- API changes reflected in docs?
- Examples provided?

### Response Timeline

- **Initial review:** Within 3-5 business days
- **Follow-up reviews:** Within 2 business days after updates
- **Merging:** After approval from 1+ maintainers

### Handling Feedback

When you receive review comments:

1. **Acknowledge feedback** - Reply to comments
2. **Ask questions** - If something is unclear
3. **Make requested changes** - Push updates to same branch
4. **Mark resolved** - When you've addressed comments
5. **Be patient** - Iterations are normal

**Example response:**

> Reviewer: "This function should validate inputs."
> 
> You: "Good catch! I've added validation and a test case. See commit abc123."

---

## Community Guidelines

### Code of Conduct Highlights

We expect contributors to:

- **Be respectful** - Value diverse perspectives
- **Be constructive** - Criticism should be helpful
- **Be collaborative** - We're building together
- **Be patient** - Everyone is learning

**Not acceptable:**
- Harassment or discrimination
- Aggressive or inflammatory language
- Off-topic discussions in issues
- Spamming or trolling

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - Questions, ideas, showcase
- **Pull Requests** - Code reviews, technical discussion

### Getting Help

Stuck on something? Here's how to get unblocked:

1. **Check documentation** - Likely already answered
2. **Search existing issues** - Someone may have asked before
3. **Ask in Discussions** - Community can help
4. **Be specific** - Include error messages, code snippets, steps to reproduce

**Good question format:**

```
I'm trying to implement feature X. I've read [docs] and tried [approach].

Expected: [what should happen]
Actual: [what actually happens]

Error message:
```
[paste error]
```

Related code:
```python
[minimal example]
```

What am I missing?
```

### Recognition

Contributors are recognized through:

- **GitHub contributor graphs**
- **CHANGELOG.md mentions** - For notable contributions
- **Documentation credits** - For significant docs work
- **Maintainer consideration** - For sustained quality contributions

---

## Special Contribution Areas

### Documentation Contributions

Documentation is always welcome! No coding required:

- Fix typos and grammatical errors
- Clarify confusing sections
- Add usage examples
- Create tutorial content
- Improve API documentation

### Translation Contributions

While not yet implemented, we plan to support internationalization. If you're interested in translation work, let us know!

### Design Contributions

Have UI/UX expertise? We welcome:

- Icon design improvements
- Color scheme refinements
- Layout optimization suggestions
- Accessibility enhancements

### Testing Contributions

Help improve reliability:

- Write tests for untested code
- Add integration test scenarios
- Create performance benchmarks
- Test on different platforms

---

## Release Process

### Version Numbering

ProjektKraken uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR:** Breaking changes (rare)
- **MINOR:** New features (backward compatible)
- **PATCH:** Bug fixes only

### Release Cycle

- **Minor releases:** Every 4-6 weeks
- **Patch releases:** As needed for critical bugs
- **Major releases:** When significant breaking changes accumulate

### Changelog Maintenance

Contributors should update CHANGELOG.md:

```markdown
## [Unreleased]

### Added
- Timeline grouping by entity type (#234)

### Fixed
- Duplicate wiki links in descriptions (#156)

### Changed
- Improved event search performance
```

---

## Advanced Topics

### Working on Large Features

For substantial features:

1. **Create RFC (Request for Comments)** - Propose design in discussion
2. **Get feedback** - Iterate on design before coding
3. **Break into phases** - Submit incremental PRs
4. **Update architecture docs** - Document design decisions

### Performance Optimization

When optimizing:

- **Measure first** - Use profiling tools
- **Document baselines** - Before/after metrics
- **Maintain correctness** - Don't sacrifice for speed
- **Add benchmarks** - Prevent regressions

### Database Migrations

Schema changes require:

- Migration script in `scripts/migrate_data.py`
- Schema version bump
- Backward compatibility test
- Documentation update in DATABASE.md

---

## Questions?

- **General questions:** GitHub Discussions
- **Bug reports:** GitHub Issues
- **Security issues:** Email maintainers directly (see SECURITY.md)
- **Feature proposals:** GitHub Discussions first, then issue

Thank you for contributing to ProjektKraken! Your work helps worldbuilders create richer, more coherent fictional universes.
