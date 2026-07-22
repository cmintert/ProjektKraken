"""OS-backed storage for AI provider credentials."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SERVICE_NAME = "ProjektKraken.AI"


def get_api_key(provider_id: str) -> str:
    """Read a provider key from the operating-system credential store."""
    try:
        import keyring

        return keyring.get_password(_SERVICE_NAME, provider_id) or ""
    except Exception as exc:
        logger.warning("Could not read %s credentials: %s", provider_id, exc)
        return ""


def set_api_key(provider_id: str, value: str) -> bool:
    """Store or remove a provider key; return whether the operation succeeded."""
    try:
        import keyring

        if value:
            keyring.set_password(_SERVICE_NAME, provider_id, value)
        else:
            try:
                keyring.delete_password(_SERVICE_NAME, provider_id)
            except keyring.errors.PasswordDeleteError:
                pass
        return True
    except Exception as exc:
        logger.warning("Could not store %s credentials: %s", provider_id, exc)
        return False


def migrate_qsettings_secret(
    settings: Any,
    setting_key: str,
    provider_id: str,
) -> str:
    """Move a legacy plaintext QSettings value into the credential store."""
    stored = get_api_key(provider_id)
    legacy = str(settings.value(setting_key, "") or "")
    if not stored and legacy and set_api_key(provider_id, legacy):
        settings.remove(setting_key)
        return legacy
    if stored and legacy:
        settings.remove(setting_key)
    return stored or legacy
