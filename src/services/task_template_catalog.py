"""Read-only bundled task templates and portable world-template validation."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from pathlib import Path

from src.core.ai_generation import (
    AI_GENERATION_PREFERENCES_VERSION,
    AIGenerationPreferences,
    TaskIntent,
    TaskTemplate,
    TaskTemplateSource,
)
from src.services.prompt_loader import PromptLoader

SUPPORTED_TEMPLATE_VARIABLES = frozenset(
    {"name", "type", "description", "lore_date"}
)
LEGACY_BUNDLED_IDS = frozenset(
    {
        "description_default",
        "description_detailed",
        "description_concise",
        "fantasy_worldbuilder",
    }
)
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class TaskTemplateValidationError(ValueError):
    """Raised when a world template cannot be safely persisted."""


class TaskTemplateCatalog:
    """Load bundled tasks and merge them with one world's custom tasks."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        legacy_dir: Path | None = None,
    ) -> None:
        """Initialize built-in and optional world task-template sources."""
        package_root = Path(__file__).parent.parent.parent
        self.built_in_dir = built_in_dir or (
            package_root / "default_assets" / "templates" / "task_prompts"
        )
        self.legacy_dir = legacy_dir or (
            package_root / "default_assets" / "templates" / "system_prompts"
        )

    def built_in_templates(self) -> tuple[TaskTemplate, ...]:
        """Return one immutable entry for each bundled task family."""
        loader = PromptLoader(str(self.built_in_dir))
        latest_by_id: dict[str, dict[str, object]] = {}
        for metadata in loader.list_templates():
            template_id = str(metadata["template_id"])
            current = latest_by_id.get(template_id)
            if current is None or self._version_key(str(metadata["version"])) > (
                self._version_key(str(current["version"]))
            ):
                latest_by_id[template_id] = metadata

        templates = []
        for template_id in sorted(latest_by_id):
            loaded = loader.load_template(template_id)
            intent_raw = str(loaded.metadata.get("intent", TaskIntent.GENERAL.value))
            try:
                intent = TaskIntent(intent_raw)
            except ValueError:
                intent = TaskIntent.GENERAL
            templates.append(
                TaskTemplate(
                    template_id=loaded.template_id,
                    name=loaded.name,
                    description=str(loaded.metadata.get("description", "")),
                    intent=intent,
                    content=loaded.content,
                    source=TaskTemplateSource.BUILT_IN,
                )
            )
        return tuple(templates)

    def merge(
        self, custom_templates: tuple[TaskTemplate, ...]
    ) -> tuple[TaskTemplate, ...]:
        """Return bundled tasks followed by validated world tasks."""
        built_ins = self.built_in_templates()
        world = tuple(
            replace(template, source=TaskTemplateSource.WORLD)
            for template in custom_templates
        )
        return built_ins + world

    def validate_world_template(
        self,
        template: TaskTemplate,
        existing: tuple[TaskTemplate, ...] = (),
    ) -> None:
        """Validate one mutable world template and its name uniqueness."""
        if template.source != TaskTemplateSource.WORLD:
            raise TaskTemplateValidationError("Bundled templates are read-only")
        try:
            uuid.UUID(template.template_id)
        except (ValueError, AttributeError) as exc:
            raise TaskTemplateValidationError(
                "World templates require a valid UUID"
            ) from exc
        if not template.name.strip():
            raise TaskTemplateValidationError("Template name is required")
        if not template.content.strip():
            raise TaskTemplateValidationError("Template content is required")
        duplicate = next(
            (
                candidate
                for candidate in existing
                if candidate.template_id != template.template_id
                and candidate.name.strip().casefold() == template.name.strip().casefold()
            ),
            None,
        )
        if duplicate is not None:
            raise TaskTemplateValidationError(
                f"A world template named '{template.name.strip()}' already exists"
            )
        unsupported = sorted(
            set(_PLACEHOLDER_RE.findall(template.content))
            - SUPPORTED_TEMPLATE_VARIABLES
        )
        if unsupported:
            variables = ", ".join(f"{{{name}}}" for name in unsupported)
            raise TaskTemplateValidationError(
                f"Unsupported template variables: {variables}"
            )

    def migrate_preferences(
        self, preferences: AIGenerationPreferences
    ) -> AIGenerationPreferences:
        """Upgrade v1 preferences and import non-bundled legacy templates once."""
        if preferences.version >= AI_GENERATION_PREFERENCES_VERSION:
            return preferences

        imported = list(preferences.custom_task_templates)
        known_names = {template.name.strip().casefold() for template in imported}
        loader = PromptLoader(str(self.legacy_dir))
        latest_ids = {
            str(item["template_id"])
            for item in loader.list_templates()
            if str(item["template_id"]) not in LEGACY_BUNDLED_IDS
        }
        for legacy_id in sorted(latest_ids):
            legacy = loader.load_template(legacy_id)
            name = legacy.name.strip() or "Imported Task"
            if name.casefold() in known_names:
                continue
            imported_template = TaskTemplate(
                template_id=str(uuid.uuid4()),
                name=name,
                description=str(legacy.metadata.get("description", "")),
                intent=TaskIntent.GENERAL,
                content=legacy.content,
                source=TaskTemplateSource.WORLD,
            )
            imported.append(imported_template)
            known_names.add(name.casefold())

        return replace(
            preferences,
            version=AI_GENERATION_PREFERENCES_VERSION,
            custom_task_templates=tuple(imported),
        )

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        """Return a sortable numeric version key."""
        return tuple(int(part) for part in version.split("."))
