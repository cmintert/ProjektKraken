"""Application preference and credential adapters, with targeted reset policies."""

from __future__ import annotations

import json
import time
from typing import Any

from PySide6.QtCore import QSettings

from src.core.settings import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.core.settings_registry import SETTINGS
from src.services import secret_store

SEED_KEY = "settings_center/legacy_policy_seed_v1"
WORKSPACE_KEYS = (
    "geometry",
    "windowState",
    "window_state",
    "timeline/playhead_time",
    "tag_filter_config",
    "workspace_layout",
    "last_selected_item_id",
    "last_selected_item_type",
)
LEGACY_SECRETS = {
    "lmstudio": "ai_lmstudio_api_key",
    "openai": "ai_gen_openai_api_key",
    "anthropic": "ai_gen_anthropic_api_key",
    "languagetool.username": "SpellCheck/username",
    "languagetool.api_key": "SpellCheck/api_key",
}


class LocalSettingsAdapter:
    """Route known preferences without clearing other persistent local state."""

    def __init__(self, settings: QSettings | None = None) -> None:
        """Initialize detached settings state and explicit dependencies."""
        self.settings = settings or QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

    def legacy_seed(self) -> dict[str, Any]:
        """Freeze legacy policies independently of active-world runtime caches."""
        raw = self.settings.value(SEED_KEY, "")
        if not raw:
            excluded = str(self.settings.value("ai_search_excluded_attrs", "") or "")
            seed = {
                "captured_at": time.time(),
                "auto_relations": self.settings.value(
                    "wiki/auto_create_relations", False, type=bool
                ),
                "excluded_attributes": [
                    x.strip() for x in excluded.split(",") if x.strip()
                ],
            }
            self.settings.setValue(SEED_KEY, json.dumps(seed))
            self.settings.sync()
            return seed
        return dict(json.loads(str(raw)))

    def legacy_ai_preferences(self) -> dict[str, Any]:
        """Capture portable legacy values before loading another world's cache."""
        from src.core.ai_generation import AIGenerationPreferences
        from src.services.prompt_builder import DEFAULT_SYSTEM_PROMPT

        seed_key = "settings_center/legacy_ai_seed_v1"
        stored = self.settings.value(seed_key, "")
        if stored:
            return dict(json.loads(str(stored)))
        defaults = AIGenerationPreferences(persona=DEFAULT_SYSTEM_PROMPT).to_dict()
        keys = {
            "persona": "system_prompt",
            "max_tokens": "max_tokens",
            "temperature_percent": "temperature",
            "rag_enabled": "rag_enabled",
            "rag_limit": "rag_limit",
            "spatial_enabled": "spatial_enabled",
            "filter_reasoning": "filter_reasoning",
            "audit_enabled": "audit_log",
            "selected_entity_template_id": "entity_template_id",
            "selected_event_template_id": "event_template_id",
            "entity_prompt_draft": "entity_prompt",
            "event_prompt_draft": "event_prompt",
        }
        for field, suffix in keys.items():
            defaults[field] = self.settings.value(
                f"ai_gen_{suffix}", defaults[field], type=type(defaults[field])
            )
        self.settings.setValue(seed_key, json.dumps(defaults))
        self.settings.sync()
        return defaults

    def snapshot(self, *, include_secrets: bool = True) -> dict[str, Any]:
        """Read registered values and secure credentials without migrating on view."""
        result: dict[str, Any] = {}
        for definition in SETTINGS:
            if definition.scope != "kraken":
                continue
            if definition.secret:
                if not include_secrets:
                    continue
                provider = definition.id.removeprefix("secret.")
                result[definition.id] = secret_store.get_api_key(provider) or str(
                    self.settings.value(LEGACY_SECRETS[provider], "") or ""
                )
            elif definition.id == "appearance.theme":
                result[definition.id] = self.settings.value(
                    definition.id,
                    QSettings("ProjektKraken", "ThemeSettings").value(
                        "current_theme", definition.default
                    ),
                    type=str,
                )
            elif definition.default is not None:
                result[definition.id] = self.settings.value(
                    definition.id, definition.default, type=type(definition.default)
                )
            else:
                from src.core.summary_data import DEFAULT_SUMMARY_PROMPT

                result[definition.id] = self.settings.value(
                    definition.id, DEFAULT_SUMMARY_PROMPT, type=str
                )
        return result

    def save(self, changes: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Acknowledge local preferences and credentials independently."""
        saved: dict[str, Any] = {}
        errors: list[str] = []
        ordinary = {
            key: value
            for key, value in changes.items()
            if not key.startswith("secret.")
        }
        previous = {key: self.settings.value(key) for key in ordinary}
        for key, value in ordinary.items():
            self.settings.setValue(key, value)
        self.settings.sync()
        if self.settings.status() == QSettings.Status.NoError:
            saved.update(ordinary)
        else:
            for key, value in previous.items():
                if value is None:
                    self.settings.remove(key)
                else:
                    self.settings.setValue(key, value)
            errors.append("Local preferences could not be saved.")
        for key, value in changes.items():
            if key.startswith("secret."):
                provider = key.removeprefix("secret.")
                if secret_store.set_api_key(provider, str(value)):
                    self.settings.remove(LEGACY_SECRETS[provider])
                    saved[key] = value
                else:
                    errors.append(f"Could not save {provider} credentials.")
        self.settings.sync()
        return saved, errors

    def migrate_credentials(self) -> list[str]:
        """Remove legacy plaintext only after acknowledged secure writes."""
        errors = []
        for provider, key in LEGACY_SECRETS.items():
            legacy = str(self.settings.value(key, "") or "")
            if not legacy:
                continue
            stored = secret_store.read_api_key(provider)
            if stored is None or (
                not stored and not secret_store.set_api_key(provider, legacy)
            ):
                errors.append(f"Could not secure {provider} credentials.")
            else:
                self.settings.remove(key)
        self.settings.sync()
        return errors

    def reset_preferences(self) -> None:
        """Reset the preference allowlist; keep all resources and world state."""
        self.legacy_seed()
        for definition in SETTINGS:
            if definition.scope == "kraken" and definition.resettable:
                self.settings.remove(definition.id)
        QSettings("ProjektKraken", "ThemeSettings").remove("current_theme")
        self.settings.setValue("appearance.theme", "dark_mode")
        self.settings.sync()

    def reset_workspace(self) -> None:
        """Reset transient view state, never named layouts or world content."""
        from src.services.workspace_store import WorkspaceStore

        WorkspaceStore(self.settings).reset_view_state()
        for key in WORKSPACE_KEYS:
            self.settings.remove(key)
        self.settings.sync()

    def request_workspace_reset(self) -> None:
        """Apply on next startup, after normal shutdown finishes saving its state."""
        self.settings.setValue("settings_center/reset_workspace_on_start", True)
        self.settings.sync()

    def apply_pending_workspace_reset(self) -> None:
        """Consume the explicit request before the main window loads its state."""
        key = "settings_center/reset_workspace_on_start"
        if self.settings.value(key, False, type=bool):
            self.reset_workspace()
            self.settings.remove(key)
            self.settings.sync()
