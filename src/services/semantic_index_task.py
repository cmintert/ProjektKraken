"""Yielding desktop index jobs with database-free background inference."""

from __future__ import annotations

import logging
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import islice
from threading import Event
from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal, Slot

from src.services.search_service import (
    REBUILD_BATCH_SIZE,
    SearchIndexStorage,
    create_provider,
    get_llm_settings_from_qsettings,
)

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService
    from src.services.search_service import EmbeddingProvider
    from src.services.worker_semantic_index_service import SemanticIndexNotifications

logger = logging.getLogger(__name__)
Document = tuple[str, str, str, dict[str, str]]


@dataclass
class RebuildJob:
    """Session-only bounded scan and terminal counters for a rebuild."""

    scope: str
    exclusions: list[str]
    types: deque[str]
    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    after: str = ""
    retries: deque[tuple[str, str]] = field(default_factory=deque)
    total: int = 0
    indexed: int = 0
    unchanged: int = 0
    failed: int = 0


class EmbeddingRunner:
    """Own a provider exclusively on a single inference executor."""

    def __init__(self, settings: dict[str, Any], cancelled: Event) -> None:
        """Capture provider settings without loading a model."""
        self.settings = settings
        self.cancelled = cancelled
        self.provider: EmbeddingProvider | None = None

    def run(self, texts: list[str]) -> dict[str, Any]:
        """Initialize or embed without touching the application database."""
        if self.cancelled.is_set():
            return {"cancelled": True}
        if self.provider is None:
            settings = self.settings
            local = settings["provider"] == "sentence-transformers"
            self.provider = create_provider(
                provider_name=settings["provider"],
                model=settings["st_model"] if local else settings["lm_model"],
                url=settings["lm_url"],
                api_key=settings["lm_api_key"],
                timeout=settings["lm_timeout"],
                settings=settings,
            )
        # Dimension discovery can itself invoke inference. Keep it here too.
        dimension = self.provider.get_dimension()
        vectors = self.provider.embed(texts) if texts else None
        return {
            "model": self.provider.get_model_name(),
            "dimension": dimension,
            "vectors": vectors,
        }


