"""Protected per-user discovery for explicitly enabled local MCP sessions."""

from __future__ import annotations

import importlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from src.core.mcp_access import McpFailure
from src.services.mcp_session import McpSession

_ACL_ENTRIES = 2
_MAX_DESCRIPTOR = 4096
_MAX_PORT = 65535
_MIN_TOKEN = 40
_MAX_TOKEN = 64


def _module(name: str) -> Any:
    """Load Windows-only APIs lazily, including in the console package."""
    return importlib.import_module(name)


def discovery_directory() -> Path:
    """Use OS-owned local application data, never a world or plugin path."""
    if os.name == "nt":
        shell = _module("win32com.shell.shell")
        return Path(shell.SHGetFolderPath(0, 28, 0, 0)) / "ProjektKraken" / "MCP"
    return Path.home() / ".local" / "state" / "projektkraken" / "mcp"


def reject_links(path: Path) -> None:
    """Reject symbolic links and Windows reparse points throughout the path."""
    for component in (path, *path.parents):
        if component.exists() or component.is_symlink():
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise McpFailure("UNSAFE_DISCOVERY_PATH")


def _sid() -> Any:
    security = _module("win32security")
    api = _module("win32api")
    token = security.OpenProcessToken(api.GetCurrentProcess(), 8)
    try:
        return security.GetTokenInformation(token, security.TokenUser)[0]
    finally:
        token.Close()


def protect(path: Path, *, install: bool) -> None:
    """Install or verify current-user/SYSTEM access, failing closed on error."""
    reject_links(path)
    if os.name != "nt":
        if install:
            path.chmod(0o700 if path.is_dir() else 0o600)
        info = path.stat()
        if info.st_uid != getattr(os, "getuid")() or info.st_mode & 0o077:
            raise McpFailure("UNSAFE_DISCOVERY_PERMISSIONS")
        return
    security = _module("win32security")
    user = security.ConvertSidToStringSid(_sid())
    if install:
        descriptor = security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            f"D:P(A;OICI;FA;;;{user})(A;OICI;FA;;;SY)", 1
        )
        security.SetFileSecurity(
            str(path), 4 | security.PROTECTED_DACL_SECURITY_INFORMATION, descriptor
        )
    descriptor = security.GetFileSecurity(str(path), 4)
    acl = descriptor.GetSecurityDescriptorDacl()
    if acl is None or acl.GetAceCount() != _ACL_ENTRIES:
        raise McpFailure("UNSAFE_DISCOVERY_PERMISSIONS")
    for index in range(acl.GetAceCount()):
        ace = acl.GetAce(index)
        if ace[0][0] != 0 or security.ConvertSidToStringSid(ace[2]) not in {
            user,
            "S-1-5-18",
        }:
            raise McpFailure("UNSAFE_DISCOVERY_PERMISSIONS")


class SessionDiscovery:
    """Publish one user's session while retaining exclusive ownership."""

    def __init__(self, directory: Path | None = None) -> None:
        """Allow an isolated directory for security tests, not client input."""
        self.directory = directory or discovery_directory()
        self._lock: Any = None
        self._published = False

    def acquire(self) -> None:
        """Secure storage before taking a nonblocking per-user ownership lock."""
        reject_links(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        protect(self.directory, install=True)
        lock_path = self.directory / "owner.lock"
        reject_links(lock_path)
        if os.name == "nt":
            files = _module("win32file")
            self._lock = files.CreateFile(
                str(lock_path), 0xC0000000, 0, None, 4, 0x80, None
            )
        else:
            fcntl = _module("fcntl")

            self._lock = lock_path.open("a+b")
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception:
                self._lock.close()
                self._lock = None
                raise

    def publish(self, port: int, session: McpSession) -> None:
        """Atomically publish encrypted session data only after server readiness."""
        if self._lock is None or not session.active:
            raise McpFailure("UNAVAILABLE")
        payload = json.dumps(
            {
                "port": port,
                "token": session.token,
                "generation": session.generation,
            }
        ).encode()
        if os.name == "nt":
            payload = _module("win32crypt").CryptProtectData(
                payload, "Kraken MCP session", None, None, None, 1
            )
        target = self.directory / "session.bin"
        reject_links(target)
        fd, temporary = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
            protect(Path(temporary), install=True)
            os.replace(temporary, target)
            self._published = True
        finally:
            Path(temporary).unlink(missing_ok=True)

    def read(self) -> dict[str, Any]:
        """Read protected current-session coordinates; never trust arbitrary URLs."""
        try:
            target = self.directory / "session.bin"
            reject_links(self.directory)
            self.directory.stat()
            protect(self.directory, install=False)
            reject_links(target)
            target.stat()
            protect(target, install=False)
            if target.stat().st_size > _MAX_DESCRIPTOR:
                raise ValueError("Oversized descriptor")
            payload = target.read_bytes()
            if os.name == "nt":
                payload = _module("win32crypt").CryptUnprotectData(
                    payload, None, None, None, 1
                )[1]
            data = json.loads(payload)
            if (
                type(data["port"]) is not int
                or not 1 <= data["port"] <= _MAX_PORT
                or not isinstance(data["token"], str)
                or not _MIN_TOKEN <= len(data["token"]) <= _MAX_TOKEN
                or not isinstance(data["generation"], str)
            ):
                raise ValueError("Invalid descriptor")
            return dict(data)
        except FileNotFoundError as exc:
            raise McpFailure("UNAVAILABLE", "NO_ACTIVE_SESSION") from exc
        except ImportError as exc:
            raise McpFailure("UNAVAILABLE", "LOCAL_RUNTIME_UNAVAILABLE") from exc
        except McpFailure as exc:
            raise McpFailure("UNAVAILABLE", "UNSAFE_DISCOVERY") from exc
        except PermissionError as exc:
            raise McpFailure("UNAVAILABLE", "UNSAFE_DISCOVERY") from exc
        except Exception as exc:
            error_number = getattr(exc, "winerror", None)
            if error_number is None and exc.args and type(exc.args[0]) is int:
                error_number = exc.args[0]
            reason = {
                2: "NO_ACTIVE_SESSION",
                3: "NO_ACTIVE_SESSION",
                5: "UNSAFE_DISCOVERY",
            }.get(
                error_number if isinstance(error_number, int) else 0,
                "INVALID_DISCOVERY",
            )
            raise McpFailure("UNAVAILABLE", reason) from exc

    def close(self) -> None:
        """Remove only this publisher's descriptor before releasing ownership."""
        try:
            if self._lock is not None and self._published:
                reject_links(self.directory / "session.bin")
                (self.directory / "session.bin").unlink(missing_ok=True)
        finally:
            self._published = False
            if self._lock is not None:
                self._lock.Close() if os.name == "nt" else self._lock.close()
                self._lock = None
