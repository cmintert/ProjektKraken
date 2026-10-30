# 0.21.0 beta 1 release preparation

Preparation date: 30 October 2026. Tracked by
[KRT-117](https://linear.app/projektkraken/issue/KRT-117/prepare-0210-beta1-release-candidate).
Source baseline: `a02fb8cb`, plus the release-preparation changes. Application
version: `0.21.0`; intended beta package tag: `0.21.0-beta1`.

The original preparation evidence below precedes commit `c7dce37b`. The
publication follow-up records the subsequent GitHub result and pending repair.

This record captures preparation before the release commit. Release preparation
and a local executable build do not establish exact-commit full regression, packaged data
safety, clean-machine acceptance or publication approval. The release commit
requires owner approval under the repository's bump-version workflow.

## Scope and upgrade boundary

The candidate rolls accumulated changes into the `0.21.0` changelog section and
aligns project/runtime versions, release date, README, installation examples,
release notes and publication copy. Historical release and evidence records
retain their original version identities. No application behavior changes are
introduced by this preparation.

The [release notes](../releases/0.21.0-beta1.md) summarize Event timing and
dependency trails, Map presence bindings, activity workspaces, Settings Center,
World Context and keyboard/navigation improvements. They explain the schema-4
upgrade, complete-world backup and recovery requirements, and older-version
incompatibility. The download guidance distinguishes the source candidate from
packages actually published on the Releases page.

## Preparation verification

Commands use the existing project Python environment; Qt tests run offscreen.
The Windows Store base interpreter requires permitted execution outside the
restricted sandbox. This does not replace the environment or alter source.

| Check | Result |
| --- | --- |
| Release metadata and changelog checker | Matching `0.21.0`; new release and fresh Unreleased sections; dirty tree expected |
| Ruff, `src/ tests/` | Passed |
| Mypy, `src` | Passed, 570 source files |
| Dependency authority and Windows pins | Passed |
| Help inspection declarations and excerpts | Passed |
| `pytest -m ci_fast -q` | 2,897 passed, 3 skipped; 4,518 deselected; 511.73 seconds |
| About dialog version display | 2 passed |
| Strict Sphinx, including new pages | Passed |
| Offline Help generation and bundled integrity | Passed; version `0.21.0`, revision `a02fb8cb`, dirty candidate; all source and payload hashes validated |
| Windows executable build | PyInstaller completed successfully in about 292 seconds |
| Windows executable resource metadata | FileVersion `0.21.0`; ProductVersion `0.21.0 beta1` |

Logs and isolated build output are retained under
`artifacts/release-0.21.0-beta1/`. These are ignored local artifacts, not a
published package. Review captures are retained under
`output/playwright/release-0.21.0-beta1/`.

The executable is at
`artifacts/release-0.21.0-beta1/dist/ProjektKraken/ProjektKraken.exe`.
Its SHA-256 is
`f04352cdabe01a34268c43be593370fdc66b044993d5872bf92d50607d9c7cd1`.
This identifies the local executable, not a release ZIP checksum.

The missing hidden imports (`tzdata` and two SciPy modules) match the packaging
contract's allowed warnings. Optional TensorBoard collection and dependency
deprecations also warn without failing the build. The package-only Help checker
requires `build-info.json`, which the raw PyInstaller build does not create;
bundled Help was instead validated directly with `HelpBundleService` against
the source identity and hashes. No executable startup or packaged data-safety
acceptance is claimed here.

## Documentation review

This record uses the [documentation review form](documentation-review.md).

| Field | Record |
| --- | --- |
| Reader and purpose | Existing users assessing changes and upgrading; new users finding the correct package |
| Primary documentation purposes | Release notes: reference; installation: how-to; this record: verification reference; README and publication copy: product overview |
| Canonical pages and release | README, Getting Started and `docs/releases/0.21.0-beta1.md`; candidate `0.21.0-beta1` |
| Source identity | `a02fb8cb` plus the listed uncommitted release-preparation scope |
| Behavior and persistence sources | Existing task guides; workspace definitions; timing-source/review controls; migration runner and schema definitions; packaging workflow; KRT-111's current owner-acceptance record |
| Preserved routes and Help identities | Getting Started headings, `help-world-manage`, topic IDs, control excerpts and inspection bindings retained; no widget or Help inventory changes |
| Procedure review | Installation still checks the ZIP hash, extracts the complete folder and keeps `_internal`; update guidance requires a complete-world backup and recovery bundle |
| Rendered review | Playwright inspection of generated release notes and installation link, Chrome at 1440 × 1100 in the light theme; version, filename, recovery text and link destination checked |
| Corrections and discrepancies | README labels the older workspace screenshot; AI wording acknowledges optional drafting; current Linear acceptance supersedes the earlier KRT-111 checkpoint note in the historical changelog |
| Native/live Help review | Not tested in this release-preparation pass; automated coverage recorded separately |
| Human prose approval and reader round | Pending; no participants, observations or reader-performance results claimed |

The rendered page review is an agent inspection. It does not establish native
Windows display coverage, owner prose approval or newcomer task performance.
Use the [reader-testing form](documentation-reader-testing.md) if a reader round
is scheduled; no round is scheduled by this record.

## Publication follow-up — 30 October 2026

The owner approved `c7dce37b271147af468306e541f252a8fe792cd2` and subsequently
authorized tag, push and publication, narrowed to GitHub only. The normal push
passed all 12 local checks, including 2,906 tests passed and 3 skipped, and
published that commit to `main`.

[Documentation run 41090143977](https://github.com/cmintert/ProjektKraken/actions/runs/41090143977)
passed. The public release-notes page returned HTTP 200 with the new version and
schema-4 guidance. Deployment used the already allowed `main` branch; the Pages
access policy was preserved. No itch.io change was made.

[Full regression run 41090132143](https://github.com/cmintert/ProjektKraken/actions/runs/41090132143)
collected 7,418 tests across 523 modules and six shards, with zero collection
skips. Three shards passed and three failed. All module reports were retained;
the final Release verification failed. No beta tag or package publication was
performed from that result.

### Diagnosed failures and prepared repair

| Failure | Repair and preserved assertion |
| --- | --- |
| Two CLI backup assertions search a Windows-only path on Linux | Isolate the child process HOME as well as APPDATA; locate the fixture's platform data directory. Keep backup count, restore and repair assertions. |
| Timeline settings double lacks `contains` | Complete that method on the existing double; retain persistence and view-state assertions. |
| Longform header is observed at 20 px after a theme/panel move | Wait for queued reflow and require the same exact 12 px top gap and horizontal alignment in every existing theme/width/zone case. |
| Two wall-clock limits fail with coverage tracing | Use the documented pytest-cov `no_cover` marker only on those two benchmark test bodies; retain every event count, operation and 200/500/100 ms limit. The functional scenarios remain instrumented. |

The unchanged Windows modules passed before repair. A disposable Linux container
then reproduced the fixture failures and the coverage-instrumented blocking-time
failure from a clean archive of `c7dce37b`. The container uses Debian bookworm,
Python 3.13.16 and PySide6 6.10.1; GitHub used Ubuntu 26.04 and Python 3.13.17, so
this is a focused reproduction, not exact runner-environment certification.

The untouched solver measured about 134 ms loading 300 Events and 249 ms zooming
500 Events without instrumentation. With only the two timing markers, the full
13-case module passed under the coverage-enabled command, measuring about
131 ms loading, 241 ms zooming and 0.04 ms panning. Source-line comparison found
5,866 covered application lines both before and after, with zero lost lines.
See the [pytest-cov marker reference](https://pytest-cov.readthedocs.io/en/stable/markers-fixtures.html).

Profiling and a solver-indexing experiment informed the diagnosis. All runtime
solver experiments were discarded; the prepared repair changes tests and this
release record only. Source workloads, functional assertions, timing budgets,
test membership and the coverage configuration are retained.

### Repair verification

| Check | Result |
| --- | --- |
| Linux workspace, settings and CLI modules, with coverage | 70 passed |
| Linux original Timeline module, coverage command with timing-only markers | 13 passed |
| Windows four-module regression, with coverage | 83 passed, 96.73 seconds |
| Ruff / formatting | Passed; all four changed test files formatted |
| Repository-wide mypy and reviewed test inventory | Passed, 570 source files; full inventory remains 7,418 tests |
| Strict Sphinx and final diff review | Passed |

The complete failed CI evidence is retained under
`artifacts/release-0.21.0-beta1/regression-41090132143/complete/`.
Linux baseline, profiler, repair, timing and line-coverage evidence is under
`artifacts/release-0.21.0-beta1/linux-repro/`. These ignored artifacts preserve
failed experiments as well as successful verification.

## Pre-tag dependency audit — 30 October 2026

The approved test repair was committed as
`4c8c4331c2f26124240a1e1c209c8e6b32a5f1e5` and pushed through all 12 local gates,
including 2,906 tests passed and 3 skipped. Its
[full regression run 41123818126](https://github.com/cmintert/ProjektKraken/actions/runs/41123818126)
was dispatched before tagging. Its
[documentation deployment 41123831113](https://github.com/cmintert/ProjektKraken/actions/runs/41123831113)
passed through the existing `main` route.

A pre-tag `pip-audit` check of the Windows lock found 12 advisories for
filelock 3.32.4 and one for setuptools 84.0.0. The upstream
[filelock 4.2.1 release](https://github.com/tox-dev/filelock/releases/tag/4.2.1)
and [setuptools advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)
identify the replacement versions used here. This records the advisory gate's
result, not proof that every reported exploit path is reachable in Kraken.

The prepared dependency repair regenerates `packaging/windows/requirements.lock`
on Windows x64 / Python 3.13 using pip-tools, selecting only filelock 4.2.1 and
setuptools 84.1.0. The other 90 distribution pins are unchanged. The generator
header records the exact targeted-update command. Evidence is retained under
`artifacts/release-0.21.0-beta1/`:

| Check | Result |
| --- | --- |
| Dependency projections and direct Windows pin contracts | Passed |
| Repeated advisory audit of all 92 locked distributions | No known vulnerabilities found |
| Installation of the two patched wheels in a separate environment | Passed with `--require-hashes --only-binary :all: --no-deps` |
| Existing development PyInstaller, Hugging Face Hub, Torch and Sentence Transformers imports with isolated patched wheels | Passed; not final package certification |
| FileLock acquisition, release and reentrancy with the patched wheel | Passed |
| Strict Sphinx build and diff whitespace check | Passed |

The source-development environment was preserved. The eventual Windows package
workflow must install the complete hashed lock and repeat the advisory audit,
build, contract checks and packaged launch/restart smoke tests. Full regression
must pass for the eventual dependency-repair commit before the beta tag is made;
the run on `4c8c4331` cannot certify a later source SHA.

## Timeline load blocker and prepared solver fix — 30 October 2026

The dependency repair was approved, committed as
`d6f4375a220ef92c2f368cade6990c85000488ae` and pushed through all 12 local gates
(2,906 tests passed, 3 skipped). Its documentation deployment passed. The
[full regression run 41126694666](https://github.com/cmintert/ProjektKraken/actions/runs/41126694666)
did not pass: the unchanged Timeline load benchmark measured 220.96 ms against
its 200 ms limit. The preceding run on `4c8c4331` measured 261.10 ms at the same
assertion; all 523 module reports were retained and only that module failed.
Some jobs in the newer run were marked cancelled, including a shard whose
recorded steps and test ledger passed. Neither run is accepted as release proof.

### Investigation and implementation boundary

The benchmark loads 300 independent Events into a hidden Timeline with no
prepared temporal context. A load-only diagnostic recorded zero dependencies
and zero paint calls. Of 142.26 ms in that instrumented local run, 98.23 ms was
temporal-state work, including 95.66 ms resolving anchors; dependency preparation
took 3.94 ms. These inclusive phase timings overlap and must not be added.

The synchronous path is `set_events` → initial playhead setup → temporal-state
update → world timing resolution. Before the fix, 300 two-endpoint components
repeatedly scanned global edges, domains and evidence, inspecting 540,000 entries
in those loops. A prepared immutable temporal context can reuse a resolution;
a cold context still needs the calculation. This is evidence for a solver
bottleneck, not a measurement of individual phases on the GitHub runner.

The prepared runtime fix keeps the existing UI/threading and timing contracts:

- Partition compiled edges, domains, evidence, calendars and diagnostics once
  per generation, rebuilding after calendar quarantine changes the graph.
- Preserve component/fact ordering, source-owned diagnostic rules and authored
  constraints; use sets for component membership.
- Remove only already-true self-bounds from the internal relaxation graph after
  exact affine reduction. Retain strict zero and negative bounds, original
  constraint records, query semantics and provenance.
- Keep benchmark workloads, coverage markers and all timing limits unchanged.
  Add strict-boundary, disconnected-world and linear-input-scan regressions plus
  a dependency-direction guard for the new pure core partition module.

### Verification of the uncommitted runtime candidate

The retained Linux diagnostic environment is Debian bookworm / Python 3.13.16 /
Qt 6.10.1. GitHub used Ubuntu 26.04 / Python 3.13.17 / Qt 6.10.1; local timings
do not certify performance on that runner.

| Same local command/workload | Before | Prepared fix |
| --- | --- | --- |
| Full 13-case Timeline module with coverage | 13 passed | 13 passed |
| UI load blocking, 300 Events | 130.97 ms | 105.84 ms |
| Average zoom, 500 Events | 243.26 ms | 162.96 ms |
| Average pan, 500 Events | 0.04 ms | 0.04 ms |
| Pure solver median, 300 independent Events | 81.59 ms | 54.12 ms |
| Pure solver median, 600 independent Events | 217.38 ms | 105.56 ms |
| Pure solver median, 1,200 independent Events | 645.95 ms | 216.85 ms |

The broader Linux semantic/persistence/context run passed 140 tests. A diagnostic
wrapper compared 223 solver calls with the preserved pre-fix solver and constraint
implementation; complete serialized outputs matched. Stateful cancellation
callbacks were exercised by the existing tests rather than consumed twice by
the comparator. Repository-wide Ruff, mypy (571 source files), complexity policy
and test policy passed. The full inventory is now 7,425 tests, with seven added
critical-suite cases and no removed tests or lost memberships. No complexity
allowance was added or raised.

The Windows coverage-enabled semantic, persistence, context, architecture and
Timeline regression passed 211 tests in 39.84 seconds. Its unchanged benchmark
measured 63.71 ms loading, 115.01 ms zooming and 0.04 ms panning.

Raw logs, phase/profile data, original solver sources and equivalence/scaling
reports are retained under
`artifacts/release-0.21.0-beta1/linux-repro/load_investigation/`. Windows regression
and policy logs are under `artifacts/release-0.21.0-beta1/`. The runtime candidate
still requires its approved commit, a passing exact-SHA full regression and the
actual Windows package checks before publication.

## Remaining delivery steps

1. Review and approve the runtime solver repair commit tracked in
   [KRT-118](https://linear.app/projektkraken/issue/KRT-118/verify-and-publish-0210-beta1-on-github).
2. Push the approved repair through normal gates and obtain successful exact-SHA
   Full Regression and Coverage before creating the beta tag.
3. Build/audit/smoke and verify the actual Windows release package, retaining
   the ZIP checksum and the actual scope of native/data-safety review.
4. Publish the authorized GitHub prerelease and verify its tag, assets and
   checksum. KRT-44 and KRT-91 retain their separate backlog review scope.

See [release regression](release-regression.md),
[development release gates](development.md#local-first-quality-checks) and the
package's clean-machine/data-safety verification instructions for the separate
release requirements.
