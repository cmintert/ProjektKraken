# Release Checklist

**Target Version**: `[X.Y.Z]`
**Date**: `[YYYY-MM-DD]`

## 1. Preparation
- [ ] **Run Status Check**:
    ```bash
    python scripts/check_release_status.py
    ```
    *Ensure "Project Kraken Release Status Checker" reports no errors.*
- [ ] **Update Tests**: Ensure all new features are tested.
- [ ] **Run Full Test Suite**:
    ```bash
    pytest
    ```
- [ ] **Check Linting**:
    ```bash
    pre-commit run --all-files
    ```

## 2. Documentation & Versioning
- [ ] **Update `CHANGELOG.md`**:
    - [ ] Rename `[Unreleased]` to `[X.Y.Z]`.
    - [ ] Add new `[Unreleased]` section at top.
    - [ ] Ensure all entries have dates.
- [ ] **Bump Version**:
    - [ ] Edit `pyproject.toml` -> `version = "X.Y.Z"`
    - [ ] Edit `src/app/constants.py` -> `WINDOW_TITLE = "... vX.Y.Z ..."`
- [ ] **Commit**:
    ```bash
    git add CHANGELOG.md pyproject.toml src/app/constants.py
    git commit -m "chore(release): vX.Y.Z"
    ```

## 3. Tag & Build
- [ ] **Tag**:
    ```bash
    git tag -a vX.Y.Z -m "Release vX.Y.Z"
    ```
- [ ] **Verify Tag**:
    ```bash
    python scripts/check_release_status.py
    ```
    *Should now say "✅ Released (Sitting on a release)"*

- [ ] **Build Executable**:
    ```bash
    /build-app
    # OR
    pyinstaller ProjektKraken.spec --clean --noconfirm
    ```
- [ ] **Test Executable**:
    - Run `dist/ProjektKraken/ProjektKraken.exe`.
    - Verify Help > About (if exists) shows correct version.

## 4. Publish
- [ ] **Push**:
    ```bash
    git push origin main --tags
    ```
