# Contributing Guide

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Guide for contributing to ProjektKraken.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Code of Conduct](#code-of-conduct)
3. [How to Contribute](#how-to-contribute)
4. [Development Process](#development-process)
5. [Pull Request Process](#pull-request-process)
6. [Coding Standards](#coding-standards)
7. [Testing Requirements](#testing-requirements)
8. [Documentation](#documentation)
9. [Community](#community)

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.13+** installed
- **Git** for version control
- **GitHub account** for pull requests
- Read the [Development Guide](DEVELOPMENT.md)
- Familiarity with PySide6/Qt (for GUI contributions)

### Setting Up Development Environment

1. **Fork the Repository**

   Click "Fork" on [GitHub](https://github.com/cmintert/ProjektKraken)

2. **Clone Your Fork**

   ```bash
   git clone https://github.com/YOUR_USERNAME/ProjektKraken.git
   cd ProjektKraken
   ```

3. **Add Upstream Remote**

   ```bash
   git remote add upstream https://github.com/cmintert/ProjektKraken.git
   ```

4. **Install Dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. **Verify Setup**

   ```bash
   pytest
   python -m src.app.main
   ```

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:

- Experience level
- Gender identity
- Sexual orientation
- Disability
- Personal appearance
- Body size
- Race
- Ethnicity
- Age
- Religion

### Expected Behavior

- **Be respectful** and considerate
- **Be constructive** in feedback
- **Be collaborative** and help others
- **Focus on what's best** for the project
- **Show empathy** towards other contributors

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Public or private harassment
- Publishing others' private information

### Enforcement

Violations may result in:

1. Warning from maintainers
2. Temporary ban from project
3. Permanent ban from project

Report violations to: [project maintainer email]

---

## How to Contribute

### Ways to Contribute

You can contribute in many ways:

#### 1. Report Bugs

Found a bug? Please report it!

**Before Reporting:**
- Check [existing issues](https://github.com/cmintert/ProjektKraken/issues)
- Verify it's reproducible
- Test on latest version

**What to Include:**
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version)
- Screenshots (for UI bugs)
- Error messages/stack traces

**Template:**

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g. Windows 10]
- Python version: [e.g. 3.13.1]
- ProjektKraken version: [e.g. 0.11.0]
```

---

#### 2. Suggest Features

Have an idea? We'd love to hear it!

**Before Suggesting:**
- Check [existing feature requests](https://github.com/cmintert/ProjektKraken/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)
- Consider if it fits project scope
- Think about implementation

**What to Include:**
- Clear description of the feature
- Use cases and benefits
- Possible implementation approach
- Alternative solutions considered

---

#### 3. Improve Documentation

Documentation is always welcome!

**Areas to Help:**
- Fix typos and grammar
- Clarify confusing sections
- Add examples and tutorials
- Translate to other languages
- Update outdated information

---

#### 4. Write Code

Ready to code? Great!

**Good First Issues:**

Look for issues labeled:
- `good-first-issue` - Great for beginners
- `help-wanted` - Community contributions welcome
- `documentation` - Documentation improvements

**Before Starting:**
- Comment on the issue to claim it
- Discuss approach with maintainers
- Create a feature branch

---

## Development Process

### Workflow

1. **Create Feature Branch**

   ```bash
   git checkout -b feature/my-feature
   # or
   git checkout -b fix/bug-description
   ```

   **Branch Naming:**
   - `feature/` - New features
   - `fix/` - Bug fixes
   - `docs/` - Documentation changes
   - `refactor/` - Code refactoring
   - `test/` - Test additions/changes

2. **Make Changes**

   - Write code following [coding standards](#coding-standards)
   - Write/update tests
   - Update documentation

3. **Test Locally**

   ```bash
   # Run linter
   ruff check src/
   
   # Run tests
   pytest
   
   # Check coverage
   pytest --cov=src --cov-report=term-missing
   ```

4. **Commit Changes**

   ```bash
   git add .
   git commit -m "feat: Add new feature"
   ```

   **Commit Message Format:**

   ```
   <type>: <short description>
   
   <optional detailed description>
   
   <optional footer>
   ```

   **Types:**
   - `feat` - New feature
   - `fix` - Bug fix
   - `docs` - Documentation only
   - `style` - Code style (formatting, no logic change)
   - `refactor` - Code refactoring
   - `test` - Adding/updating tests
   - `chore` - Maintenance tasks

   **Examples:**

   ```
   feat: Add semantic search support
   
   Implement semantic search using LM Studio embeddings.
   Includes vector storage and similarity search.
   
   Closes #123
   ```

   ```
   fix: Resolve database lock on world close
   
   Ensure all connections are properly closed before
   shutdown to prevent lock errors.
   
   Fixes #456
   ```

5. **Keep Branch Updated**

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

6. **Push to Your Fork**

   ```bash
   git push origin feature/my-feature
   ```

---

## Pull Request Process

### Before Submitting

**Checklist:**

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass locally
- [ ] No linter errors
- [ ] Branch is up to date with main

### Creating Pull Request

1. **Go to GitHub**

   Navigate to your fork on GitHub

2. **Click "New Pull Request"**

   Select your feature branch

3. **Fill Out Template**

   ```markdown
   ## Description
   Brief description of changes.
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Refactoring
   
   ## Changes Made
   - List key changes
   - One change per line
   
   ## Testing
   Describe how you tested the changes.
   
   ## Screenshots
   If UI changes, add screenshots.
   
   ## Checklist
   - [ ] Tests pass
   - [ ] Documentation updated
   - [ ] No linter errors
   
   ## Related Issues
   Closes #123
   ```

4. **Submit Pull Request**

   Click "Create pull request"

### Review Process

**What Happens Next:**

1. **Automated Checks**
   - CI runs tests
   - Linter checks code style
   - Coverage measured

2. **Code Review**
   - Maintainer reviews code
   - May request changes
   - Discuss feedback constructively

3. **Address Feedback**
   - Make requested changes
   - Push updates to same branch
   - Respond to comments

4. **Approval and Merge**
   - Once approved, maintainer merges
   - Branch can be deleted

### Review Timeline

- **Initial Response**: Within 48 hours
- **Full Review**: Within 1 week
- **Merge**: After approval and passing checks

---

## Coding Standards

### Python Style

Follow [PEP 8](https://pep8.org/) with modifications:

- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes
- **Imports**: Ordered (stdlib → third-party → local)

### Type Hints

**Required** for all public functions:

```python
def create_event(name: str, lore_date: float) -> Event:
    """Create event with given parameters."""
    pass
```

### Docstrings

**Google Style** required:

```python
def update_entity(entity_id: str, **kwargs: Any) -> Entity:
    """
    Update entity with new properties.
    
    Args:
        entity_id: Unique identifier of entity.
        **kwargs: Properties to update.
    
    Returns:
        Entity: Updated entity object.
    
    Raises:
        ValueError: If entity_id is invalid.
    """
    pass
```

### Code Quality Tools

**Run before committing:**

```bash
# Format code
ruff format src/

# Check style
ruff check src/

# Type checking
mypy src/

# Run tests
pytest
```

---

## Testing Requirements

### Test Coverage

**Minimum Requirements:**

| Component | Coverage |
|-----------|----------|
| Core Logic | 100% |
| Commands | 100% |
| Repositories | 95% |
| Services | 95% |
| Overall | 95% |

### Writing Tests

**Every contribution must include tests:**

```python
def test_my_feature():
    """Test my new feature."""
    # Arrange
    setup_data()
    
    # Act
    result = my_feature()
    
    # Assert
    assert result == expected
```

**Test Naming:**

```
test_<method>_<scenario>_<expected_result>
```

**Examples:**

```python
def test_create_event_with_valid_data_returns_event():
    """Test event creation with valid input."""
    pass

def test_create_event_with_invalid_date_raises_error():
    """Test event creation with invalid date."""
    pass
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/unit/test_events.py

# With coverage
pytest --cov=src --cov-report=term-missing
```

---

## Documentation

### When to Update Documentation

Update documentation when:

- Adding new features
- Changing existing behavior
- Fixing bugs that affect usage
- Adding new APIs

### Documentation Types

1. **Code Documentation**
   - Docstrings for classes/functions
   - Inline comments for complex logic

2. **User Documentation**
   - User Guide updates
   - Workflow examples
   - FAQ entries

3. **Technical Documentation**
   - Architecture changes
   - API Reference updates
   - Development guide changes

### Documentation Style

- **Clear and concise**
- **Use examples**
- **Update related docs**
- **Check for broken links**

---

## Community

### Getting Help

- **Documentation**: Start with [docs/INDEX.md](INDEX.md)
- **GitHub Discussions**: Ask questions
- **GitHub Issues**: Report bugs
- **Discord**: Join community server (link in README)

### Staying Updated

- **Watch Repository**: Get notified of updates
- **Read Changelog**: See what's new
- **Follow Releases**: Keep up with versions

### Recognition

Contributors are recognized in:

- **Contributors list** in README
- **Release notes** for significant contributions
- **Hall of Fame** for major contributors

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (GPL-3.0).

---

## Questions?

Still have questions? Reach out:

- **GitHub Discussions**: [Link to discussions]
- **Email**: [Maintainer email]
- **Discord**: [Server invite]

Thank you for contributing to ProjektKraken! 🎉

---

**Navigation:**  
[← API Reference](API_REFERENCE.md) • [Back to Index](INDEX.md) • [Development Guide](DEVELOPMENT.md)
