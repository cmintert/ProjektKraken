"""GUI probes must never select registry storage or a credential backend."""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.ci_fast


def test_probe_settings_redirect_named_and_default_stores_in_fresh_process():
    source = """
import tempfile
from pathlib import Path
from scripts.gui_probe_settings import install_probe_settings
with tempfile.TemporaryDirectory() as directory:
    install_probe_settings(directory)
    from PySide6.QtCore import QSettings
    from src.services.local_settings import LocalSettingsAdapter
    from src.services import secret_store
    for store in [QSettings(), QSettings('ProbeOrg','ProbeApp'),
                  LocalSettingsAdapter().settings]:
        assert store.format() == QSettings.Format.IniFormat
        assert Path(store.fileName()).resolve().is_relative_to(Path(directory))
        assert not store.fallbacksEnabled()
        store.setValue('probe', 123)
        store.sync()
        assert Path(store.fileName()).exists()
    assert QSettings('ProbeOrg','ProbeApp').value('probe', type=int) == 123
    assert secret_store.get_api_key('openai') == ''
    try:
        secret_store.set_api_key('openai', 'not-a-real-key')
    except RuntimeError:
        pass
    else:
        raise AssertionError('Credential write was allowed')
    try:
        QSettings('untrusted.ini', QSettings.Format.NativeFormat)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Unsupported storage overload was allowed')
"""
    subprocess.run(
        [sys.executable, "-c", source], check=True, capture_output=True, text=True
    )
