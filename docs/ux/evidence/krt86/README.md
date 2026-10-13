# KRT-86 offline Help implementation evidence

Date: 2026-10-13. Implementation is verified locally; commit delivery and issue
status are tracked in KRT-86.
This delivers the build/read/package layer of the
[Expert Assistance contract](../../expert-assistance-contract.md).
Contextual invocation, the companion viewer and control inspection remain
KRT-87/88; prose review remains KRT-89 and native/human acceptance KRT-91.

## Implemented behavior

The registry resolves 20 substantive topics and three utility routes against
explicit canonical targets. The 12 manual pages produce local Qt-compatible
HTML, 90 search sections, referenced raster assets, optional canonical excerpt
HTML and a version/revision/dirty-source/hash manifest. No second maintained
manual is introduced. Structural targets and a canonical Longform recovery link
were added without rewriting reference instructions.

Local pre-push/release validation and direct PyInstaller spec builds regenerate
Help. Windows CI uses a separate documentation interpreter without changing
workflow triggers or publishing policy. The reader rejects stale, corrupt,
version-mismatched or escaped resources and provides local recovery guidance.
External references are inert text; remote images fail before Sphinx can fetch
them. Source Help resolves independently of the working directory.

The internal `--help-bundle-smoke-report` route validates and renders Help before
MainWindow/world initialization. It is a verification route, not a user-facing
Help viewer. It has no database, command, AI or network dependency.

## Automated verification

- `ci_fast`: 1,954 passed, three skipped; `artifacts/krt86/ci-fast.xml` and log.
  Subsequent Help-only startup and remote-image guard changes passed the focused
  suite: 60 passed, one skipped; `artifacts/krt86/focused.xml` and log.
- Ruff and repository-wide mypy passed (468 source files); dependency,
  complexity and visual policy checks passed. Evidence is in
  `artifacts/krt86/{ruff,mypy,dependencies,complexity,visual-policy}.*`.
- Strict Sphinx website generation passed. Generated user HTML was inspected:
  all 23 explicit targets and the Longform recovery link resolve.
- Tests cover deterministic regeneration, failed-build preservation, canonical
  excerpts, stale/version/corrupt content, broken links/assets/targets, unsupported
  raw HTML, remote-image rejection, fallback, frozen paths and arbitrary CWD.
- Qt 6.10.1 rendered tables, code, Unicode/custom-calendar text and bundled
  images. Every emitted anchor must survive Qt parsing. Adjacent empty anchors
  collapse in Qt; invisible anchor characters retain both semantic and legacy
  targets without adding visible prose.
- Windows symlink testing was skipped because this session lacks symlink
  privilege. Other path-escape cases passed.

The test-inventory checker remains blocked by two **pre-existing** obsolete
`test_focus_action_precedes_bold_in_formatting_toolbar` entries. HEAD already
contains `test_focus_action_uses_secondary_writing_row` instead. The unrelated
baseline was not regenerated; details are in `artifacts/krt86/test-policy.log`.

## Package evidence and limits

Package build logs and candidates are retained under `build/krt86-package/` and
`artifacts/krt86/windows/`. Earlier candidates are provisional; final verification
uses the dedicated Help-only probe, not ordinary application startup.

The general provisional smoke followed saved application settings and opened
Northwatch Demo. It reported success and sent no authoring commands, but it is
not evidence of isolation from existing-world settings. The final Help-only route
avoids world initialization entirely.

Final ZIP: `artifacts/krt86/windows/ProjektKraken-0.19.7-krt86-final-windows-x64.zip`
(470,461,267 bytes).

SHA-256:

```text
d148f3563f83e40dbd4e375a7f7051a0aef48ab4389c6a1548be0717c3e7ea26
```

The final extracted Help-only probe passed with Python absent from PATH, HTTP/S
proxies pointing to an unavailable local port, and an unrelated working
directory. It rendered all 12 pages, verified their anchors and validated 90
search sections for version 0.19.7 / source revision
`0d74316baaa5af102f82d0b4628cbe1f0d00abcb` (dirty source). No `worlds/` directory
was created. Results: `artifacts/krt86/windows/final-reports/help-only.json`.
Resource, archive-path and frozen-bytecode audits passed; the frozen archive
contains no Sphinx, Docutils or MyST parser modules. The reader's installed
manifest SHA-256 is
`25e91cf60dcdab2bec22ee2d634cbd6fe26aa49f98a68e001312044a16021178`.

The build is a dirty-source verification candidate, not a tagged release or an
isolated hash-pinned CI build. PowerShell packaging syntax was verified locally;
the release-script end-to-end run requires PowerShell 7, absent on this host.
Python is installed on the host; its absence from the executable's PATH and the
unusable proxies are scoped dependency evidence, not a clean offline VM run.

No user-facing control presentation changed. Generated content contains no
fixed theme colors; Help link styling, focus, disabled controls, theme switching
and narrow/scaled layout evidence belong to KRT-87/91. Authoring Contracts
1–9 and 11 retain their existing meaning; the Help-only probe bypasses authoring
state. Static/rendering checks do not establish human reference-prose approval,
native modal/multi-monitor behavior or clean-VM acceptance.
