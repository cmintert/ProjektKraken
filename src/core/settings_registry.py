"""Descriptions and detached edit state for genuine Kraken preferences."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal

Scope = Literal["kraken", "world"]


@dataclass(frozen=True)
class SettingDefinition:
    """A discoverable preference; persistence belongs to its adapter."""

    id: str
    label: str
    category: str
    scope: Scope
    default: Any
    description: str = ""
    aliases: tuple[str, ...] = ()
    resettable: bool = True
    restart_required: bool = False
    secret: bool = False

    @property
    def backend(self) -> str:
        """Identify the specialized adapter, without owning its storage."""
        return (
            "secret" if self.secret else "world" if self.scope == "world" else "local"
        )

    def validate(self, value: Any) -> None:
        """Reject incompatible scalar snapshots before any backend is written."""
        if self.default is not None and type(value) is not type(self.default):
            raise ValueError(f"{self.label}: invalid value type.")
        if self.id == "world.excluded_attributes" and any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError("Index exclusions must be attribute names.")

    def matches(self, query: str) -> bool:
        """Search descriptions, never preference values or credentials."""
        haystack = " ".join(
            (self.label, self.description, self.category, self.scope, *self.aliases)
        ).casefold()
        return all(word in haystack for word in query.casefold().split())


@dataclass
class SettingsDraft:
    """Keep edits independently of views and detect concurrent changes."""

    baseline: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    conflicts: dict[str, Any] = field(default_factory=dict)

    def replace(self, values: dict[str, Any]) -> None:
        """Start a new acknowledged snapshot."""
        self.baseline = deepcopy(values)
        self.values = deepcopy(values)
        self.conflicts.clear()

    def changes(self) -> dict[str, Any]:
        """Return only modified values, with independent ownership."""
        return deepcopy(
            {
                key: value
                for key, value in self.values.items()
                if value != self.baseline.get(key)
            }
        )

    def merge(self, current: dict[str, Any]) -> None:
        """Refresh clean fields without overwriting pending edits."""
        dirty = self.changes()
        for key, value in current.items():
            if key in dirty and value == self.baseline.get(key):
                self.conflicts.pop(key, None)
            if key in dirty and value != self.baseline.get(key):
                if value != self.values[key]:
                    self.conflicts[key] = deepcopy(value)
                else:
                    self.acknowledge({key: value})
            elif key not in dirty:
                self.baseline[key] = deepcopy(value)
                self.values[key] = deepcopy(value)

    def resolve(self, key: str, keep_edit: bool) -> None:
        """Accept the external baseline and optionally preserve the edit."""
        value = self.conflicts.pop(key)
        self.baseline[key] = deepcopy(value)
        if not keep_edit:
            self.values[key] = deepcopy(value)

    def acknowledge(self, saved: dict[str, Any]) -> None:
        """Clear only values actually persisted, keeping newer edits dirty."""
        for key, value in saved.items():
            self.baseline[key] = deepcopy(value)
            self.conflicts.pop(key, None)


def _definitions() -> tuple[SettingDefinition, ...]:
    basic = (
        ("appearance.theme", "Default theme", "Appearance", "dark_mode"),
        ("longform_auto_refresh", "Auto-refresh Longform", "Writing", True),
        ("SpellCheck/enabled", "Spell & grammar checking", "Writing", False),
        ("SpellCheck/language", "Spelling language", "Writing", "auto"),
        ("timeline/snap_playhead_to_events", "Snap to Events", "Timeline", False),
        ("analysis/editorial_checks", "Editorial checks", "Analysis", False),
        ("ai_auto_index_on_save", "Automatically index saved entries", "AI", False),
        ("ai_embedding_provider", "Embedding provider", "AI", "sentence-transformers"),
        ("ai_lmstudio_base_url", "LM Studio server", "AI", "http://localhost:1234"),
        ("ai_lmstudio_model", "Embedding model", "AI", ""),
        ("ai_lmstudio_timeout", "LM Studio timeout", "AI", 30),
        ("ai_st_model", "Sentence Transformers model", "AI", "all-MiniLM-L6-v2"),
        ("ai_gen_lmstudio_enabled", "Enable LM Studio generation", "AI", True),
        ("ai_gen_lmstudio_use_chat_api", "LM Studio chat API", "AI", True),
        ("ai_gen_lmstudio_model", "LM Studio generation model", "AI", ""),
        ("ai_gen_openai_enabled", "Enable OpenAI", "AI", False),
        ("ai_gen_openai_model", "OpenAI model", "AI", "gpt-3.5-turbo"),
        ("ai_gen_google_enabled", "Enable Google Vertex AI", "AI", False),
        ("ai_gen_google_project_id", "Google project", "AI", ""),
        ("ai_gen_google_location", "Google location", "AI", "us-central1"),
        ("ai_gen_google_model", "Google model", "AI", "text-bison@001"),
        ("ai_gen_google_credentials_path", "Google credential file", "AI", ""),
        ("ai_gen_anthropic_enabled", "Enable Anthropic", "AI", False),
        ("ai_gen_anthropic_model", "Anthropic model", "AI", "claude-3-haiku-20240307"),
        ("ai_gen_summary_prompt", "Summary prompt", "AI", None),
        ("ai_gen_summary_max_tokens", "Summary token limit", "AI", 2048),
        ("ai_gen_summary_temperature", "Summary temperature", "AI", 0),
        ("backup_enabled", "Enable automatic backups", "Backups & storage", True),
        ("backup_auto_save_interval", "Backup interval", "Backups & storage", 5),
        (
            "backup_auto_save_retention",
            "Automatic backups to keep",
            "Backups & storage",
            12,
        ),
        ("backup_daily_retention", "Daily backups to keep", "Backups & storage", 7),
        ("backup_weekly_retention", "Weekly backups to keep", "Backups & storage", 4),
        ("backup_manual_retention", "Manual backups to keep", "Backups & storage", -1),
        ("backup_verify_after", "Verify backups", "Backups & storage", True),
        ("backup_vacuum_before", "Compact before backup", "Backups & storage", False),
        ("backup_custom_dir", "Backup directory", "Backups & storage", ""),
        ("backup_external_path", "External backup copy", "Backups & storage", ""),
    )
    result = [
        SettingDefinition(key, label, category, "kraken", default)
        for key, label, category, default in basic
    ]
    for provider, label in (
        ("lmstudio", "LM Studio API key"),
        ("openai", "OpenAI API key"),
        ("anthropic", "Anthropic API key"),
        ("languagetool.username", "LanguageTool username"),
        ("languagetool.api_key", "LanguageTool API key"),
    ):
        result.append(
            SettingDefinition(
                f"secret.{provider}",
                label,
                "Writing" if provider.startswith("languagetool") else "AI",
                "kraken",
                "",
                "Stored on this computer in the OS credential store.",
                resettable=False,
                secret=True,
            )
        )
    for key, label, category, default in (
        ("world.theme", "World theme override", "Appearance", ""),
        (
            "world.auto_relations",
            "Auto-create relations from WikiLinks",
            "Writing",
            False,
        ),
        ("world.excluded_attributes", "Semantic-index attribute exclusions", "AI", []),
        ("world.ai", "Creative AI preferences and task templates", "AI", {}),
        ("world.calendar", "Calendar configuration", "Timeline", None),
        ("world.grouping", "Timeline grouping", "Timeline", None),
        ("world.lexicon", "Graph visual lexicon", "Graph", None),
        ("world.tag_colors", "Grouping tag colours", "Timeline", {}),
    ):
        result.append(
            SettingDefinition(
                key,
                label,
                category,
                "world",
                default,
                "Portable configuration saved with this world.",
                aliases=("persona", "prompts", "templates")
                if key == "world.ai"
                else (),
                resettable=key
                not in {"world.ai", "world.calendar", "world.tag_colors"},
            )
        )
    return tuple(result)


SETTINGS = _definitions()
BY_ID = {setting.id: setting for setting in SETTINGS}
