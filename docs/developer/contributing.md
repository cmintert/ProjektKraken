# Contributing

1. Make one coherent change. Use a focused branch when isolation helps; a pull
   request is optional for solo work. A verified direct commit is also fine.
2. Update tests and documentation when behaviour changes.
3. Add a dated entry to the Unreleased changelog before committing.
4. Run the relevant test, lint, type, and documentation checks. CI requires
   `python -m ruff check` and `python -m mypy src` to pass with no diagnostics.
5. Commit the change. If using a pull request, explain user-visible behaviour
   and architectural implications there.

Linear tracks substantial features, bugs, and planned investigations. Reuse an
existing `KRT` issue when one fits; small fixes and housekeeping need no issue.
For a tracked change, add `Refs KRT-<number>` to the commit footer. Mark an
implementation issue Done after the work is verified and committed.

Use conventional commit types such as `feat`, `fix`, `docs`, `refactor`,
`test`, and `chore`.

Do not mix unrelated cleanup with a feature change. Preserve existing user
changes in a dirty working tree.

## Incremental architecture and complexity improvement

Reviewed C901 debt is recorded in `scripts/complexity_policy_baseline.json`.
Untouched debt may remain. Every executable change to a reviewed callable,
including behavior fixes, must strictly decrease Ruff-measured complexity.
Signatures and decorators count; comments, docstrings, formatting, and pure
moves/renames do not. New/extracted code must satisfy the normal limit of 15.
Existing dependency-direction tests remain the architecture authority; extend
them with narrow guards when an extraction creates an enforceable boundary.

Run `python -m scripts.check_complexity_policy` before and after editing. It
compares the worktree against HEAD by default. Use `--base-ref <commit>` for a
whole branch or PR and `--format json` for callable IDs, before/after values,
touch status, and required actions. Missing history/tooling fails closed. CI
uses the PR base/push predecessor and project-pinned Ruff. First adoption can
only baseline existing suppressed debt from that comparison revision.

Carry the persistent allowance ID through a move or rename; update its path and
qualified symbol, never replace the ID. The recorded ceiling must equal the
improved measurement. Remove suppressions at 15 or below, then run `--tighten`
to apply only verified reductions/removals. Checks never change source or
baselines by default. Tightening cannot add exceptions or raise ceilings.
Exceptional increases require separate explicit policy review and a policy
amendment, not baseline regeneration or a routine bypass option.

Use the repository skill
[`incremental-refactor`](../../.agents/skills/incremental-refactor/SKILL.md) to
prepare and verify one authorized target. Record before/after evidence in its
Linear issue, preserve behavior and architecture contracts, and keep the issue
open until verified and committed. The skill does not schedule changes or
authorize commits/pushes. No additional LOC targets or complexity framework
are introduced.

## Authoring interaction contract

All UI presentation changes also follow the
[visual vocabulary](../ux/visual-interaction-vocabulary.md), including Map,
Timeline, Graph and Longform. Use shared roles/helpers and run
`python -m scripts.check_visual_policy`. PR/direct-commit verification notes
record role choices, contract numbers, disabled/focus/theme-switch/narrow evidence,
context preservation and justified exceptions. Review exact visual-policy baseline
changes with their explanation; new violations and stale exceptions fail CI.
Unify/correct legacy styling on the next function/method or stylesheet touch;
the policy checker expires those exemptions against HEAD locally and the PR/push
baseline in CI. Unrelated paths do not require a whole-app redesign.

Use [UI/UX Contract v1](../ux/authoring-contract.md) for authoring UI changes.
Linear remains the design authority; update both copies in the same work batch
when deliberately revising a rule. In the change description, identify relevant
contract numbers, visible entry points (including narrow layouts), keyboard
ownership, selection/draft/caret/playhead preservation, and justified exceptions.
Use shared disclosure and overflow presentation before inventing local patterns.
Consult the [surface audit](../ux/authoring-interaction-audit.md) and
[20-task benchmark](../ux/authoring-benchmark.md). Known violations belong to their
owning issues; do not silently endorse them through regression tests.
