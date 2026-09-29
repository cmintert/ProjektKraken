"""The benchmark launcher must not select a real user world."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.ux.fixture import prepare_task


def test_windows_settings_select_only_the_imported_copy(tmp_path: Path) -> None:
    """A fresh process reads the task-local INI instead of registry settings."""
    scenario = prepare_task("KA-01", tmp_path / "worlds")
    world = Path(scenario["world_path"])
    settings = tmp_path / "settings"
    script = (
        "import json,sys; from pathlib import Path; "
        "from PySide6.QtCore import QSettings; "
        "from tests.ux.launch import configure_task_settings; "
        "from src.services.world_storage_settings import WorldStorageSettings; "
        "configure_task_settings(Path(sys.argv[1]),Path(sys.argv[2])); "
        "q=QSettings(); "
        "print(json.dumps({'file':q.fileName(),'world':str(WorldStorageSettings(q).active_world_path())}))"
    )
    output = subprocess.run(
        [sys.executable, "-c", script, str(world), str(settings)],
        check=True,
        capture_output=True,
        text=True,
    )
    state = json.loads(output.stdout)
    assert Path(state["file"]).is_relative_to(settings)
    assert Path(state["world"]) == world.resolve()
