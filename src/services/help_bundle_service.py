"""Read and validate version-matched offline Help without application state."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from src.core.help_bundle import (
    HELP_BUILD_COMMAND,
    HELP_SCHEMA,
    HelpMetadata,
    HelpPage,
    HelpSearchDocument,
    HelpTopic,
    file_hash,
    source_hashes,
)
from src.core.version import VERSION

ErrorCode = Literal["missing", "invalid", "stale", "version", "path", "topic"]


class HelpBundleError(RuntimeError):
    """A structured failure for the future Help viewer to present accessibly."""

    def __init__(self, code: ErrorCode, detail: str, *, packaged: bool = False) -> None:
        """Include the appropriate local recovery route."""
        self.code = code
        self.detail = detail
        self.recovery = (
            "Reinstall the matching ProjektKraken release."
            if packaged
            else f"Regenerate Help with {HELP_BUILD_COMMAND}."
        )
        super().__init__(f"{detail} {self.recovery}")


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("Expected a list of strings")
    return tuple(value)


def _text(record: dict[str, Any], key: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected nonempty {key}")
    return value


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError("Expected string map")
    return value


class HelpBundleService:
    """Serve only validated local manual files; never build or access world data."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        version: str = VERSION,
        source_root: Path | None = None,
        build_info: Path | None = None,
    ) -> None:
        """Resolve deterministic defaults; explicit roots support build validation."""
        repository = Path(__file__).resolve().parents[2]
        self.packaged = bool(getattr(sys, "frozen", False))
        if root is None:
            root = (
                Path(getattr(sys, "_MEIPASS")) / "help"
                if self.packaged
                else repository / "docs/_build/help"
            )
            if self.packaged:
                build_info = Path(sys.executable).resolve().parent / "build-info.json"
            else:
                source_root = repository
        self.root = root.resolve()
        self.version = version
        self.source_root = source_root
        self.build_info = build_info
        self._manifest: dict[str, Any] | None = None
        self._pages: dict[str, HelpPage] = {}
        self._topics: dict[str, HelpTopic] = {}
        self._hashes: dict[str, str] = {}

    def _error(self, code: ErrorCode, detail: str) -> HelpBundleError:
        return HelpBundleError(code, detail, packaged=self.packaged)

    def validate(self) -> HelpMetadata:
        """Validate shape, every payload, source freshness and package identity."""
        self._manifest = None
        try:
            manifest = _object(self.root / "manifest.json")
            self._load_manifest(manifest)
            self._validate_identity(manifest)
            for name in self._hashes:
                self._resource_path(name)
            self._validate_search()
        except FileNotFoundError as exc:
            raise self._error("missing", "Offline Help is missing.") from exc
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise self._error("invalid", f"Offline Help is invalid: {exc}") from exc
        self._manifest = manifest
        return HelpMetadata(
            manifest["version"], manifest["revision"], manifest["dirty"]
        )

    def _load_manifest(self, manifest: dict[str, Any]) -> None:
        if manifest.get("schema_version") != HELP_SCHEMA:
            raise ValueError("Unsupported Help schema")
        for key in ("version", "revision"):
            if not isinstance(manifest[key], str) or not manifest[key]:
                raise ValueError(f"Invalid {key}")
        if not isinstance(manifest["dirty"], bool):
            raise ValueError("Invalid dirty-source flag")
        self._hashes = _string_map(manifest["payload_hashes"])
        self._pages = {}
        for record in manifest["pages"]:
            page = HelpPage(
                _text(record, "path"),
                _text(record, "title"),
                _strings(record["anchors"]),
            )
            if page.path in self._pages or page.path not in self._hashes:
                raise ValueError("Duplicate or missing page")
            self._pages[page.path] = page
        self._topics = {}
        for record in manifest["topics"]:
            topic = HelpTopic(
                _text(record, "id"),
                _text(record, "page"),
                _text(record, "fragment"),
                _text(record, "title"),
                _text(record, "level"),
                _strings(record["related_ids"]),
                record.get("control_excerpt_target"),
            )
            if topic.id in self._topics or topic.level not in {
                "control",
                "task",
                "concept",
            }:
                raise ValueError("Duplicate or invalid topic")
            page = self._pages[topic.page]
            if topic.fragment not in page.anchors:
                raise ValueError(f"Unresolved topic: {topic.id}")
            if (
                topic.control_excerpt_target
                and topic.control_excerpt_target not in page.anchors
            ):
                raise ValueError(f"Unresolved excerpt: {topic.id}")
            self._topics[topic.id] = topic
        if "manual.home" not in self._topics or "search.json" not in self._hashes:
            raise ValueError("Missing manual fallback or search index")
        if any(
            r not in self._topics for t in self._topics.values() for r in t.related_ids
        ):
            raise ValueError("Unresolved related topic")

    def _validate_identity(self, manifest: dict[str, Any]) -> None:
        if manifest["version"] != self.version:
            raise self._error(
                "version", "Offline Help does not match this app version."
            )
        if self.source_root is not None:
            if _string_map(manifest["source_hashes"]) != source_hashes(
                self.source_root
            ):
                raise self._error(
                    "stale", "Offline Help does not match the current sources."
                )
        if self.build_info is not None:
            info = _object(self.build_info)
            expected = (
                self.version,
                manifest["revision"],
                manifest["dirty"],
                file_hash(self.root / "manifest.json"),
            )
            actual = (
                info["version"],
                info["commit"],
                info["source_dirty"],
                info["help_manifest_sha256"],
            )
            if actual != expected:
                raise self._error("version", "Help and package build identity differ.")

    def _resource_path(self, uri: str) -> Path:
        """Resolve a listed local resource and fragment, checking confinement/hash."""
        parsed = urlsplit(uri)
        name = unquote(parsed.path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or "\\" in name
            or not name
            or Path(name).is_absolute()
            or ".." in Path(name).parts
        ):
            raise self._error("path", "Help resource is outside the offline bundle.")
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root) or name not in self._hashes:
            raise self._error("path", "Help resource is not in the offline manifest.")
        fragment = unquote(parsed.fragment)
        if fragment and (
            name not in self._pages or fragment not in self._pages[name].anchors
        ):
            raise self._error("path", "Unknown Help fragment.")
        try:
            actual_hash = file_hash(path)
        except FileNotFoundError as exc:
            raise self._error("missing", f"Help resource is missing: {name}") from exc
        except OSError as exc:
            raise self._error(
                "invalid", f"Help resource is unreadable: {name}"
            ) from exc
        if actual_hash != self._hashes[name]:
            raise self._error("invalid", f"Help content hash mismatch: {name}")
        return path

    def resource_path(self, uri: str) -> Path:
        """Resolve only after full bundle validation, never after a failed load."""
        self._ensure_valid()
        return self._resource_path(uri)

    def _ensure_valid(self) -> None:
        if self._manifest is None:
            self.validate()

    def resolve_topic(self, topic_id: str) -> HelpTopic:
        """Resolve an ID, using the validated manual home for unknown IDs."""
        self._ensure_valid()
        return self._topics.get(topic_id, self._topics["manual.home"])

    def pages(self) -> tuple[HelpPage, ...]:
        """Return the immutable manual page inventory."""
        self._ensure_valid()
        return tuple(self._pages.values())

    def load_page(self, page: str) -> str:
        """Read a validated HTML page for the future read-only viewer."""
        self._ensure_valid()
        if page not in self._pages:
            raise self._error("path", "Unknown Help page.")
        return self.resource_path(page).read_text(encoding="utf-8")

    def search_documents(self) -> tuple[HelpSearchDocument, ...]:
        """Read section text without introducing a search engine or database."""
        self._ensure_valid()
        return self._validate_search()

    def load_control_excerpt(self, topic_id: str) -> str | None:
        """Read only explicitly curated, generated excerpt HTML for a known topic."""
        self._ensure_valid()
        topic = self._topics.get(topic_id)
        if topic is None or topic.control_excerpt_target is None:
            return None
        excerpts = _string_map(
            json.loads(self.resource_path("excerpts.json").read_text("utf-8"))
        )
        try:
            return excerpts[topic.page + "#" + topic.control_excerpt_target]
        except KeyError as exc:
            raise self._error("invalid", "Missing generated control excerpt.") from exc

    def _validate_search(self) -> tuple[HelpSearchDocument, ...]:
        values = json.loads(self._resource_path("search.json").read_text("utf-8"))
        result = []
        for record in values:
            document = HelpSearchDocument(
                record["page"],
                record["fragment"],
                record["title"],
                record["text"],
                _strings(record["topic_ids"]),
            )
            self._resource_path(document.page + "#" + document.fragment)
            if not all(isinstance(v, str) for v in (document.title, document.text)):
                raise ValueError("Invalid search text")
            if any(t not in self._topics for t in document.topic_ids):
                raise ValueError("Invalid search topic")
            result.append(document)
        return tuple(result)
