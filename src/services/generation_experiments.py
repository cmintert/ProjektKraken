"""Session-local asynchronous experiments using the shared generation worker."""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from typing import Any
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Qt, Signal

from src.core.ai_generation import (
    AIGenerationPreferences,
    GenerationRequest,
    PreparedGeneration,
)
from src.core.description_date_policy import find_description_dates
from src.core.generation_experiment import fingerprint, render_variant
from src.core.generation_quality import (
    assessment_dict,
    estimate_tokens,
    output_allowance,
)
from src.core.mcp_access import MAX_RESULT_BYTES, McpFailure
from src.services.generation_embeddings import (
    LocalGenerationEmbeddings,
    LoopbackSession,
    OfflineGenerationEmbeddings,
)
from src.services.generation_worker import GenerationWorker
from src.services.llm_provider import (
    get_provider_settings_from_qsettings,
)
from src.services.prompt_builder import PromptBuilder, build_retrieval_query
from src.services.rag_service import RAGService
from src.services.reasoning_filter import filter_reasoning_tags
from src.services.search_service import (
    EmbeddingProvider,
    get_llm_settings_from_qsettings,
)
from src.services.task_template_catalog import TaskTemplateCatalog

MAX_KEY_CHARS = 128
MAX_STORAGE_BYTES = 32 * 1024 * 1024


