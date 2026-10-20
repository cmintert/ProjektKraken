# Isolated release regression

KRT-103 replaces the release-only monolithic pytest process with a frozen plan,
six balanced shards and a fresh interpreter for each test module. Local execution
is sequential. Remote execution uses six jobs with matrix fail-fast disabled.
Push/PR smoke and the curated pre-push suite retain their existing membership.

## Candidate and evidence contract

A certifying run requires a clean committed checkout. The planner uses the same
collection and reviewed baseline as `scripts.check_test_policy`; it does not
maintain a second inventory. It records every collected node ID, original module
order, marker counts and collection skip reason. Duplicate IDs, collection errors,
unexpected deselection, removed baseline cases and lost critical markers fail.
New cases are assigned automatically. Intentional renames/removals still require
the existing reviewed baseline update procedure.

`plan.json` binds the SHA, planner environment, inventory digest, run identity
and exact module assignments. Each shard records its own complete runner
environment: GitHub can assign different image revisions to separate jobs while
an image rollout is in progress. A shard checks that its source, configuration
and environment stay stable during execution. The aggregator retains each image
and environment digest, and refuses recovery if a later attempt changes the
initial environment of that same shard. Mixed initial shard images are visible
in the evidence and do not silently inherit the planner image. Node IDs are
case-sensitive. Longest-estimated modules are
allocated first to the least-loaded shard, with stable path/shard tie-breaking.
No module is split. `durations.json` contains observed spans for 263 completed
modules from [failed run 39438787358](https://github.com/cmintert/ProjektKraken/actions/runs/39438787358).
These include time between module starts, rather than isolated test-body timings.
Unknown modules use `max(5, number of cases)` seconds and are listed explicitly.
Estimates are scheduling inputs, not acceptance evidence. Regenerate estimates
from a timestamped execution log with (inventory-only node listings are ignored):

```text
python -m scripts.release_regression durations --log <log> --output <new-estimates.json>
```

Each child recollects only its module and verifies the exact ordered node IDs
before execution. It records and flushes setup/call/teardown progress, completion,
skip reasons, stdout/stderr, JUnit and separate coverage. An assertion does not
stop later cases. An abort or timeout does not stop later modules. The supervisor
owns a POSIX process group or Windows kill-on-close job, including native children.
Default limits are 600 seconds per module, 1,500 seconds per shard and 35 minutes
per remote shard job. Unstarted and unfinished cases remain explicit failures.

Reports and artifact checksums are verified again by the aggregator. A passing
call cannot hide failed teardown or a later process abort. Missing reports,
unexpected xfail, conflicting attempts, wrong provenance and corrupt coverage
block acceptance. Complete coverage XML is published only after all module
reports reconcile with the full inventory. Failed partial coverage remains
diagnostic evidence. No coverage threshold or source scope is relaxed.

## Run locally

Use the normal release preflight to retain dependency, Ruff, mypy, complexity,
visual, schema, Help, strict-docs and action-label/native-review gates:

```text
python -m scripts.preflight release
```

The inventory step creates a unique `artifacts/release-runs/<run>/plan.json`.
The final regression step reuses that collection and executes all shards
sequentially. Do not run it alongside render matrices or other GUI suites.
To run regression alone from a clean candidate:

```text
python -m scripts.release_regression local
```

Evidence directories are ignored and immutable per attempt. Preserve the whole
run directory before cleanup; the aggregate refers to its retained attempts.
Release commands fail on a dirty checkout instead of presenting rehearsal
results as committed-candidate evidence. No environment repair is performed by
the runner. Run Windows source tests through the permitted working Python 3.13
environment and the launcher environment preflight.

WindowsApps Python uses brokered launches that escaped Windows job containment
in the explicit descendant probe. Release planning therefore requires a
non-WindowsApps Python 3.13 environment. The implementation was checked using an
isolated runtime under `artifacts/krt103/`, reusing installed project dependencies;
the existing `.venv` was not replaced. Ordinary focused pytest remains available
separately, but cannot certify release isolation through that Store launcher.
Disposable infrastructure tests resolve the actual native interpreter image and
pass the installed dependency paths explicitly. This lets the unchanged `.venv`
run the normal pre-push tests while keeping brokered release execution rejected.

## Remote execution and reviewed recovery

Dispatch the existing manual path:

```text
gh workflow run tests.yml --ref <candidate-branch-or-tag> -f full_regression=true
```

Confirm the resulting head SHA. Release jobs use `ubuntu-26.04`, Python 3.13 and
the complete `requirements.txt` environment. The runner image and actual package
versions are captured; the OS label does not promise an immutable image.
Release concurrency is independent of smoke and does not automatically cancel
an older full run.

The stable acceptance job is **Release verification**. It runs after failed
dependencies, downloads all retained attempts, and emits a red summary for
incomplete evidence. If planning, setup or upload fails before a report exists,
the job logs and workflow summary identify infrastructure incompleteness. A hard
runner loss can prevent an upload; it can never make a missing shard successful.
Artifacts use run, shard and attempt identities and are retained for 30 days.
Download them before expiry if longer retention is needed.

Use GitHub's **Re-run failed jobs** within the same run. Successful shards and
the original plan are retained; failed shards execute every assigned module
again. Do not create a new run and mix its evidence into the old one. Package,
Python, native dependency, runner-image or rendering-environment drift within a
shard's recovery attempts requires a fresh complete run, even at unchanged SHA.
Expired/missing artifacts also
require a complete new run.

Configure the GitHub environment `release-regression-recovery` with a required
reviewer before using recovery. After investigating the failure, approve its
recovery job with a comment in this exact form:

```text
attempt 2: <original failure, investigation and reason recovery is acceptable>
```

Use the actual GitHub run attempt number. The runner reads the approval through
GitHub's [workflow review-history API](https://docs.github.com/en/rest/actions/workflow-runs#get-the-review-history-for-a-workflow-run).
An unprotected environment or missing/empty/wrong-attempt explanation fails
closed. All previous attempts remain in the ledger; no automatic retry hides
flakiness. The workflow uses GitHub's built-in token with read-only Actions access.
It needs no OpenAI API credential. Actions minutes and artifact storage remain
subject to the repository's GitHub billing/allowance.

For local recovery, retain the same plan and evidence root:

```text
python -m scripts.release_regression resume --plan <run>/plan.json --evidence <run> --output <run> --shard 0 --explanation "<reviewed cause>"
python -m scripts.release_regression aggregate --plan <run>/plan.json --evidence <run> --output <run>/aggregate-recovery-2 --explanation "<reviewed cause and acceptance>"
```

The local operator and explanation are recorded. Only the latest attempt for
each shard can be selected; a later incomplete attempt cannot fall back to an
older pass. Local and Linux CI runs are separate evidence sets.

## Release boundary

Tagged Windows builds and publication both verify the latest manual release
run for the exact checked-out SHA. They require successful **Release
verification**, a matching plan/summary and intact combined coverage artifacts.
Successful smoke, an older candidate or metadata-only release status is
insufficient. Untagged package rehearsals remain possible.

The verifier can also run explicitly (authenticated with `GH_TOKEN` locally):

```text
python -m scripts.release_regression verify --repo cmintert/ProjektKraken --sha <candidate-sha>
```

Read-only workflow credentials supply authentication in CI. Artifact redirects
to storage hosts do not receive the GitHub token. Required check configuration
does not prevent a user manually creating a tag; tagged build/publication checks
enforce the boundary independently.

1. Commit the candidate through the normal review and separately authorized
   delivery process; run local checks against that candidate.
2. Obtain complete Linux regression and coverage for that SHA.
3. Create/push the authorized beta tag; retain the exact Windows package ZIP,
   checksum and package smoke reports.
4. Complete native Windows, disposable-account/clean-VM, Help and data-trust
   acceptance for that ZIP.
5. Approve the existing protected `windows-beta` publication environment only
   after those separate gates pass.

## Validation and performance evidence

`tests/cli/test_release_regression.py` uses disposable suites to assert that
failure, hard process exit and timeout preserve later results. It also covers
missing/corrupt artifacts, recovery, descendant cleanup, exact assignment and
release-verifier isolation. The manual **Release infrastructure verification**
workflow runs these checks on both Linux and Windows without adding PR/push work.

Before KRT-103 is Done, record an exact committed-candidate full run, combined
coverage and skip reconciliation, Linux reproduction of both known assertions,
and isolated/shared-process-order diagnosis of the former abort. A green sharded
run does not prove the underlying shared-process lifetime defect is fixed.

Record collection/setup/install time, module startup cost, slowest shard, total
elapsed time, runner minutes, artifact size and time to identify a failure. Setup
timings are uploaded separately; reports retain module and shard wall time.
The 20–25 minute remote target remains a measurement target, not a demonstrated
result. Keep full dependencies until a narrower environment has proved equivalent;
do not remove coverage or relax GUI assertions to meet the target.

### Preserved diagnostic baseline

Run 39438787358 used candidate `a80e285971f968f772ba6a6174de5fb16eeeb9f0`,
Ubuntu 26.04.1, Python 3.13.16 and Qt/PySide6 6.10.1. It collected 6,871 cases,
failed after about 36 minutes and exited 134 near 42%, without complete coverage.
The last active case was `test_lmstudio_circuit_breaker`; this does not establish
provider retry logic as the native abort's cause. Earlier failures were the
populated explorer filter-row assertion and repeated Event focus-mode restoration.
The full retrieved job log is preserved locally under
`artifacts/krt103/baseline/github-job-118682813308.log` and its observed module
spans seed the checked-in estimates. KRT-100 remains blocked on these release
failures and on exact-candidate/package acceptance.

### Implementation verification (20 October 2026)

The uncommitted-source assignment proof collected 6,901 cases across 504 modules,
with zero collection skips and exactly one assignment per case. Six shards contain
83–85 modules each. This change adds 30 infrastructure cases to the previous
6,871-case suite; it does not add 7,000 tests. Estimated loads are about 1,019
seconds per shard before unknown startup/setup cost; 241 modules use fallback
estimates. These are estimates, not a measured full-run performance result.

The focused Windows infrastructure/policy/preflight/package-contract run passed
73 cases on standalone Python 3.13.16 and Qt/PySide6 6.10.1 in 26.94 seconds.
This includes hard process exit, timeout, native descendant cleanup on success
and timeout, missing/corrupt evidence and reviewed recovery. Repository-wide Ruff,
typing over `src` plus the new scripts, and strict Sphinx passed.
Evidence is retained under ignored `artifacts/krt103/`, including `focused.xml`,
`final-probes/`, `assignment-proof.json` and the baseline log. The isolated
verification environment is `artifacts/krt103/test-env/` and its standalone base
runtime is `artifacts/krt103/python313/`; preserve them if local reruns are needed.
The final compatibility rerun through the original `.venv` also passed all 73
focused cases in 28.79 seconds, exercising native process containment through
the disposable harness rather than accepting the WindowsApps broker as a release
runtime.

The Windows-hosted Linux container probe was stopped at the owner's request;
none of its results certify Linux release behavior. Authoritative Linux checks
will use GitHub's Ubuntu runner after the change is committed and pushed.
The first dispatched run on `aad50c84` was
[39492278049](https://github.com/cmintert/ProjektKraken/actions/runs/39492278049).
Its planner used runner image `20261012.163.1`; several shards received
`20261018.168.1` and failed the original cross-job environment equality check
before tests. Shard 0 passed, but the aggregate correctly stayed red with no
complete coverage. Runner images are now recorded per shard, while each job
still checks its own environment during execution and against later recovery
attempts. This fix requires a new full run on its own exact commit.
The manual infrastructure workflow runs the three reported cases independently,
both with their original fixtures and with production QApplication QSS applied;
its optional shared-order probe runs the five preceding GUI-heavy modules before
the provider module, with flushed progress and faulthandler. That bounded order
is diagnostic, not a claim to reproduce every earlier case in the failed run.
KRT-103 remains In Progress: committed-candidate Linux regression/coverage,
remote adversarial results, runtime/cost measurements and package/native
acceptance are still outstanding. No release is validated by this local proof.
