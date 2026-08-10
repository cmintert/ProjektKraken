"""Serializable contracts for AI-assisted description generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskIntent(str, Enum):
    """Authoring purpose of a task template."""

    CREATE = "create"
    UPDATE = "update"
    GENERAL = "general"


class TaskTemplateSource(str, Enum):
    """Ownership and mutability of a task template."""

    BUILT_IN = "built_in"
    WORLD = "world"


@dataclass(frozen=True)
class TaskTemplate:
    """Serializable task prompt available to description-generation widgets."""

    template_id: str
    name: str
    description: str
    intent: TaskIntent
    content: str
    source: TaskTemplateSource = TaskTemplateSource.WORLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskTemplate":
        """Build a template from a portable preferences snapshot."""
        intent_value = str(data.get("intent", TaskIntent.GENERAL.value))
        source_value = str(data.get("source", TaskTemplateSource.WORLD.value))
        try:
            intent = TaskIntent(intent_value)
        except ValueError:
            intent = TaskIntent.GENERAL
        try:
            source = TaskTemplateSource(source_value)
        except ValueError:
            source = TaskTemplateSource.WORLD
        return cls(
            template_id=str(data.get("template_id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            intent=intent,
            content=str(data.get("content", "")),
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable template snapshot."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "intent": self.intent.value,
            "content": self.content,
            "source": self.source.value,
        }


class GenerationApplyMode(str, Enum):
    """How an approved generation should be applied to an editor."""

    REPLACE = "replace"
    APPEND = "append"
    DISCARD = "discard"


@dataclass(frozen=True)
class GenerationRequest:
    """Serializable input contract for one description-generation task."""

    prompt: dict[str, str]
    max_tokens: int = 512
    temperature: float = 0.7
    db_path: str | None = None
    rag_limit: int = 3
    exclude_names: tuple[str, ...] = ()
    target_id: str | None = None
    source_hash: str | None = None
    object_type: str | None = None
    active_map_id: str | None = None
    playhead_date: float | None = None
    spatial_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-safe snapshot for queued boundaries."""
        return {
            "prompt": dict(self.prompt),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "db_path": self.db_path,
            "rag_limit": self.rag_limit,
            "exclude_names": list(self.exclude_names),
            "target_id": self.target_id,
            "source_hash": self.source_hash,
            "object_type": self.object_type,
            "active_map_id": self.active_map_id,
            "playhead_date": self.playhead_date,
            "spatial_enabled": self.spatial_enabled,
        }


@dataclass(frozen=True)
class ModelReply:
    """A provider-neutral model reply which preserves the API response shape.

    ``content`` is the exact user-visible text returned by the model. Reasoning,
    tool calls, and completion metadata are kept separate so they cannot leak
    into an entity or event description.
    """

    content: str
    reasoning_content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    system_fingerprint: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_provider_result(cls, result: dict[str, Any]) -> "ModelReply":
        """Create a reply from the provider dictionary contract."""
        text = result.get("text", "")
        reasoning = result.get("reasoning_content", "")
        return cls(
            content=text if isinstance(text, str) else str(text),
            reasoning_content=(
                reasoning if isinstance(reasoning, str) else str(reasoning)
            ),
            tool_calls=list(result.get("tool_calls") or []),
            finish_reason=result.get("finish_reason"),
            usage=dict(result.get("usage") or {}),
            model=str(result.get("model") or ""),
            system_fingerprint=result.get("system_fingerprint"),
            provider_metadata=dict(result.get("provider_metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "content": self.content,
            "reasoning_content": self.reasoning_content,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "model": self.model,
            "system_fingerprint": self.system_fingerprint,
            "provider_metadata": self.provider_metadata,
        }


@dataclass(frozen=True)
class GenerationReviewResult:
    """The user's reviewed text and explicit editor action."""

    action: GenerationApplyMode
    text: str
    rating: int = 0
    comment: str = ""
    target_id: str | None = None
    source_hash: str | None = None
    reply: ModelReply | None = None


@dataclass(frozen=True)
class AIGenerationPreferences:
    """Portable, versioned creative preferences stored inside a world."""

    version: int = 2
    persona: str = ""
    max_tokens: int = 512
    temperature_percent: int = 70
    rag_enabled: bool = True
    rag_limit: int = 3
    spatial_enabled: bool = False
    filter_reasoning: bool = True
    audit_enabled: bool = False
    selected_entity_template_id: str = ""
    selected_event_template_id: str = ""
    entity_prompt_draft: str = ""
    event_prompt_draft: str = ""
    custom_task_templates: tuple[TaskTemplate, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIGenerationPreferences":
        """Load known fields while tolerating newer schema versions."""
        legacy_id = str(data.get("selected_template_id", ""))
        legacy_map = {
            "description_default": "create_complete_description",
            "description_detailed": "expand_grounded_detail",
            "description_concise": "condense_essential_version",
            "fantasy_worldbuilder": "",
        }
        migrated_id = legacy_map.get(legacy_id, legacy_id)
        raw_templates = data.get("custom_task_templates", [])
        templates = tuple(
            template
            for raw in raw_templates
            if isinstance(raw, dict)
            and (template := TaskTemplate.from_dict(raw)).template_id
            and template.source == TaskTemplateSource.WORLD
        )
        return cls(
            version=int(data.get("version", 1)),
            persona=str(data.get("persona", "")),
            max_tokens=int(data.get("max_tokens", 512)),
            temperature_percent=int(data.get("temperature_percent", 70)),
            rag_enabled=bool(data.get("rag_enabled", True)),
            rag_limit=int(data.get("rag_limit", 3)),
            spatial_enabled=bool(data.get("spatial_enabled", False)),
            filter_reasoning=bool(data.get("filter_reasoning", True)),
            audit_enabled=bool(data.get("audit_enabled", False)),
            selected_entity_template_id=str(
                data.get("selected_entity_template_id", migrated_id)
            ),
            selected_event_template_id=str(
                data.get("selected_event_template_id", migrated_id)
            ),
            entity_prompt_draft=str(data.get("entity_prompt_draft", "")),
            event_prompt_draft=str(data.get("event_prompt_draft", "")),
            custom_task_templates=templates,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "version": self.version,
            "persona": self.persona,
            "max_tokens": self.max_tokens,
            "temperature_percent": self.temperature_percent,
            "rag_enabled": self.rag_enabled,
            "rag_limit": self.rag_limit,
            "spatial_enabled": self.spatial_enabled,
            "filter_reasoning": self.filter_reasoning,
            "audit_enabled": self.audit_enabled,
            "selected_entity_template_id": self.selected_entity_template_id,
            "selected_event_template_id": self.selected_event_template_id,
            "entity_prompt_draft": self.entity_prompt_draft,
            "event_prompt_draft": self.event_prompt_draft,
            "custom_task_templates": [
                template.to_dict() for template in self.custom_task_templates
            ],
        }


def apply_reviewed_generation(
    current_text: str,
    result: GenerationReviewResult,
) -> str:
    """Apply an explicit review action without parsing control text."""
    if result.action == GenerationApplyMode.REPLACE:
        return result.text
    if result.action == GenerationApplyMode.APPEND:
        return f"{current_text}\n\n{result.text}" if current_text else result.text
    return current_text