class GenerationExperiments(QObject):
    """Keep all public state on the GUI thread, inference in an owned executor."""

    changed = Signal()
    prepared = Signal(str)
    _finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an initially empty, disabled session store."""
        super().__init__(parent)
        self.entries: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, tuple[str, str]] = {}
        self.epoch = 0
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KrakenTrial")
        self._busy = threading.Event()
        self._cancel = threading.Event()
        self._worker: GenerationWorker | None = None
        self._active_id = ""
        self._finished.connect(self._accept, Qt.ConnectionType.QueuedConnection)

    def reset(self) -> None:
        """Revoke stored evidence immediately, retaining draining worker ownership."""
        self.epoch += 1
        self.cancel_active()
        self.entries.clear()
        self.keys.clear()

    def cancel_active(self) -> None:
        """Stop active provider work without waiting on the UI."""
        self._cancel.set()
        if self._worker is not None:
            self._worker.cancel()

    def reserve(self, args: dict[str, Any]) -> tuple[str, bool]:
        """Reserve idempotent preparation admission before queued DB capture."""
        key = str(args.get("idempotency_key", ""))
        if not key or len(key) > MAX_KEY_CHARS:
            raise McpFailure("INVALID_INPUT")
        signature = fingerprint(args)
        if key in self.keys:
            previous, identifier = self.keys[key]
            if previous != signature:
                raise McpFailure("INVALID_INPUT", "IDEMPOTENCY_CONFLICT")
            return identifier, False
        if self._busy.is_set() or any(
            entry["state"] == "preparing" for entry in self.entries.values()
        ):
            raise McpFailure("BUSY")
        identifier = str(uuid.uuid4())
        self.entries[identifier] = {
            "experiment_id": identifier,
            "state": "preparing",
            "trials": {},
            "keys": {},
        }
        self.keys[key] = signature, identifier
        return identifier, True

    def prepare(
        self,
        identifier: str,
        snapshot: dict[str, Any],
        args: dict[str, Any],
        database: str,
        world_id: str,
    ) -> None:
        """Capture private provider configuration and schedule source preparation."""
        entry = self.entries[identifier]
        settings = get_provider_settings_from_qsettings("lmstudio", world_id)
        settings["_embedding"] = get_llm_settings_from_qsettings()
        for field in ("generate_url", "embed_url"):
            url = urlsplit(str(settings.get(field, "")))
            if url.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise McpFailure("UNAVAILABLE", "LOCAL_PROVIDER_REQUIRED")
        entry["snapshot_revision"] = snapshot["revision"]
        self._launch(
            identifier, None, self._prepare, snapshot, args, database, settings
        )

    def _prepare(
        self,
        snapshot: dict[str, Any],
        args: dict[str, Any],
        database: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        prefs = AIGenerationPreferences.from_dict(snapshot["preferences"])
        subject = snapshot["subject"]
        operation = str(args.get("operation", "custom"))
        task = str(args.get("task", ""))
        template_id = args.get("template_id")
        if template_id:
            templates = (
                *TaskTemplateCatalog().built_in_templates(),
                *prefs.custom_task_templates,
            )
            operation = next(
                (t.operation for t in templates if t.template_id == template_id),
                operation,
            )
            task = next(
                (t.content for t in templates if t.template_id == template_id), ""
            )
        editing = operation in {"revise", "condense"}

        def selected(key: str, default: bool) -> bool:
            value = args.get(key)
            return default if value is None else bool(value)

        authoring_enabled = selected("include_world_context", not editing)
        prefs = replace(
            prefs,
            rag_enabled=selected(
                "include_retrieved", prefs.rag_enabled and not editing
            ),
            spatial_enabled=selected(
                "include_spatial", prefs.spatial_enabled and not editing
            ),
        )
        if not task.strip():
            raise McpFailure("INVALID_INPUT", "TASK_REQUIRED")
        context = {
            "name": subject.get("name", ""),
            "type": subject.get("type", ""),
            "existing_description": subject.get("description", ""),
            "object_type": args["kind"],
            "object_id": args["target_id"],
        }
        builder = PromptBuilder(prefs.persona or None)
        if snapshot.get("lore_date_caption"):
            context["lore_date"] = snapshot["lore_date_caption"]
        if args["kind"] == "entity":
            context["entity_context_mode"] = args.get("context_mode", "all_history")
        task = builder.substitute_variables(task, context)
        details = builder.build_context_string(context)
        prompt = builder.construct_prompt(
            details,
            task,
            include_authoring_placeholder=authoring_enabled,
            include_rag_placeholder=prefs.rag_enabled,
            include_spatial_placeholder=bool(args.get("active_map_id"))
            and prefs.spatial_enabled,
            object_type=args["kind"],
        )
        request = GenerationRequest(
            prompt,
            max_tokens=(
                output_allowance(str(subject.get("description", "")), operation)
                if prefs.budget_mode == "auto"
                else prefs.max_tokens
            ),
            temperature=prefs.temperature_percent / 100,
            db_path=database,
            target_id=args["target_id"],
            object_type=args["kind"],
            rag_enabled=prefs.rag_enabled,
            rag_limit=prefs.rag_limit,
            retrieval_query=build_retrieval_query(task, context),
            authoring_context_enabled=authoring_enabled,
            include_undated=bool(args.get("include_undated", False)),
            operation=operation,
            budget_mode=prefs.budget_mode,
            entity_context_mode=args.get("context_mode", "all_history"),
            authoring_date=args.get("lore_day"),
            active_map_id=args.get("active_map_id"),
            spatial_enabled=bool(args.get("active_map_id")) and prefs.spatial_enabled,
            playhead_date=args.get("lore_day"),
        )
        embedding: EmbeddingProvider | None = None
        config = settings.pop("_embedding")
        dated = (
            request.object_type == "event"
            or request.entity_context_mode != "all_history"
        )
        if prefs.rag_enabled and (request.include_undated or not dated):
            if config["provider"] == "lmstudio":
                url = config["lm_url"] or "http://localhost:1234/v1/embeddings"
                if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
                    raise McpFailure("UNAVAILABLE", "LOCAL_PROVIDER_REQUIRED")
                embedding = LocalGenerationEmbeddings(config)
            else:
                embedding = OfflineGenerationEmbeddings(
                    config["st_model"] or "all-MiniLM-L6-v2", self._cancel.is_set
                )
        worker = GenerationWorker(
            None,
            prompt,
            512,
            0.7,
            request=request,
            rag_factory=lambda path: RAGService(path, embedding_provider=embedding),
        )
        self._worker = worker
        if self._cancel.is_set():
            worker.cancel()
        try:
            prepared = worker.prepare_context()
        finally:
            if isinstance(embedding, OfflineGenerationEmbeddings):
                embedding.helper.close()
            if isinstance(embedding, LocalGenerationEmbeddings):
                embedding.transport.close()
        blocks = {"subject": details, "task": task}
        if prepared.authoring_context:
            blocks["authoring"] = prepared.authoring_context
        if prepared.rag_context:
            blocks["retrieved"] = prepared.rag_context
        if prepared.spatial_context:
            blocks["spatial"] = prepared.spatial_context
        return {
            "prepared": prepared.to_dict(),
            "request": request.to_dict(),
            "blocks": blocks,
            "settings": settings,
            "filter_reasoning": prefs.filter_reasoning,
            "baseline": prepared.prompt,
            "parameters": {
                "operation": operation,
                "model": settings.get("generation_model", ""),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "context_mode": request.entity_context_mode,
                "lore_day": request.authoring_date,
                "active_map_id": request.active_map_id,
                "rag_enabled": request.rag_enabled,
            },
            "baseline_hash": fingerprint(prepared.prompt),
            "source_references": prepared.source_references,
            "context_warnings": list(worker.context_warnings),
            "month_names": snapshot.get("month_names", []),
            "source": {
                "kind": args["kind"],
                "id": args["target_id"],
                "description": subject.get("description", ""),
            },
        }

    def _launch(self, identifier: str, trial: str | None, fn: Any, *args: Any) -> None:
        self._busy.set()
        self._active_id = identifier
        self._cancel = threading.Event()
        epoch = self.epoch
        cancel = self._cancel

        def run() -> None:
            value: Any = None
            error = ""

            def timeout() -> None:
                cancel.set()
                if self._worker is not None:
                    self._worker.cancel()

            timer = threading.Timer(300, timeout)
            timer.start()
            try:
                value = fn(*args)
            except McpFailure as exc:
                error = exc.reason_code or exc.code
            except Exception:
                error = "GENERATION_FAILED"
            finally:
                timer.cancel()
                self._worker = None
                self._busy.clear()
            self._finished.emit(
                (epoch, identifier, trial, value, error, cancel.is_set())
            )

        self._pool.submit(run)

    def _accept(self, response: Any) -> None:
        epoch, identifier, trial, value, error, cancelled = response
        if epoch != self.epoch or identifier not in self.entries:
            return
        entry = self.entries[identifier]
        if entry["state"] in {"failed", "cancelled"}:
            return
        target = entry if trial is None else entry["trials"][trial]
        target["state"] = (
            "cancelled"
            if cancelled
            else "failed"
            if error
            else ("ready" if trial is None else "completed")
        )
        if error:
            target["error"] = error
        if value and not cancelled and not error:
            if trial is None:
                entry["state"] = "preparing"
                entry["_candidate"] = value
                self.prepared.emit(identifier)
                return
            target.update(value)
            total = sum(
                len(json.dumps(self.public(key)).encode()) for key in self.entries
            )
            if total > MAX_STORAGE_BYTES:
                target.clear()
                target.update(state="failed", error="RESULT_TOO_LARGE")
        self.changed.emit()

    def publish(self, identifier: str, revision: str) -> None:
        """Publish only after fresh verification by the live database owner."""
        entry = self.entries.get(identifier)
        if entry is None or entry["state"] != "preparing":
            return
        candidate = entry.pop("_candidate", None)
        if revision != entry["snapshot_revision"] or candidate is None:
            entry.update(state="failed", error="WORLD_CHANGED")
        else:
            entry.update(candidate)
            entry["state"] = "ready"
            total = sum(
                len(json.dumps(self.public(key)).encode()) for key in self.entries
            )
            if total > MAX_STORAGE_BYTES:
                for key in candidate:
                    entry.pop(key, None)
                entry.update(state="failed", error="RESULT_TOO_LARGE")
        self.changed.emit()

    def start(self, identifier: str, args: dict[str, Any]) -> dict[str, Any]:
        """Start one idempotent trial using frozen evidence and settings."""
        entry = self.entries[identifier]
        key = args.get("idempotency_key", "")
        signature = fingerprint(args)
        if not isinstance(key, str) or not key or len(key) > MAX_KEY_CHARS:
            raise McpFailure("INVALID_INPUT")
        if key in entry["keys"]:
            old, trial = entry["keys"][key]
            if old != signature:
                raise McpFailure("INVALID_INPUT", "IDEMPOTENCY_CONFLICT")
            return {"trial_id": trial}
        if entry["state"] != "ready" or self._busy.is_set():
            raise McpFailure("BUSY")
        prompt = render_variant(
            entry["baseline"], entry["blocks"], args.get("variant") or {}
        )
        trial = str(uuid.uuid4())
        entry["trials"][trial] = {
            "trial_id": trial,
            "state": "running",
            "prompt": prompt,
            "variant": args.get("variant") or {},
        }
        entry["keys"][key] = signature, trial
        self._launch(
            identifier, trial, self._generate, entry, prompt, args.get("variant") or {}
        )
        self.changed.emit()
        return {"trial_id": trial, "state": "running"}

    def _generate(
        self,
        entry: dict[str, Any],
        prompt: dict[str, str],
        variant: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prepared = replace(
            PreparedGeneration.from_dict(entry["prepared"]), prompt=prompt
        )
        request_data = {**entry["request"], "prepared": prepared}
        if variant and "max_tokens" in variant:
            request_data["max_tokens"] = variant["max_tokens"]
        request = GenerationRequest(**request_data)
        from src.services.providers.lmstudio_provider import LMStudioProvider

        settings = entry["settings"]
        transport = LoopbackSession()
        transport.trust_env = False
        provider = LMStudioProvider(
            model=settings.get("generation_model") or None,
            generate_url=settings["generate_url"],
            embed_url=settings["embed_url"],
            api_key=settings.get("api_key") or None,
            timeout=settings.get("timeout", 30),
            use_chat_api=settings.get("use_chat_api", True),
            max_retries=1,
            request_session=transport,
        )
        worker = GenerationWorker(provider, prompt, 512, 0.7, request=request)
        self._worker = worker
        if self._cancel.is_set():
            worker.cancel()
        replies: list[Any] = []
        errors: list[str] = []
        worker.generation_complete.connect(
            replies.append, Qt.ConnectionType.DirectConnection
        )
        worker.generation_error.connect(
            errors.append, Qt.ConnectionType.DirectConnection
        )
        started = time.monotonic()
        try:
            worker.run()
        finally:
            transport.close()
        if not replies:
            raise McpFailure("UNAVAILABLE", "GENERATION_FAILED")
        reply = replies[0]
        presented = (
            filter_reasoning_tags(reply.content)
            if entry["filter_reasoning"]
            else reply.content
        )
        return {
            **assessment_dict(
                entry.get("source", {}).get("description", ""),
                presented,
                reply.finish_reason,
            ),
            "effective_max_tokens": request.max_tokens,
            "excluded_block_ids": (variant or {}).get("exclude", []),
            "block_token_estimates": {
                key: estimate_tokens(value)
                for key, value in entry.get("blocks", {}).items()
                if key not in (variant or {}).get("exclude", [])
            },
            "model_context_window": None,
            "prompt_tokens_estimate": {
                key: estimate_tokens(value) for key, value in prompt.items()
            },
            "raw_text": reply.content,
            "presented_text": presented,
            "model": reply.model,
            "usage": reply.usage,
            "finish_reason": reply.finish_reason,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "prompt_hash": fingerprint(prompt),
            "policy_findings": [
                asdict(item)
                for item in find_description_dates(
                    presented,
                    known_date_values=prepared.description_date_values,
                    month_names=entry.get("month_names", ()),
                )
            ],
        }

    def public(self, identifier: str) -> dict[str, Any]:
        """Project experiment evidence without private settings or worker objects."""
        entry = self.entries[identifier]
        return copy.deepcopy(
            {
                key: value
                for key, value in entry.items()
                if key not in {"settings", "request", "prepared", "keys", "_candidate"}
            }
        )

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch short public job operations on the owning thread."""
        identifier = args.get("experiment_id", "")
        if identifier not in self.entries:
            raise McpFailure("NOT_FOUND")
        entry = self.entries[identifier]
        expected = args.get("expected_revision")
        if expected is not None and expected != entry.get("snapshot_revision"):
            raise McpFailure("WORLD_CHANGED")
        if tool == "start_generation_trial":
            return self.start(identifier, args)
        if tool == "cancel_generation_experiment":
            entry["state"] = "cancelled"
            if self._active_id == identifier:
                self.cancel_active()
            for trial in entry["trials"].values():
                if trial["state"] == "running":
                    trial["state"] = "cancelled"
            return {"state": "cancelled"}
        data = self.public(identifier)
        if tool == "get_generation_trial":
            if args.get("trial_id") not in entry["trials"]:
                raise McpFailure("NOT_FOUND")
            data = data["trials"][args["trial_id"]]
        text = json.dumps(data, ensure_ascii=False)
        offset = args.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise McpFailure("INVALID_INPUT")
        page = {
            "state": data["state"],
            "content": text[offset : offset + 8000],
            "offset": offset,
            "next_offset": offset + 8000 if offset + 8000 < len(text) else None,
        }
        size = 8000
        while len(json.dumps(page).encode()) > MAX_RESULT_BYTES - 1024:
            size //= 2
            page["content"] = text[offset : offset + size]
            page["next_offset"] = offset + size if offset + size < len(text) else None
        return page
