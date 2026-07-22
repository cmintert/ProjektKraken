"""Tests for bundled and per-world task-template behavior."""

import uuid
from pathlib import Path

import pytest

from src.core.ai_generation import (
    AIGenerationPreferences,
    TaskIntent,
    TaskTemplate,
    TaskTemplateSource,
)
from src.services.task_template_catalog import (
    TaskTemplateCatalog,
    TaskTemplateValidationError,
)


def _world_template(name: str = "World Task", content: str = "Use {name}") -> TaskTemplate:
    return TaskTemplate(
        template_id=str(uuid.uuid4()),
        name=name,
        description="Portable task",
        intent=TaskIntent.GENERAL,
        content=content,
        source=TaskTemplateSource.WORLD,
    )


def _write_legacy(path: Path, template_id: str, name: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                "version: 1.0",
                f"template_id: {template_id}",
                f"name: {name}",
                "description: Legacy custom task",
                "---",
                "",
                "Write {name} using the legacy task.",
            ]
        ),
        encoding="utf-8",
    )


def test_bundled_catalog_contains_only_four_authoring_tasks() -> None:
    templates = TaskTemplateCatalog().built_in_templates()

    assert {template.template_id for template in templates} == {
        "create_complete_description",
        "revise_clarity_flow",
        "expand_grounded_detail",
        "condense_essential_version",
    }
    assert all(template.source == TaskTemplateSource.BUILT_IN for template in templates)
    assert all("Return only the finished description" in template.content for template in templates)


def test_merge_keeps_built_ins_read_only_and_world_template_mutable() -> None:
    custom = _world_template()
    catalog = TaskTemplateCatalog()

    merged = catalog.merge((custom,))

    assert merged[-1] == custom
    assert all(
        template.source == TaskTemplateSource.BUILT_IN for template in merged[:-1]
    )


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("", "Use {name}", "name is required"),
        ("Task", "", "content is required"),
        ("Task", "Use {relations}", "Unsupported template variables"),
    ],
)
def test_validation_rejects_unusable_templates(
    name: str, content: str, message: str
) -> None:
    template = _world_template(name=name, content=content)

    with pytest.raises(TaskTemplateValidationError, match=message):
        TaskTemplateCatalog().validate_world_template(template)


def test_validation_rejects_case_insensitive_duplicate_names() -> None:
    existing = _world_template(name="Continuity Pass")
    duplicate = _world_template(name="continuity pass")

    with pytest.raises(TaskTemplateValidationError, match="already exists"):
        TaskTemplateCatalog().validate_world_template(duplicate, (existing,))


def test_v1_migration_imports_only_unknown_legacy_families(tmp_path: Path) -> None:
    built_in_dir = tmp_path / "builtins"
    legacy_dir = tmp_path / "legacy"
    built_in_dir.mkdir()
    legacy_dir.mkdir()
    _write_legacy(
        legacy_dir / "description_default_v1.0.txt",
        "description_default",
        "Old Default",
    )
    _write_legacy(
        legacy_dir / "personal_voice_v1.0.txt",
        "personal_voice",
        "Personal Voice",
    )
    catalog = TaskTemplateCatalog(built_in_dir=built_in_dir, legacy_dir=legacy_dir)

    migrated = catalog.migrate_preferences(AIGenerationPreferences(version=1))

    assert migrated.version == 2
    assert [item.name for item in migrated.custom_task_templates] == ["Personal Voice"]
    assert migrated.custom_task_templates[0].source == TaskTemplateSource.WORLD
