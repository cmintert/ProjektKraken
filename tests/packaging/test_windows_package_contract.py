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

    def test_lock_is_hash_pinned(self) -> None:
        """Require the generated lock and hashes for every requirement block."""
        lock = (ROOT / "packaging/windows/requirements.lock").read_text(
            encoding="utf-8"
        )
        self.assertIn("--hash=sha256:", lock)
        self.assertIn("pyinstaller==6.17.0", lock.lower())
        self.assertIn("setuptools==", lock.lower())
        self.assertNotIn("# WARNING:", lock)

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
