# Windows beta clean-VM validation

Complete this checklist against the exact CI candidate before approving the
protected `windows-beta` GitHub Environment. Onboarding remains frozen until this
record and the automated packaged smoke are both green.

- Candidate: `ProjektKraken-0.19.0-beta1-windows-x64.zip`
- Source tag: `0.19.0-beta1`
- Windows version/build:
- Standard user account:
- Python absent (`python` and `py` are not found):
- Recorded ZIP SHA-256:
- Supplied SHA-256 matches:
- SmartScreen result or prompt:
- ZIP extracted completely before launch:
- `ProjektKraken.exe` opened by double-click:
- About dialog reports `0.19.0`:
- Named world created through World Manager:
- World ID/path recorded:
- Application closed cleanly:
- Restart reopened the same world and retained data:
- Representative icons render:
- Graph opens and renders bundled offline assets:
- Map opens and renders controls/icons:
- Longform opens and bundled web assets load:
- `logs/kraken.log` contains no startup failure:
- Validator/date/name:
- Result: PASS / FAIL

Attach this completed record, the checksum, and any screenshots or failure logs to
the `[Beta] Produce reproducible Windows beta package` GitHub issue before release
approval.
