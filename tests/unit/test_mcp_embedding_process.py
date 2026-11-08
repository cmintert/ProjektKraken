"""Exercise real process framing, warm reuse and immediate revocation."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.core.mcp_access import McpFailure
from src.services import mcp_embedding_process

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def helper(tmp_path, monkeypatch):
    script = tmp_path / "helper.py"
    script.write_text(
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "for raw in sys.stdin.buffer:\n"
        "    value = json.loads(raw)\n"
        "    if value.get('block'):\n"
        "        Path(value['marker']).touch()\n"
        "        time.sleep(60)\n"
        "    print(json.dumps({'pid':os.getpid(),'value':value}), flush=True)\n",
        encoding="utf-8",
    )
    original = mcp_embedding_process.subprocess.Popen
    processes = []

    def spawn(command, **kwargs):
        process = original([sys.executable, "-u", str(script)], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(mcp_embedding_process.subprocess, "Popen", spawn)
    session = mcp_embedding_process.EmbeddingProcess()
    yield session, processes
    session.close()
    for process in processes:
        process.wait(timeout=5)


def test_warm_requests_reuse_process_and_preserve_unicode(helper):
    session, processes = helper
    first = session.encode({"texts": ["Éowyn 漢字\nsecond line"]}, lambda: False, 5)
    second = session.encode({"texts": ["query"]}, lambda: False, 5)
    assert first["pid"] == second["pid"]
    assert len(processes) == 1
    assert first["value"]["texts"] == ["Éowyn 漢字\nsecond line"]
    assert second["value"]["keep_alive"] is True
    session.close()
    with pytest.raises(McpFailure, match="MODEL_UNAVAILABLE"):
        session.encode({"texts": ["revoked"]}, lambda: False, 5)


def test_revocation_kills_inflight_process(helper, tmp_path, qtbot):
    session, processes = helper
    marker = tmp_path / "started"
    cancelled = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            session.encode,
            {"block": True, "marker": str(marker)},
            cancelled.is_set,
            5,
        )
        qtbot.waitUntil(marker.exists, timeout=3000)
        cancelled.set()
        with pytest.raises(McpFailure, match="TIMEOUT"):
            future.result(timeout=2)
    assert processes[0].wait(timeout=2) is not None