class SemanticIndexTask(QObject):
    """Schedule short database stages around one background inference batch."""

    _next = Signal()
    _ready = Signal(dict)
    state_changed = Signal(dict)

    def __init__(
        self, database: DatabaseService, notifications: SemanticIndexNotifications
    ) -> None:
        """Create lazily on the database thread, never before worker migration."""
        super().__init__()
        self.database = database
        self.notifications = notifications
        self.session = str(uuid.uuid4())
        self.cancelled = Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="index")
        self.runner = EmbeddingRunner(get_llm_settings_from_qsettings(), self.cancelled)
        self.storage: SearchIndexStorage | None = None
        self.pending: dict[tuple[str, str], list[str]] = {}
        self.rebuilds: deque[RebuildJob] = deque()
        self.active: RebuildJob | None = None
        self.busy = False
        self._scheduled = False
        self._next.connect(self.step, Qt.ConnectionType.QueuedConnection)
        self._ready.connect(self.receive, Qt.ConnectionType.QueuedConnection)

    def enqueue(self, identities: list[tuple[str, str]], exclusions: list[str]) -> None:
        """Replace pending requests for the same saved identity."""
        for kind, identifier in identities:
            if kind not in {"entity", "event"}:
                self.notifications.error_occurred(f"Unknown object type: {kind}")
                continue
            self.pending[kind, identifier] = list(exclusions)
        self.schedule()

    def rebuild(self, scope: str, exclusions: list[str]) -> None:
        """Coalesce identical rebuilds and serialize different scopes."""
        if scope not in {"all", "entity", "event"}:
            self.notifications.error_occurred(f"Unknown object type: {scope}")
            self.notifications.rebuild_finished(0, 0, 1)
            return
        jobs = list(self.rebuilds)
        if self.active is not None:
            jobs.append(self.active)
        if any(j.scope == scope and j.exclusions == exclusions for j in jobs):
            return
        types = deque(["entity", "event"] if scope == "all" else [scope])
        job = RebuildJob(scope, list(exclusions), types)
        self.rebuilds.append(job)
        self.state(job, "queued")
        self.schedule()

    def schedule(self) -> None:
        """Queue one continuation, leaving foreground worker messages room."""
        if not self._scheduled and not self.cancelled.is_set():
            self._scheduled = True
            self._next.emit()

    def state(self, job: RebuildJob, state: str) -> None:
        """Publish detached session-scoped lifecycle information."""
        snapshot = {
            "session": self.session,
            "job_id": job.identifier,
            "state": state,
            "database": str(self.database.db_path),
        }
        self.state_changed.emit(snapshot)
        self.notifications.job_state(snapshot)

    def close(self) -> None:
        """Invalidate work before database cleanup without waiting for inference."""
        self.cancelled.set()
        self.pending.clear()
        jobs = list(self.rebuilds)
        if self.active is not None:
            jobs.append(self.active)
        for job in jobs:
            self.state(job, "cancelled")
        self.rebuilds.clear()
        self.active = None
        self.executor.shutdown(wait=False, cancel_futures=True)

    def submit(self, texts: list[str], context: dict[str, Any]) -> None:
        """Submit only detached text and receive completion through Qt's queue."""
        self.busy = True
        future = self.executor.submit(self.runner.run, texts)

        def completed(result: Future[dict[str, Any]]) -> None:
            if self.cancelled.is_set():
                return
            try:
                payload = {**context, **result.result()}
            except Exception:
                logger.exception("Semantic indexing inference failed")
                payload = {**context, "error": True}
            try:
                self._ready.emit(payload)
            except RuntimeError:
                # Shutdown can destroy the receiver while a provider is retiring.
                pass

        future.add_done_callback(completed)

    @Slot()
    def step(self) -> None:
        """Prepare at most one batch, then yield or wait for inference."""
        self._scheduled = False
        if self.cancelled.is_set() or self.busy:
            return
        if not self.pending and self.active is None and not self.rebuilds:
            return
        try:
            if self.storage is None:
                self.submit([], {})
                return
            if self.pending:
                kind, identifier = next(iter(self.pending))
                exclusions = self.pending[kind, identifier]
                identities = list(
                    islice(
                        (
                            key
                            for key, value in self.pending.items()
                            if key[0] == kind and value == exclusions
                        ),
                        REBUILD_BATCH_SIZE,
                    )
                )
                for key in identities:
                    del self.pending[key]
                self.prepare(kind, [key[1] for key in identities], exclusions, None)
                return
            self.advance_rebuild()
        except Exception:
            logger.exception("Semantic indexing preparation failed")
            self.fail()

    def advance_rebuild(self) -> None:
        """Read a keyset page without materializing an entire world's text."""
        if self.active is None:
            if not self.rebuilds:
                return
            self.active = self.rebuilds.popleft()
            self.active.total = sum(
                self.database.require_connection()
                .execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                )
                .fetchone()[0]
                for table in (
                    "entities" if kind == "entity" else "events"
                    for kind in self.active.types
                )
            )
            self.state(self.active, "running")
        job = self.active
        if job.retries:
            kind, identifier = job.retries.popleft()
            self.prepare(kind, [identifier], job.exclusions, job)
            return
        if not job.types:
            self.finish()
            self.schedule()
            return
        kind = job.types[0]
        table = "entities" if kind == "entity" else "events"
        rows = (
            self.database.require_connection()
            .execute(
                f"SELECT id FROM {table} WHERE id > ? ORDER BY id LIMIT ?",  # noqa: S608
                (job.after, REBUILD_BATCH_SIZE),
            )
            .fetchall()
        )
        if not rows:
            job.types.popleft()
            job.after = ""
            self.schedule()
            return
        job.after = rows[-1][0]
        self.prepare(kind, [row[0] for row in rows], job.exclusions, job)

    def prepare(
        self,
        kind: str,
        identifiers: list[str],
        exclusions: list[str],
        job: RebuildJob | None,
    ) -> None:
        """Snapshot text with the same builders used by synchronous indexing."""
        assert self.storage is not None
        items = []
        for identifier in identifiers:
            item = self.storage._prepare_item_for_batch(kind, identifier, exclusions)
            if item is None:
                if job is not None:
                    job.unchanged += 1
            else:
                items.append(item)
        if items:
            self.submit(
                [item[1] for item in items],
                {
                    "kind": kind,
                    "items": items,
                    "exclusions": exclusions,
                    "rebuild": job is not None,
                },
            )
        else:
            self.progress()
            self.schedule()

    @Slot(dict)
    def receive(self, result: dict[str, Any]) -> None:
        """Validate and commit results exclusively on the database worker."""
        self.busy = False
        if self.cancelled.is_set():
            return
        if result.get("error"):
            self.fail()
            return
        try:
            if self.storage is None:
                if not result["model"] or result["dimension"] <= 0:
                    raise ValueError("Invalid provider metadata")
                self.storage = SearchIndexStorage(
                    self.database.require_connection(),
                    result["model"],
                    result["dimension"],
                )
            else:
                self.persist(result)
            self.progress()
            self.schedule()
        except Exception:
            logger.exception("Semantic indexing persistence failed")
            self.fail()

    def persist(self, result: dict[str, Any]) -> None:
        """Reject changed/deleted objects and atomically store accepted vectors."""
        assert self.storage is not None
        if (result["model"], result["dimension"]) != (
            self.storage.model,
            self.storage.dimension,
        ):
            raise ValueError("Provider metadata changed during indexing")
        items: list[Document] = result["items"]
        vectors = np.asarray(result["vectors"], dtype=np.float32)
        if vectors.shape != (len(items), self.storage.dimension):
            raise ValueError("Unexpected embedding batch shape")
        if not np.isfinite(vectors).all():
            raise ValueError("Non-finite embedding batch")
        kind, exclusions = result["kind"], result["exclusions"]
        accepted, positions = [], []
        unchanged = 0
        connection = self.database.require_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            for position, item in enumerate(items):
                current = self.storage._prepare_item_for_batch(
                    kind, item[0], exclusions
                )
                if current is None:
                    unchanged += 1
                    continue
                if current[2] != item[2]:
                    if result["rebuild"] and self.active is not None:
                        self.active.retries.append((kind, item[0]))
                    else:
                        self.pending.setdefault((kind, item[0]), exclusions)
                    continue
                accepted.append(current)
                positions.append(position)
            indexed, _ = self.storage.store_vectors(kind, accepted, vectors[positions])
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        if result["rebuild"] and self.active is not None:
            self.active.indexed += indexed
            self.active.unchanged += unchanged

    def progress(self) -> None:
        """Report completed work against the scanned candidate count."""
        if self.active is not None:
            job = self.active
            done = job.indexed + job.unchanged + job.failed
            total = max(job.total, done)
            percentage = min(99, int(done * 100 / total)) if total else 0
            self.notifications.rebuild_progress(done, total, percentage)

    def finish(self) -> None:
        """Publish one terminal result for the active rebuild."""
        assert self.active is not None
        job, self.active = self.active, None
        done = job.indexed + job.unchanged + job.failed
        self.notifications.rebuild_progress(done, done, 100)
        self.state(job, "completed")
        self.notifications.rebuild_finished(job.indexed, job.unchanged, job.failed)

    def fail(self) -> None:
        """Stop this session's queued jobs after one provider/storage failure."""
        self.notifications.error_occurred(
            "Semantic indexing failed. Check diagnostics."
        )
        jobs = list(self.rebuilds)
        if self.active is not None:
            jobs.append(self.active)
        for job in jobs:
            self.state(job, "failed")
            self.notifications.rebuild_finished(
                job.indexed, job.unchanged, job.failed + 1
            )
        self.active = None
        self.rebuilds.clear()
        self.pending.clear()
