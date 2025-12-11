# Security Best Practices

## Overview

This document outlines security best practices for ProjektKraken development to ensure the application is secure, maintains data integrity, and protects against common vulnerabilities.

## SQL Injection Prevention

### Parameterized Queries (REQUIRED)

**Always** use parameterized queries with placeholder (`?`) syntax:

✅ **Correct Examples:**
```python
# Single parameter
cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))

# Multiple parameters
cursor.execute(
    "INSERT INTO events (id, name, lore_date) VALUES (?, ?, ?)",
    (event.id, event.name, event.lore_date)
)

# Using named placeholders (SQLite also supports :name syntax)
cursor.execute(
    "SELECT * FROM events WHERE name = :name AND type = :type",
    {"name": event_name, "type": event_type}
)
```

❌ **NEVER Do This (SQL Injection Vulnerable):**
```python
# f-strings - VULNERABLE
cursor.execute(f"SELECT * FROM events WHERE id = '{event_id}'")

# String concatenation - VULNERABLE
cursor.execute("SELECT * FROM events WHERE id = '" + event_id + "'")

# .format() - VULNERABLE
cursor.execute("SELECT * FROM events WHERE id = '{}'".format(event_id))

# % formatting - VULNERABLE
cursor.execute("SELECT * FROM events WHERE id = '%s'" % event_id)
```

### Why This Matters

An attacker could inject malicious SQL:
```python
# If using f-strings or concatenation:
event_id = "1' OR '1'='1"  # Returns all events!
event_id = "1'; DROP TABLE events; --"  # Deletes the table!
```

With parameterized queries, SQLite treats the entire input as data, not code.

### Code Review Checklist

Before committing any database code:
- ✅ All SQL queries use `?` placeholders
- ✅ No f-strings in SQL statements
- ✅ No `.format()` in SQL statements
- ✅ No string concatenation with user input
- ✅ Parameters passed as tuple or dict

## Input Validation

### Validate Before Database

Always validate user input before database operations:

```python
def create_event(name: str, lore_date: float) -> CommandResult:
    """Create event with validation."""
    # Validate name
    if not name or not name.strip():
        return CommandResult(
            success=False,
            message="Event name cannot be empty",
            command_name="CreateEventCommand"
        )
    
    # Validate date
    if not isinstance(lore_date, (int, float)):
        return CommandResult(
            success=False,
            message="Invalid date format",
            command_name="CreateEventCommand"
        )
    
    # Sanitize HTML in descriptions if needed
    description = html.escape(description) if description else ""
    
    # Now safe to insert
    event = Event(name=name.strip(), lore_date=lore_date, description=description)
    db_service.insert_event(event)
    return CommandResult(success=True, ...)
```

### Type Safety

Use Python type hints to catch type errors early:

```python
def insert_event(self, event: Event) -> None:
    """Type hint ensures only Event objects accepted."""
    # ... implementation ...

def get_event(self, event_id: str) -> Optional[Event]:
    """Type hint documents expected return type."""
    # ... implementation ...
```

## Data Sanitization

### HTML/XSS Prevention

When displaying user content in the UI:

```python
import html

# Before displaying in HTML context
safe_text = html.escape(user_input)

# For wiki links - already implemented safely
pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")
safe_text = html.escape(text)  # Escape first
html_content = pattern.sub(replace_link, safe_text)  # Then process
```

### JSON Serialization

When storing JSON attributes:

```python
import json

# Safe serialization
attributes_json = json.dumps(event.attributes)

# Safe deserialization
attributes = json.loads(attributes_json)
```

**Never** use `eval()` or `exec()` on user data!

## Secrets Management

### Environment Variables

For any sensitive configuration (if added in future):

```python
import os
from pathlib import Path

# Use environment variables
API_KEY = os.getenv("KRAKEN_API_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Or .env file (not committed to git)
from dotenv import load_dotenv
load_dotenv()
```

### .gitignore

Ensure sensitive files are excluded:

```gitignore
# Already in .gitignore:
.env
.env.local
.env.*.local
*.pem
*.key
secrets/
credentials/

# Database files (may contain sensitive user data)
*.db
*.kraken
world.kraken
```

### Never Commit

❌ **Never commit these to git:**
- API keys or passwords
- Database files with real user data
- Private keys or certificates
- `.env` files
- Personal data

## File Security

### Database File Permissions

On production deployment (if applicable):

```python
import os
import stat

# Set restrictive permissions on database file
db_path = "world.kraken"
os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 - owner only
```

### Path Traversal Prevention

If implementing file operations:

