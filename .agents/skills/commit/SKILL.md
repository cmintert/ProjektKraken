---
name: commit
description: Use this skill when the user wants to commit changes, create a git commit, write a commit message, or types "/commit". Guides the user through writing a conventional commit message with the correct type, scope, description, body, and footer.
---

# Conventional Commit Skill

Guide the user through creating a well-formed conventional commit message, then execute the commit.

## Step 1 — Inspect Changes

Run the following in parallel:

- `git status` — see which files are staged vs. unstaged
- `git diff --staged` — see exactly what is staged; if nothing is staged, fall back to `git diff`
- `git log --oneline -5` — check recent commit style for this repo

If nothing is staged and nothing is modified, tell the user there is nothing to commit and stop.

If there are unstaged changes but nothing staged, ask the user whether they want to stage everything (`git add -A`) or specific files before continuing.

## Step 2 — Update the Changelog

Every commit must include an update to the root `CHANGELOG.md`. Follow
`.agent/workflows/update-changelog.md` before drafting the commit message:

- add concise, dated entries under `## [Unreleased]` for the complete commit
  scope, including documentation, tests, tooling, and internal maintenance;
- update `Last Updated` to the current date;
- set `Commit` to the current pre-commit `HEAD` hash, which records the baseline
  reviewed for the new entry (a commit cannot contain its own final hash);
- stage the changelog with the rest of the approved changes.

Do not skip this step for small or non-user-facing commits.

## Verification

Choose focused tests for the changed behavior. When a broad local regression
check is warranted, run the curated PR suite:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -m ci_fast -q
```

`ci_fast` is the bounded PR suite for deterministic core, command,
persistence, CLI, security, packaging, and selected repository tests. Do not
use `pytest -m "not slow"` as a fast-suite substitute: it selects every test
that lacks the `slow` marker.

Run `python -m ruff check src/ tests/` and `python -m mypy src/` when the
commit changes Python production code, tests, or CI quality configuration.
The full coverage-enabled suite is a nightly, manual-dispatch, and beta-tag
release check; it is not required for an ordinary commit.

## Step 3 — Draft the Commit Message

Using the diff content, draft a message that follows this structure:

```
<type>(<optional scope>): <short description>

<optional body>

<optional footer>
```

### Types (choose exactly one)

| Type       | When to use                                              |
|------------|----------------------------------------------------------|
| `feat`     | New feature visible to the user                          |
| `fix`      | Bug fix                                                  |
| `docs`     | Documentation only                                       |
| `style`    | Formatting, whitespace — no logic changes                |
| `refactor` | Code restructuring without behavior change               |
| `perf`     | Performance improvement                                  |
| `test`     | Adding or updating tests                                 |
| `build`    | Build system, dependencies, tooling                      |
| `ops`      | CI/CD, infrastructure, deployment scripts                |
| `chore`    | Maintenance (`.gitignore`, project config, etc.)         |

### Scope (optional)

A short lowercase identifier for the affected area, e.g. `api`, `ui`, `db`, `auth`, `timeline`, `map`.
Omit if the change is truly cross-cutting.

### Description rules

- Imperative mood: `add`, `fix`, `change`, `remove` — not `added`, `fixes`, `changing`
- Lowercase first letter
- No trailing period
- Target ~50 characters; hard limit 72

### Body (optional)

- Explain **why**, not what — the diff already shows what
- Wrap at 72 characters
- Separate from subject with a blank line
- Skip for trivial changes (typos, single-line fixes)

### Footer (optional)

Use for:

- **Breaking changes**: add `!` after the type/scope AND add `BREAKING CHANGE: <explanation>` in the footer
- **Issue references**: `Closes #123`, `Refs #456`

Example with breaking change:

```
feat(api)!: remove deprecated /v1/events endpoint

The v1 endpoint has been superseded by v2 for 6 months.
All known clients have migrated.

BREAKING CHANGE: /v1/events is no longer available. Use /v2/events.
```

## Step 4 — Present for Review

Show the user the full drafted commit message in a fenced code block. Ask them to confirm or request changes. Do **not** commit yet.

## Step 5 — Commit

Once the user approves:

1. Stage any files the user agreed to stage (if not already staged)
2. Write the approved message to a temporary file outside the repository, then use
   Git's file-based message option so Windows quoting cannot corrupt it:

```powershell
git commit -F C:\tmp\projektkraken-commit-message.txt
```

   Create the temporary file with the available safe file-writing tool, never stage
   it, and remove it after the commit attempt.

3. Run `git status` and `git log -1 --oneline` after the commit to confirm it
   succeeded.
4. Do **not** push unless the user explicitly asks.

## Safety Rules

- Never use `--no-verify` or `--no-gpg-sign` unless the user explicitly requests it
- Never amend an existing commit — always create a new one
- Never force-push
- If a pre-commit hook fails, fix the underlying issue and try a new commit; do not bypass the hook
