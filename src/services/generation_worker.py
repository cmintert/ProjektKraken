"""Shared background preparation and inference for desktop and MCP generation."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

from src.core.ai_generation import GenerationRequest, ModelReply, PreparedGeneration
from src.core.authoring_context import EntityAuthoringContext
from src.core.entity_context_mode import EntityContextMode
from src.core.operation_trace import safe_stack
from src.services.authoring_context_builder import (
    format_entity_authoring_context,
    format_event_authoring_context,
    lookup_entity_authoring_context,
    lookup_event_authoring_context,
)
from src.services.generation_context_policy import select_entity_evidence
from src.services.rag_service import RAGService, retrieval_exclusion_kwargs
from src.services.spatial_context_builder import lookup_spatial_context

logger = logging.getLogger(__name__)
GenerationPrompt = str | dict[str, str]


def _normalize_generation_prompt(prompt: object) -> GenerationPrompt:
    """Validate and copy a prompt crossing into the generation worker.

    Args:
        prompt: Legacy string prompt or structured prompt object.

    Returns:
        A string prompt or a detached ``system``/``user`` prompt dictionary.

    Raises:
        TypeError: If the prompt does not match the supported contract.

    """
    if isinstance(prompt, str):
        return prompt
    if not isinstance(prompt, dict):
        raise TypeError("Generation prompt must be a string or dictionary")

    system_prompt = prompt.get("system", "")
    user_prompt = prompt.get("user")
    if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
        raise TypeError(
            "Structured generation prompts require string 'system' and 'user' values"
        )
    return {"system": system_prompt, "user": user_prompt}


class GenerationWorker(QThread):
    """Worker thread for LLM text generation.

    Runs generation in background to avoid blocking the UI.
    """

    # chunk_received = Signal(str)  # Removed as per user request
    context_prepared = Signal(object)
    generation_complete = Signal(object)  # ModelReply
    generation_error = Signal(str)  # Error message

    def __init__(
        self,
        provider: Any,
        prompt: GenerationPrompt,
        max_tokens: int,
        temperature: float,
        db_path: Optional[str] = None,
        rag_limit: int = 3,
        exclude_names: Optional[list[str]] = None,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
        active_map_id: Optional[str] = None,
        spatial_enabled: bool = False,
        request: GenerationRequest | None = None,
        preview_only: bool = False,
        rag_factory: Callable[[str], RAGService] | None = None,
    ) -> None:
        """Initialize generation worker.

        Args:
            provider: LLM provider instance.
            prompt: Text prompt (str) or structured prompt (dict with
                'system' and 'user' keys) for generation.
            max_tokens: Maximum tokens to generate.
            temperature: Temperature parameter (0.0-2.0).
            db_path: Optional path to database for RAG context.
            rag_limit: Number of RAG items to retrieve.
            exclude_names: Entity/event names to exclude from RAG hits.
            object_id: UUID of the entity/event being generated for. Required
                together with ``active_map_id`` for spatial context.
            object_type: ``"entity"`` or ``"event"``.
            active_map_id: ID of the map currently selected in the map widget,
                used as the strict primary map for spatial context lookup.
            spatial_enabled: When True, the worker attempts to inject a
                ``[Spatial Context]`` block in place of ``{{SPATIAL_CONTEXT}}``.

        """
        super().__init__()
        self.preview_only = preview_only
        self.rag_factory = rag_factory
        self.prepared = request.prepared if request else None
        self.entity_context_mode = (
            request.entity_context_mode if request else "all_history"
        )
        self.include_undated = request.include_undated if request else True
        self.provider = provider
        raw_prompt: object = request.prompt if request is not None else prompt
        self.prompt = _normalize_generation_prompt(raw_prompt)
        if request is not None:
            self.max_tokens = request.max_tokens
            self.temperature = request.temperature
            self.db_path = request.db_path
            self.rag_limit = request.rag_limit
            self.retrieval_query = request.retrieval_query
            self.exclude_names = list(request.exclude_names)
            self.object_id = request.target_id
            self.object_type = request.object_type
            self.active_map_id = request.active_map_id
            self.playhead_date = request.playhead_date
            self.spatial_enabled = request.spatial_enabled
            self.rag_enabled = request.rag_enabled
            self.authoring_context_enabled = request.authoring_context_enabled
            self.authoring_date = request.authoring_date
        else:
            self.max_tokens = max_tokens
            self.temperature = temperature
            self.db_path = db_path
            self.rag_limit = rag_limit
            self.retrieval_query = ""
            self.exclude_names = exclude_names or []
            self.object_id = object_id
            self.object_type = object_type
            self.active_map_id = active_map_id
            self.playhead_date = None
            self.spatial_enabled = spatial_enabled
            self.rag_enabled = db_path is not None
            self.authoring_context_enabled = False
            self.authoring_date = None
        # Populated during run() when spatial context is actually injected;
        # read by the widget to drive the post-generation transparency label.
        self.rag_context_used: Optional[str] = None
        self.spatial_context_used: Optional[str] = None
        self.authoring_context_used: Optional[str] = None
        self.description_date_values: tuple[float, ...] = ()
        self.source_references: tuple[tuple[str, str], ...] = ()
        self.context_warnings: list[str] = []
        self._cancelled = False

    def _apply_rag_to_prompt(self) -> None:
        """Inject RAG context into the prompt."""
        # Check if RAG is useful/enabled
        dated = self.object_type == "event" or self.entity_context_mode != "all_history"
        if dated and not self.include_undated:
            self.context_warnings.append(
                "Undated retrieved prose excluded at the selected date."
            )
            if isinstance(self.prompt, dict):
                self.prompt["user"] = self.prompt["user"].replace("{{RAG_CONTEXT}}", "")
            return
        if not self.rag_enabled or not self.db_path:
            return

        rag_context = ""
        user_msg = ""
        prompt = self.prompt

        # Extract user message for context key
        if isinstance(prompt, dict):
            user_msg = prompt.get("user", "")
        else:
            user_msg = prompt

        # A zero limit disables retrieval even when a legacy prompt contains
        # the placeholder. Empty request queries retain legacy prompt behavior.
        should_run = self.rag_limit > 0

        if should_run:
            try:
                # Use modular RAGService
                rag_service = (
                    self.rag_factory(self.db_path)
                    if self.rag_factory
                    else RAGService(self.db_path)
                )
                retrieval_query = self.retrieval_query or user_msg
                logger.info(
                    "RAG: Searching context (query_chars=%d limit=%d)",
                    len(retrieval_query),
                    self.rag_limit,
                )
                rag_context = rag_service.get_context(
                    retrieval_query,
                    top_k=self.rag_limit,
                    **retrieval_exclusion_kwargs(
                        self.object_type, self.object_id, self.exclude_names
                    ),
                )
                self.source_references = getattr(rag_service, "source_references", ())
                retrieval_error = getattr(rag_service, "last_error", None)
                if isinstance(retrieval_error, str):
                    self.context_warnings.append(retrieval_error)

                if rag_context:
                    logger.info("RAG: Found context (chars=%d)", len(rag_context))
                else:
                    logger.info("RAG: No context found or returned empty.")

            except Exception as e:
                logger.error(
                    "RAG service failure error_type=%s stack=%s",
                    type(e).__name__,
                    safe_stack(e),
                )
                rag_context = ""

        # Inject logic
        if isinstance(prompt, dict):
            if "{{RAG_CONTEXT}}" in prompt["user"]:
                replacement = (
                    f"[Retrieved Context]\n{rag_context}" if rag_context else ""
                )
                prompt["user"] = prompt["user"].replace("{{RAG_CONTEXT}}", replacement)
            elif rag_context:
                # Prepend if no placeholder but content found
                prompt["user"] = f"[Context]\n{rag_context}\n\n" + prompt["user"]
        else:
            # String prompt
            if "{{RAG_CONTEXT}}" in prompt:
                replacement = (
                    f"[Retrieved Context]\n{rag_context}" if rag_context else ""
                )
                prompt = prompt.replace("{{RAG_CONTEXT}}", replacement)
            elif rag_context:
                prompt = f"[Context]\n{rag_context}\n\n" + prompt

        self.prompt = prompt
        self.rag_context_used = rag_context or None

        if rag_context:
            logger.debug(f"Applied RAG context: {len(rag_context)} chars")

    def _lookup_entity_context(self) -> EntityAuthoringContext | None:
        assert self.db_path is not None and self.object_id is not None
        if self.entity_context_mode == "all_history":
            return lookup_entity_authoring_context(self.db_path, self.object_id)
        return lookup_entity_authoring_context(
            self.db_path,
            self.object_id,
            mode=EntityContextMode(self.entity_context_mode),
            context_date=self.authoring_date,
        )

    def _apply_authoring_context_to_prompt(self) -> None:
        """Inject deterministic authoring context using a read-only connection."""
        placeholder = "{{AUTHORING_CONTEXT}}"
        prompt = self.prompt
        user_msg = prompt.get("user", "") if isinstance(prompt, dict) else prompt
        if placeholder not in user_msg:
            return

        context_text: Optional[str] = None
        if (
            self.authoring_context_enabled
            and self.object_type == "entity"
            and self.entity_context_mode != "all_history"
            and (not self.db_path or not self.object_id or self.authoring_date is None)
        ):
            raise ValueError("Select a saved Entity and viewing date for World Context")
        if (
            self.authoring_context_enabled
            and self.db_path
            and self.object_id
            and self.object_type in {"entity", "event"}
        ):
            if self.object_type == "event":
                event_context = lookup_event_authoring_context(
                    self.db_path,
                    self.object_id,
                    context_date=self.authoring_date,
                    active_map_id=self.active_map_id,
                )
                if event_context is not None:
                    context_text = format_event_authoring_context(event_context)
                    values = [event_context.context_date]
                    values.extend(
                        item.lore_date
                        for item in (
                            *event_context.previous_events,
                            *event_context.concurrent_events,
                            *event_context.next_events,
                        )
                        if item.lore_date is not None
                    )
                    values.extend(
                        value
                        for relation in (
                            *event_context.direct_relations,
                            *event_context.neighborhood_relations,
                        )
                        for value in (relation.valid_from, relation.valid_to)
                        if value is not None
                    )
                    self.description_date_values = tuple(values)
            else:
                entity_context = self._lookup_entity_context()
                if entity_context is None and self.entity_context_mode != "all_history":
                    raise ValueError(
                        "World Context is unavailable. Refresh before generating."
                    )
                if entity_context is not None:
                    entity_context = select_entity_evidence(
                        entity_context,
                        include_undated=self.include_undated,
                    )
                    if (
                        entity_context.mode != "all_history"
                        and not self.include_undated
                    ):
                        self.context_warnings.append(
                            "Undated baseline references excluded."
                        )
                    context_text = format_entity_authoring_context(entity_context)
                    values = [
                        item.event.lore_date
                        for item in entity_context.event_appearances
                        if item.event.lore_date is not None
                    ]
                    values.extend(
                        item.lore_date
                        for item in entity_context.mentions
                        if item.lore_date is not None
                    )
                    values.extend(
                        event.lore_date
                        for item in entity_context.co_appearances
                        for event in item.events
                        if event.lore_date is not None
                    )
                    values.extend(
                        value
                        for relation in (
                            *entity_context.temporal_history,
                            *entity_context.neighborhood_relations,
                        )
                        for value in (relation.valid_from, relation.valid_to)
                        if value is not None
                    )
                    if entity_context.context_date is not None:
                        values.append(entity_context.context_date)
                    self.description_date_values = tuple(values)

        self.authoring_context_used = context_text
        if isinstance(prompt, dict):
            prompt["user"] = prompt["user"].replace(placeholder, context_text or "")
        else:
            prompt = prompt.replace(placeholder, context_text or "")
        self.prompt = prompt

    def _apply_spatial_to_prompt(self) -> None:
        """Inject spatial context into the prompt (mirrors ``_apply_rag_to_prompt``).

        Runs synchronously on the worker thread. ``lookup_spatial_context``
        opens its own short-lived SQLite connection so the worker never
        touches the main thread's DB connection. Silently no-ops when
        spatial context is disabled, no DB is available, or the quality
        gate fails.
        """
        placeholder = "{{SPATIAL_CONTEXT}}"
        prompt = self.prompt
        user_msg = prompt.get("user", "") if isinstance(prompt, dict) else prompt
        if placeholder not in user_msg:
            return

        context_text: Optional[str] = None
        if (
            self.spatial_enabled
            and self.db_path
            and self.object_id
            and self.object_type
            and self.active_map_id
        ):
            context_text = lookup_spatial_context(
                self.db_path,
                self.object_id,
                self.object_type,
                self.active_map_id,
                self.playhead_date,
            )

        self.spatial_context_used = context_text
        replacement = context_text if context_text else ""
        if isinstance(prompt, dict):
            prompt["user"] = prompt["user"].replace(placeholder, replacement)
        else:
            prompt = prompt.replace(placeholder, replacement)
        self.prompt = prompt

        if context_text:
            logger.debug(
                f"Applied spatial context: {len(context_text)} chars for "
                f"{self.object_type}={self.object_id} on map={self.active_map_id}"
            )

    def prepare_context(self) -> PreparedGeneration:
        """Resolve sources once, or restore the exact frozen reviewed messages."""
        if self.prepared is None:
            self._apply_authoring_context_to_prompt()
            if not self._cancelled:
                self._apply_rag_to_prompt()
            if not self._cancelled:
                self._apply_spatial_to_prompt()
            prompt = (
                self.prompt if isinstance(self.prompt, dict) else {"user": self.prompt}
            )
            self.prepared = PreparedGeneration(
                dict(prompt),
                self.authoring_context_used,
                self.rag_context_used,
                self.spatial_context_used,
                self.description_date_values,
                self.source_references,
                tuple(self.context_warnings),
            )
        prepared = self.prepared
        self.prompt = dict(prepared.prompt)
        self.authoring_context_used = prepared.authoring_context
        self.rag_context_used = prepared.rag_context
        self.spatial_context_used = prepared.spatial_context
        self.description_date_values = prepared.description_date_values
        return prepared

    def run(self) -> None:
        """Run generation in background thread."""
        try:
            prepared = self.prepare_context()
            if self._cancelled:
                return
            if self.preview_only:
                self.context_prepared.emit(prepared.to_dict())
                return

            if isinstance(self.prompt, dict):
                sys_len = len(self.prompt.get("system", ""))
                usr_len = len(self.prompt.get("user", ""))
                logger.debug(
                    f"Final prompt (dict): system={sys_len} chars, user={usr_len} chars"
                )
            # Check if provider supports streaming
            meta = self.provider.metadata()
            if meta.get("supports_streaming", False):
                # Use streaming generation
                self._run_streaming()
            else:
                # Fallback to non-streaming
                self._run_non_streaming()
        except Exception as e:
            logger.error(
                "Generation failed error_type=%s stack=%s",
                type(e).__name__,
                safe_stack(e),
            )
            if not self._cancelled:
                self.generation_error.emit(str(e))

    def _run_streaming(self) -> None:
        """Run streaming generation."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def generate() -> ModelReply:
                """Execute streaming generation and preserve its reply fields."""
                full_text = ""
                reasoning_content = ""
                tool_calls: list[dict[str, Any]] = []
                finish_reason = None
                usage: dict[str, Any] = {}
                model = ""
                system_fingerprint = None
                provider_metadata: dict[str, Any] = {}
                async for chunk in self.provider.stream_generate(
                    self.prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ):
                    delta = chunk.get("delta", "")
                    full_text += delta
                    reasoning_content += chunk.get("reasoning_delta", "")
                    tool_calls.extend(chunk.get("tool_calls_delta") or [])
                    finish_reason = chunk.get("finish_reason") or finish_reason
                    usage = chunk.get("usage") or usage
                    model = str(chunk.get("model") or model)
                    system_fingerprint = (
                        chunk.get("system_fingerprint") or system_fingerprint
                    )
                    provider_metadata.update(chunk.get("provider_metadata") or {})
                return ModelReply(
                    content=full_text,
                    reasoning_content=reasoning_content,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    usage=usage,
                    model=model,
                    system_fingerprint=system_fingerprint,
                    provider_metadata=provider_metadata,
                )

            result = loop.run_until_complete(generate())
            loop.close()

            if not self._cancelled:
                if not result.content:
                    raise ValueError("The model returned no visible content")
                self.generation_complete.emit(result)

        except Exception as e:
            logger.error(
                "Streaming generation failed error_type=%s stack=%s",
                type(e).__name__,
                safe_stack(e),
            )
            if not self._cancelled:
                self.generation_error.emit(f"Streaming failed: {e}")

    def _run_non_streaming(self) -> None:
        """Run non-streaming generation."""
        try:
            result = self.provider.generate(
                prompt=self.prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            if not self._cancelled:
                reply = ModelReply.from_provider_result(result)
                if not reply.content:
                    raise ValueError("The model returned no visible content")
                self.generation_complete.emit(reply)

        except Exception as e:
            logger.error(
                "Non-streaming generation failed error_type=%s stack=%s",
                type(e).__name__,
                safe_stack(e),
            )
            if not self._cancelled:
                self.generation_error.emit(f"Generation failed: {e}")

    def cancel(self) -> None:
        """Cancel the generation."""
        self._cancelled = True
        cancel_request = getattr(self.provider, "cancel_current_request", None)
        if callable(cancel_request):
            cancel_request()
