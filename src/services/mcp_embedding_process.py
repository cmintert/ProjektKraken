"""Revocable offline embedding process retained only for one sharing session."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.core.mcp_access import McpFailure
from src.services.mcp_embedding_protocol import encode_payload

MAX_RESPONSE_BYTES = 256 * 1024 * 1024


class EmbeddingProcess:
    """Load once during preparation; serialize warm requests off the DB thread."""

    def __init__(self) -> None:
        """Start a local helper without loading models in the application process."""
        executable = Path(sys.executable)
        command = (
            [str(executable.with_name("KrakenMCP.exe")), "--semantic-helper"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "src.services.mcp_semantic_helper"]
        )
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "TOKENIZERS_PARALLELISM": "false",
                "OMP_NUM_THREADS": "1",
            },
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._responses: queue.Queue[bytes | None] = queue.Queue(maxsize=2)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        threading.Thread(target=self._read, daemon=True, name="McpEmbeddings").start()

    def _read(self) -> None:
        """Drain framed results; keep native model loading outside Qt threads."""
        assert self._process.stdout is not None
        try:
            while not self._closed.is_set():
                data = self._process.stdout.readline(MAX_RESPONSE_BYTES + 1)
                if not data or len(data) > MAX_RESPONSE_BYTES:
                    break
                self._responses.put_nowait(data)
        except (OSError, ValueError, queue.Full):
            pass
        finally:
            self.close()
            try:
                self._responses.put_nowait(None)
            except queue.Full:
                pass
            self._process.wait()
            self._process.stdout.close()
            if self._process.stdin is not None:
                try:
                    self._process.stdin.close()
                except OSError:
                    pass

    def close(self) -> None:
        """Revoke immediately, including an encoding call currently in progress."""
        self._closed.set()
        if self._process.poll() is None:
            try:
                self._process.kill()
            except OSError:
                pass

    @property
    def available(self) -> bool:
        """Distinguish retained vectors from a usable warm model process."""
        return not self._closed.is_set() and self._process.poll() is None

    def encode(
        self, payload: dict[str, Any], expired: Callable[[], bool], timeout: float
    ) -> dict[str, Any]:
        """Await a bounded response and abandon the process on any failure."""
        deadline = time.monotonic() + timeout

        def checkpoint() -> None:
            if expired() or time.monotonic() >= deadline:
                raise McpFailure("TIMEOUT")
            if self._closed.is_set():
                raise McpFailure("MODEL_UNAVAILABLE")

        acquired = False
        try:
            while not acquired:
                checkpoint()
                acquired = self._lock.acquire(timeout=0.05)
            checkpoint()
            assert self._process.stdin is not None
            data = encode_payload({**payload, "keep_alive": True})
            self._process.stdin.write(data)
            self._process.stdin.flush()
            while True:
                checkpoint()
                try:
                    response = self._responses.get(timeout=0.05)
                except queue.Empty:
                    continue
                if response is None:
                    raise McpFailure("MODEL_UNAVAILABLE")
                return json.loads(response)
        except Exception:
            self.close()
            raise
        finally:
            if acquired:
                self._lock.release()
