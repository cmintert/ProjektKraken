---
description: Bump the project version and update all associated files (pyproject.toml, constants, README, Design, CHANGELOG)
---

# Version Bump Workflow

Follow these steps to safely bump the project version across all relevant files.

## Steps

1. **Verify Pre-Release Status**:
   Run the release status checker to ensure the working copy is clean and ready.
   ```bash
   python scripts/check_release_status.py
   ```

2. **Update Core Version**:
   - **`pyproject.toml`**: Update `version = "X.Y.Z"`.
   - **`src/app/constants.py`**: Update `WINDOW_TITLE = "Project Kraken - vX.Y.Z (Beta)"`.

3. **Update Project Documentation**:
   - **`README.md`**: Update header metadata `commit: X.Y.Z` and the version footer section.
   - **`Design.md`**: Update `Version: X.Y.Z` in the header section.

4. **Finalize Changelog**:
   Edit `CHANGELOG.md`:
   - Rename `## [Unreleased]` to `## [X.Y.Z]`.
   - Add a new empty `## [Unreleased]` section at the top.
   - Update header metadata: Set `**Last Updated:**` to today and `**Commit:**` to `X.Y.Z`.

5. **Verify Post-Release Status**:
   Run the checker again to confirm all versions match.
   ```bash
   python scripts/check_release_status.py
   ```

6. **Build Executable (Final Step)**:
   Generate the standalone executable for the new version.
   ```bash
   pyinstaller ProjektKraken.spec --noconfirm
   ```

## Summary Checklist
- [ ] `pyproject.toml`
- [ ] `src/app/constants.py`
- [ ] `README.md`
- [ ] `Design.md`
- [ ] `CHANGELOG.md`
- [ ] PyInstaller Build
