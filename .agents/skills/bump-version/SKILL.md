---
name: bump-version
description: Bump and release ProjektKraken versions safely across application metadata, README labels, and CHANGELOG.md; build the executable; prepare the release commit; and optionally create the matching Git tag. Use when the user asks to bump, release, or tag a ProjektKraken semantic version such as 0.18.8.
---

# Bump Version

Prepare one coherent ProjektKraken release commit without disturbing unrelated
work. Treat version edits, changelog rollover, build verification, commit, and
tagging as one ordered workflow.

## 1. Inspect and validate

1. Read the repository instructions and inspect git status, staged and
   unstaged diffs, recent release commits, and existing tags.
2. Validate the requested version as MAJOR.MINOR.PATCH. Stop for confirmation
   if it is equal to or lower than the current version.
3. Confirm that neither the plain release tag, a conflicting v-prefixed tag,
   nor the requested beta tag exists. ProjektKraken uses lightweight plain
   release tags such as `0.18.8` and beta package tags such as `0.19.5-beta1`.
4. Preserve unrelated user changes. Start from a clean tree unless the user has
   explicitly included existing changes in the release.
5. Run python scripts/check_release_status.py. On Windows, set PYTHONUTF8=1 if
   the console cannot encode the status emoji.

## 2. Update release surfaces

Update the current authoritative files:

- pyproject.toml: set the project version.
- src/core/version.py: set VERSION; leave the derived WINDOW_TITLE expression
  in src/app/constants.py intact.
- README.md: update both bold vX.Y.Z Beta labels.
- CHANGELOG.md: roll the current unreleased changes into the new release.

Do not recreate or edit Design.md; it no longer exists. Do not add invented
README frontmatter fields. Search for the old version outside archived material
and inspect scripts/check_release_status.py in case the authoritative surface
changes later.

For CHANGELOG.md:

1. Record today's date in Last Updated.
2. Record the current pre-commit short HEAD hash in Commit.
3. Keep a fresh Unreleased section at the top.
4. Add a dated Changed release entry under the fresh Unreleased section:

   ~~~markdown
   - *(YYYY-MM-DD)* **Release**: Bumped project and application metadata to
     version X.Y.Z.
   ~~~

5. Place the new X.Y.Z release heading immediately before the previous
   Unreleased content. This preserves every accumulated entry in the released
   section and matches prior ProjektKraken release commits.

## 3. Verify and build

1. Run git diff --check and inspect the complete release diff.
2. Rerun scripts/check_release_status.py. Before the commit, version and
   changelog checks must pass; Dirty (Uncommitted changes) is expected.
3. Run the project quality gates and the focused version test:

   ~~~powershell
   $env:QT_QPA_PLATFORM = "offscreen"
   python -m ruff check src/ tests/
   python -m mypy src/
   python -m pytest -m ci_fast -q
   python -m pytest tests/gui/dialogs/test_about_dialog.py -q
   ~~~

4. Build the executable as the final pre-commit verification. On Windows,
   prefer the project environment directly:

   ~~~powershell
   .venv/Scripts/pyinstaller.exe ProjektKraken.spec --noconfirm
   ~~~

   Allow several minutes. Never start a second build merely because the command
   wrapper timed out; first inspect whether the original PyInstaller process is
   still running. Treat missing optional hidden imports as warnings only when
   PyInstaller exits successfully and reports Build complete.

## 4. Commit and tag

1. Stage only the approved release files. Reinspect the staged diff and run
   git diff --staged --check.
2. Draft this conventional commit message:

   ~~~text
   chore(release): bump version to X.Y.Z
   ~~~

3. Present the exact message and staged scope for confirmation. Do not commit
   until the user approves, even if they requested the bump and tag earlier.
4. Follow the project commit skill: write the approved message to a temporary
   file outside the repository and commit with git commit -F.
5. Verify the new commit and clean working tree before tagging.
6. Before creating a release or beta tag, manually dispatch the **Full
   Regression and Coverage** workflow for the candidate commit and confirm it
   passes. That workflow also runs nightly and again for beta tags. Do not
   substitute `pytest -m "not slow"`; it is not a bounded release suite.
7. If tagging was requested, create the appropriate lightweight tag: `X.Y.Z`
   for a final release or `X.Y.Z-betaN` for a beta package release.
8. Verify that the tag resolves to HEAD. Never move an existing tag, amend,
   bypass hooks, or push unless the user explicitly asks.
9. Rerun the release checker after commit and tag. It must report matching
   versions, the release changelog section, a clean tree, and the current tag.

Report the commit hash, tag, build result, checks run, and whether anything was
left uncommitted or unpushed.