```python
from pathlib import Path

def safe_file_access(user_path: str, base_dir: str) -> bool:
    """Prevent directory traversal attacks."""
    try:
        requested = Path(base_dir) / user_path
        requested = requested.resolve()
        
        # Ensure it's within base_dir
        if not str(requested).startswith(str(Path(base_dir).resolve())):
            return False
        
        return True
    except Exception:
        return False
```

## Logging Security

### Sensitive Data in Logs

❌ **Never log:**
- Passwords or tokens
- Full credit card numbers
- Personal identification numbers
- Session tokens

✅ **Safe logging:**
```python
# Mask sensitive data
logger.info(f"User login: {username} (ID: {user_id[:8]}...)")

# Log events without sensitive fields
logger.info(f"Event created: {event.name} at {event.lore_date}")

# Don't log entire objects that might contain secrets
# BAD: logger.debug(f"Config: {config}")
# GOOD: logger.debug(f"Config loaded with {len(config)} items")
```

## Dependency Security

### Requirements Management

Keep dependencies up to date:

```bash
# Check for known vulnerabilities
pip install safety
safety check

# Update dependencies regularly
pip list --outdated
```

### Minimal Dependencies

Only add dependencies that are:
1. Well-maintained
2. Widely used
3. Security-audited
4. Actually needed

Current dependencies are minimal and well-established:
- PySide6 (Qt framework)
- pytest (testing)
- Standard library modules

## Error Handling

### Avoid Information Disclosure

❌ **Bad - Exposes internals:**
```python
try:
    db_service.insert_event(event)
except Exception as e:
    # Shows full stack trace to user
    QMessageBox.critical(self, "Error", str(e))
```

✅ **Good - User-friendly messages:**
```python
try:
    db_service.insert_event(event)
except sqlite3.IntegrityError:
    QMessageBox.warning(self, "Error", "Event already exists")
except sqlite3.Error:
    logger.error(f"Database error", exc_info=True)  # Full error in logs
    QMessageBox.critical(self, "Error", "Failed to save event. Please try again.")
```

### Graceful Degradation

Handle errors gracefully:

```python
def load_events(self) -> List[Event]:
    """Load events with fallback on error."""
    try:
        return db_service.get_all_events()
    except sqlite3.Error as e:
        logger.error(f"Failed to load events: {e}")
        # Return empty list instead of crashing
        return []
```

## Testing for Security

### Security Test Cases

Include security-focused tests:

```python
def test_sql_injection_prevention(db_service):
    """Test that SQL injection attempts are neutralized."""
    malicious_name = "Event'; DROP TABLE events; --"
    event = Event(name=malicious_name, lore_date=1.0)
    
    db_service.insert_event(event)
    
    # Event should be inserted safely
    retrieved = db_service.get_event(event.id)
    assert retrieved.name == malicious_name
    
    # events table should still exist
    all_events = db_service.get_all_events()
    assert len(all_events) == 1

def test_xss_prevention_in_wiki_links():
    """Test that HTML is escaped in wiki link display."""
    malicious_text = "<script>alert('XSS')</script>"
    
    widget = WikiTextEdit()
    widget.set_wiki_text(malicious_text)
    
    html = widget.toHtml()
    # Script tags should be escaped
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
```

## Security Checklist

Before each release:

- [ ] All SQL queries use parameterized statements
- [ ] No sensitive data in logs
- [ ] No secrets in code or git
- [ ] Input validation on all user inputs
- [ ] HTML escaping in UI displays
- [ ] Dependencies updated
- [ ] Security tests passing
- [ ] Error messages don't leak internals
- [ ] .gitignore includes sensitive files
- [ ] File permissions appropriate

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** create a public GitHub issue
2. Email the maintainer privately
3. Provide details of the vulnerability
4. Allow time for a fix before public disclosure

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQLite Security](https://www.sqlite.org/security.html)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [PEP 20 - The Zen of Python](https://www.python.org/dev/peps/pep-0020/) - "Explicit is better than implicit"

## Summary

**Core Principles:**

1. **Parameterize Everything**: Never interpolate strings into SQL
2. **Validate Input**: Check all user input before processing
3. **Escape Output**: HTML-escape data displayed in UI
4. **Keep Secrets Secret**: Use environment variables, never commit
5. **Log Safely**: Don't log sensitive data
6. **Fail Gracefully**: Handle errors without exposing internals
7. **Test Security**: Include security-focused test cases
8. **Stay Updated**: Keep dependencies current

Following these practices ensures ProjektKraken remains secure and trustworthy.
