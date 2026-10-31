"""Fail-closed settings and credential isolation for disposable GUI subprocesses."""

from pathlib import Path
from typing import Any

_installed_root: Path | None = None
_NAMED_SETTINGS_ARGUMENTS = 2


def install_probe_settings(directory: str) -> None:
    """Redirect every supported QSettings overload before project GUI imports.

    setDefaultFormat alone does not affect QSettings(organization, application).
    This helper is process-owned: call once, before importing application modules.
    Unsupported overloads fail rather than falling back to the Windows registry.
    """
    from PySide6 import QtCore

    global _installed_root
    root = Path(directory).resolve()
    if _installed_root is not None:
        if _installed_root != root:
            raise RuntimeError("GUI probe settings are already installed")
        return
    native = QtCore.QSettings
    native.setPath(native.Format.IniFormat, native.Scope.UserScope, str(root))

    class ProbeSettings(native):
        """Use only temporary INI storage, including named application stores."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            if not args:
                organization = (
                    QtCore.QCoreApplication.organizationName() or "KrakenProbe"
                )
                application = QtCore.QCoreApplication.applicationName() or "settings"
            elif len(args) == _NAMED_SETTINGS_ARGUMENTS and all(
                isinstance(value, str) for value in args
            ):
                organization, application = args
            else:
                raise RuntimeError(
                    "Unsupported QSettings overload in isolated GUI probe"
                )
            super().__init__(
                native.Format.IniFormat,
                native.Scope.UserScope,
                organization,
                application,
                **kwargs,
            )
            self.setFallbacksEnabled(False)
            if self.format() != native.Format.IniFormat or not Path(
                self.fileName()
            ).resolve().is_relative_to(root):
                raise RuntimeError("GUI probe attempted settings outside its INI root")

    QtCore.QSettings = ProbeSettings
    _installed_root = root
    # No diagnostic fixture may touch a credential backend, including spell check.
    from src.services import secret_store

    secret_store.get_api_key = lambda _provider: ""
    secret_store.read_api_key = lambda _provider: ""

    def reject_write(_provider: str, _value: str) -> bool:
        raise RuntimeError("Credential writes are disabled in GUI probes")

    secret_store.set_api_key = reject_write
