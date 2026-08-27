"""Chromium-level regression coverage for longform stored HTML injection."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_RESULT_PREFIX = "RESULT_JSON="


@pytest.mark.integration
@pytest.mark.slow
def test_longform_renderer_keeps_published_payload_inert_in_chromium() -> None:
    """Run the hostile-content probe without risking the pytest process."""
    repo_root = Path(__file__).resolve().parents[2]
    probe_path = repo_root / "tests" / "helpers" / "longform_browser_security_probe.py"
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONFAULTHANDLER": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "QT_OPENGL": "software",
            "QSG_RHI_BACKEND": "software",
            "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
        }
    )

    completed = subprocess.run(
        [sys.executable, str(probe_path)],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (
        "Chromium security probe failed or crashed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )

    result_lines = [
        line.removeprefix(_RESULT_PREFIX)
        for line in completed.stdout.splitlines()
        if line.startswith(_RESULT_PREFIX)
    ]
    assert len(result_lines) == 1, completed.stdout
    observed = json.loads(result_lines[0])
    assert observed == {
        "bodyXss": False,
        "imageXss": False,
        "titleXss": False,
        "activeElements": 0,
        "attackerResources": 0,
        "formatting": "Safe formatting",
        "wikiHref": "#section-1",
        "wikiText": "working wiki link",
        "locationHash": "#section-1",
        "tocText": (
            '<img src=x onerror="globalThis.__titleXss=true">Imported title'
        ),
        "tocMarkup": True,
    }
