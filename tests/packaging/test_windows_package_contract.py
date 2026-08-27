"""Dependency-light CI checks for the Windows package source contract."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WindowsPackageContractTests(unittest.TestCase):
    """Validate packaging inputs before the expensive PyInstaller build."""

    def test_versions_match(self) -> None:
        """Require project and runtime versions to agree."""
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        runtime = (ROOT / "src/core/version.py").read_text(encoding="utf-8")
        project_version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project)
        runtime_version = re.search(r'VERSION\s*=\s*"([^"]+)"', runtime)
        self.assertIsNotNone(project_version)
        self.assertIsNotNone(runtime_version)
        self.assertEqual(project_version.group(1), runtime_version.group(1))

    def test_contract_resources_exist(self) -> None:
        """Require every runtime smoke resource in the source checkout."""
        contract = json.loads(
            (ROOT / "packaging/windows/package-contract.json").read_text(
                encoding="utf-8"
            )
        )
        for relative_path in contract["smoke_resources"]:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_gpl_license_is_included_in_the_windows_package(self) -> None:
        """Ship the declared GPL-3.0-only licence with every Windows ZIP."""
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        spec = (ROOT / "ProjektKraken.spec").read_text(encoding="utf-8")
        contract = json.loads(
            (ROOT / "packaging/windows/package-contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 3, 29 June 2007", license_text)
        self.assertIn('(str(ROOT / "LICENSE"), ".")', spec)
        packaging_script = (ROOT / "scripts/build_windows_package.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE")',
            packaging_script,
        )
        self.assertIn("LICENSE", contract["required_package_paths"])

    def test_lock_is_hash_pinned(self) -> None:
        """Require the generated lock and hashes for every requirement block."""
        lock = (ROOT / "packaging/windows/requirements.lock").read_text(
            encoding="utf-8"
        )
        self.assertIn("--hash=sha256:", lock)
        self.assertIn("pyinstaller==6.17.0", lock.lower())
        self.assertIn("setuptools==", lock.lower())
        self.assertNotIn("# WARNING:", lock)

    def test_workflow_audits_the_hash_pinned_runtime_lock(self) -> None:
        """Make a known-vulnerable runtime dependency fail the release build."""
        workflow = (ROOT / ".github/workflows/windows-package.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Audit pinned runtime dependencies", workflow)
        self.assertIn(
            "pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266 # v1.1.0",
            workflow,
        )
        self.assertIn("inputs: packaging/windows/requirements.lock", workflow)
        self.assertIn("require-hashes: true", workflow)

    def test_workflow_keeps_publication_approval_gated(self) -> None:
        """Require the protected environment and validated beta tag gate."""
        workflow = (ROOT / ".github/workflows/windows-package.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("environment: windows-beta", workflow)
        self.assertIn("PK_BETA_LABEL", workflow)
        self.assertIn("inputs.release_tag || github.ref", workflow)
        self.assertIn("GH_REPO: ${{ github.repository }}", workflow)
        self.assertIn(
            "^([0-9]+\\.[0-9]+\\.[0-9]+)-beta([1-9][0-9]*)$",
            workflow,
        )

    def test_build_info_records_x64_architecture(self) -> None:
        """Require explicit architecture provenance in build metadata."""
        script = (ROOT / "scripts/build_windows_package.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('architecture = "x64"', script)

    def test_archive_paths_are_bounded_for_windows_extraction(self) -> None:
        """Keep the extracted root short and reserve room for user folders."""
        script = (ROOT / "scripts/build_windows_package.ps1").read_text(
            encoding="utf-8"
        )
        contract = json.loads(
            (ROOT / "packaging/windows/package-contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            '$packageRoot = Join-Path $stagingRoot "ProjektKraken"', script
        )
        self.assertLessEqual(contract["maximum_archive_entry_length"], 200)
        self.assertIn("maximum_archive_entry_length", script)

    def test_packaged_smoke_allows_cold_runner_startup(self) -> None:
        """Give the signed-off executable a bounded cold-start budget."""
        smoke_script = (ROOT / "scripts/test_packaged_windows.ps1").read_text(
            encoding="utf-8"
        )
        timeout = re.search(r"\[int\]\$TimeoutSeconds\s*=\s*(\d+)", smoke_script)
        self.assertIsNotNone(timeout)
        self.assertGreaterEqual(int(timeout.group(1)), 300)
        self.assertIn('Join-Path $packagePath "logs\\kraken.log"', smoke_script)

    def test_workflow_uploads_failure_diagnostics(self) -> None:
        """Retain actionable logs when the expensive package step fails."""
        workflow = (ROOT / ".github/workflows/windows-package.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Upload package failure diagnostics", workflow)
        self.assertIn("if: failure()", workflow)
        self.assertIn("windows-package-failure-diagnostics", workflow)

    def test_release_upload_excludes_report_directory(self) -> None:
        """Upload only the public ZIP and checksum release assets."""
        workflow = (ROOT / ".github/workflows/windows-package.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("PK_PACKAGE_NAME", workflow)
        self.assertIn('"release-assets/${PK_PACKAGE_NAME}.zip"', workflow)
        self.assertIn('"release-assets/${PK_PACKAGE_NAME}.zip.sha256"', workflow)
        self.assertNotIn("release-assets/* --clobber", workflow)

    def test_known_optional_hidden_imports_are_explicit(self) -> None:
        """Keep clean-runner PyInstaller warning exceptions reviewable."""
        contract = json.loads(
            (ROOT / "packaging/windows/package-contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            "scipy._lib.array_api_compat.numpy.fft",
            contract["allowed_missing_hidden_imports"],
        )


if __name__ == "__main__":
    unittest.main()
