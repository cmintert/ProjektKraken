# Release Strategy & Policy

## 1. Versioning Strategy
We adhere to **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`).
- **MAJOR**: Incompatible API changes or massive architectural shifts.
- **MINOR**: Backward-compatible functionality additions (e.g., new features).
- **PATCH**: Backward-compatible bug fixes.

**Current Version Ref**:
- `pyproject.toml` (`[project] version`)
- `src/app/constants.py` (`WINDOW_TITLE`)

## 2. Progress & Iteration Handling
Development is iterative and tracked via:
- **`task.md`**: Used for granular tracking of current development sprint/session.
- **Feature Branches**: Large features should use dedicated branches (e.g., `feature/timeline-refactor`).
- **Workflows**: Defined in `.agent/workflows`, ensuring consistent operations.

### The "Unreleased" State
As work progresses, changes are logged in the `[Unreleased]` section of `CHANGELOG.md`. This ensures that the changelog is always up-to-date and ready for a release at any moment.

## 3. Branching Strategy
We use a **Feature Branch** workflow (implied GitHub Flow).
- **`main`**: The stable, production-ready branch. Always buildable.
- **`feature/<name>`**: For developing new features.
  - Merged into `main` via Pull Request (PR).
  - Must pass tests/lints before merge.
  - Deleted after merge.
- **`fix/<name>`**: For bug fixes.
- **`chore/<name>`**: For maintenance tasks (deps, docs, etc.).


## 4. Release Strategy
Releases are **triggered when a cohesive set of features or critical fixes are ready**.
We do not release on a fixed time cadence (e.g., every 2 weeks), but rather on a **feature-complete** basis.

## 5. Release Process Workflow
To perform a release, follow these steps strictly:

### A. Preparation (Working Copy)
1.  **Check Release Status**: Run the helper script to verify versions and git state.
    ```bash
    python scripts/check_release_status.py
    ```
2.  **Verify Tests**: Ensure all tests pass (`pytest`) and linting is clean (`pre-commit run --all-files`).
3.  **Manual Checklist (Optional)**: If you prefer a checklist, copy `docs/RELEASE_CHECKLIST_TEMPLATE.md` to a temporary file.
2.  **Update `CHANGELOG.md`**:
    - Rename `[Unreleased]` section header to `## [X.Y.Z]`.
    - Create a new empty `## [Unreleased]` section above it.
    - Ensure all items have dates and proper categorization.
3.  **Bump Version**:
    - Update `version = "X.Y.Z"` in `pyproject.toml`.
    - Update `WINDOW_TITLE` in `src/app/constants.py`.

### B. Commit & Tag
1.  **Commit**: Create a release commit.
    ```bash
    git add CHANGELOG.md pyproject.toml src/app/constants.py
    git commit -m "chore(release): version X.Y.Z"
    ```
2.  **Tag**: Tag the commit.
    ```bash
    git tag -a vX.Y.Z -m "Release version X.Y.Z"
    ```

### C. Build (Artifacts)
1.  **Generate Executable**: Use the build workflow.
    ```bash
    # Run the user-defined workflow
    # Trigger /build-app if available, or run manually:
    pyinstaller ProjektKraken.spec --clean --noconfirm
    ```
2.  **Verify**: Test the generated executable in `dist/` to ensure it launches.

### D. Publish
- **Git Push**: `git push origin main --tags`
- (Optional) Upload the executable to GitHub Releases.
