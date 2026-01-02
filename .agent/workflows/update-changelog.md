---
description: Update CHANGELOG.md with recent commits
---

# Update Changelog Workflow

## Steps

1. Get recent commits with dates:
   ```
   git log --format="%h %ad %s" --date=short -15
   ```

2. View current CHANGELOG.md to understand structure:
   ```
   view_file CHANGELOG.md
   ```

3. Add new entries under `## [Unreleased]` following this format:
   - Group by category: `### Added`, `### Fixed`, `### Changed`, `### Deprecated`
   - Each entry should have a date prefix: `*(YYYY-MM-DD)*`
   - Format: `- *(date)* **Category**: Description.`
   - Categories: CLI, Architecture, Testing, Stability, Bug, Refactor, Cleanup

4. Update the header metadata:
   - `**Last Updated:**` - Set to current date
   - `**Commit:**` - Set to latest commit hash

5. Keep entries concise - trim verbose descriptions

## Example Entry

```markdown
- *(2026-01-02)* **Refactor**: Extracted `MapHandler` from MainWindow (~226 lines).
- *(2026-01-02)* **Bug**: Fixed map markers not appearing immediately after creation.
```

## Notes
- Only add entries for user-visible changes, not internal refactoring unless significant
- Group related commits into single entries where appropriate
- Use past tense for descriptions
