# 0.21.0 beta 1 release preparation

Preparation date: 30 October 2026. Tracked by
[KRT-117](https://linear.app/projektkraken/issue/KRT-117/prepare-0210-beta1-release-candidate).
Source baseline: `a02fb8cb`, plus the release-preparation changes. Application
version: `0.21.0`; intended beta package tag: `0.21.0-beta1`.

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

## Remaining delivery steps

1. Approve and create the coherent release commit.
2. Run and verify Full Regression and Coverage for that exact committed
   candidate before creating the beta tag.
3. Build and verify the actual Windows release package, including packaged-world
   data safety and required native acceptance.
4. Verify the intended tag and package identity, ZIP checksum and publication
   surfaces before approved distribution.

See [release regression](release-regression.md),
[development release gates](development.md#local-first-quality-checks) and the
package's clean-machine/data-safety verification instructions for the separate
release requirements.
