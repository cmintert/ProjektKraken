"""Generate and atomically publish version-matched offline Help from MyST."""

from __future__ import annotations

import argparse
import ast
import io
import json
import logging
import posixpath
import subprocess
import tempfile
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from src.core.help_bundle import HELP_SCHEMA, file_hash, source_hashes
from src.services.help_bundle_service import HelpBundleService

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def write_json(path: Path, value: Any) -> None:
    """Serialize deterministic UTF-8 JSON with a final newline."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def source_identity(root: Path) -> dict[str, Any]:
    """Read exact app/Git identity without importing application startup."""
    module = ast.parse((root / "src/core/version.py").read_text("utf-8"))
    version = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets)
    )
    project = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    if version != project["project"]["version"]:
        raise ValueError("Runtime and project versions differ")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    return {
        "version": version,
        "revision": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--untracked-files=all")),
    }


class LinkInventory(HTMLParser):
    """Collect emitted anchors/resources for strict generated-link validation."""

    def __init__(self) -> None:
        """Initialize one page's structural inventory."""
        super().__init__()
        self.links: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Collect only the generated local navigation and image attributes."""
        values = dict(attrs)
        for key in ("href", "src"):
            if values.get(key):
                self.links.append(str(values[key]))
        if values.get("name"):
            self.anchors.add(str(values["name"]))


def validate_links(output: Path, pages: list[dict[str, Any]]) -> None:
    """Reject dangling fragments, escaping paths and remote resources."""
    inventory: dict[str, LinkInventory] = {}
    for page in pages:
        parser = LinkInventory()
        parser.feed((output / page["path"]).read_text("utf-8"))
        inventory[page["path"]] = parser
    for name, parser in inventory.items():
        for uri in parser.links:
            parsed = urlsplit(uri)
            relative = unquote(parsed.path)
            target = (
                posixpath.normpath(posixpath.join(posixpath.dirname(name), relative))
                if relative
                else name
            )
            if parsed.scheme or parsed.netloc or parsed.query or "\\" in relative:
                raise ValueError(f"{name}: unsafe generated link {uri}")
            path = (output / target).resolve()
            if not path.is_relative_to(output.resolve()) or not path.is_file():
                raise ValueError(f"{name}: unresolved generated link {uri}")
            if parsed.fragment and (
                target not in inventory
                or unquote(parsed.fragment) not in inventory[target].anchors
            ):
                raise ValueError(f"{name}: unresolved generated fragment {uri}")


def resolve_topics(root: Path, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve every approved semantic ID against actual generated fragments."""
    registry = json.loads((root / "docs/help-topics.json").read_text("utf-8"))
    if registry["schema_version"] != HELP_SCHEMA:
        raise ValueError("Unsupported topic registry schema")
    page_map = {page["path"]: page for page in pages}
    result = []
    ids: set[str] = set()
    for record in registry["topics"]:
        topic_id = record["id"]
        if topic_id in ids:
            raise ValueError(f"Duplicate topic ID: {topic_id}")
        ids.add(topic_id)
        source = Path(record["source"])
        if source.is_absolute() or ".." in source.parts or source.suffix != ".md":
            raise ValueError(f"Invalid canonical source: {source}")
        page = source.with_suffix(".html").as_posix()
        if page not in page_map or record["target"] not in page_map[page]["anchors"]:
            raise ValueError(
                f"Unresolved Help topic: {topic_id} ({source}#{record['target']})"
            )
        result.append(
            {
                "id": topic_id,
                "page": page,
                "fragment": record["target"],
                "title": page_map[page]["title"],
                "level": record["level"],
                "related_ids": record["related_ids"],
                "control_excerpt_target": record.get("control_excerpt_target"),
            }
        )
    return result


def generate(root: Path, output: Path) -> None:
    """Resolve MyST/Sphinx into a fresh bundle and validate before publication."""
    from sphinx.application import Sphinx
    from sphinx.errors import SphinxError

    initial_hashes = source_hashes(root)
    identity = source_identity(root)
    warnings = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="kraken-help-doctrees-") as cache:
        app = Sphinx(
            srcdir=str(root / "docs/user"),
            confdir=str(root / "docs"),
            outdir=str(output),
            doctreedir=cache,
            buildername="kraken_help",
            confoverrides={
                "extensions": ["myst_parser", "scripts.help_builder"],
                "root_doc": "index",
                "exclude_patterns": [],
                "html_static_path": [],
                "html_logo": None,
            },
            status=None,
            warning=warnings,
            freshenv=True,
            warningiserror=True,
        )
        try:
            app.build(force_all=True)
        except SphinxError as exc:
            raise ValueError(str(exc)) from exc
        if app.statuscode or warnings.getvalue():
            raise ValueError("Help Sphinx build failed:\n" + warnings.getvalue())
    pages = json.loads((output / "pages.json").read_text("utf-8"))
    topics = resolve_topics(root, pages)
    excerpts = json.loads((output / "excerpts.json").read_text("utf-8"))
    for topic in topics:
        target = topic.get("control_excerpt_target")
        if target and topic["page"] + "#" + target not in excerpts:
            raise ValueError(f"Unresolved control excerpt: {topic['id']}")
    search = json.loads((output / "search.json").read_text("utf-8"))
    for record in search:
        matched = [
            t
            for t in topics
            if t["page"] == record["page"]
            and t["fragment"] in record.get("anchors", [])
        ]
        record.pop("anchors", None)
        record["topic_ids"] = sorted(
            set(record.get("topic_ids", [])) | {t["id"] for t in matched}
        )
        for topic in matched:
            topic["title"] = record["title"]
    write_json(output / "search.json", search)
    (output / "pages.json").unlink()
    validate_links(output, pages)
    if source_hashes(root) != initial_hashes or source_identity(root) != identity:
        raise ValueError("Source changed during Help generation; rebuild")
    manifest = {
        "schema_version": HELP_SCHEMA,
        **identity,
        "pages": pages,
        "topics": topics,
        "source_hashes": initial_hashes,
        "payload_hashes": {
            p.relative_to(output).as_posix(): file_hash(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    write_json(output / "manifest.json", manifest)
    HelpBundleService(output, version=identity["version"], source_root=root).validate()


def build_help(root: Path = ROOT, output: Path | None = None) -> Path:
    """Publish a complete validated bundle, preserving the old one on failure."""
    output = output or root / "docs/_build/help"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".help-stage-", dir=output.parent) as temp:
        staged = Path(temp) / "bundle"
        staged.mkdir()
        generate(root, staged)
        backup = Path(temp) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            staged.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    return output


def check_package(root: Path, package: Path) -> None:
    """Validate an existing package against its own and the requested source identity."""
    service = HelpBundleService(
        package / "_internal/help",
        source_root=root,
        build_info=package / "build-info.json",
    )
    metadata = service.validate()
    expected = source_identity(root)
    if (metadata.version, metadata.revision, metadata.dirty) != (
        expected["version"],
        expected["revision"],
        expected["dirty"],
    ):
        raise ValueError("Existing package does not match the requested source")


def main() -> int:
    """Run generation or validate an existing package without rewriting it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-package", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if args.check_package:
            check_package(ROOT, args.check_package.resolve())
        else:
            logger.info("Generated offline Help: %s", build_help())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        logger.error("Help generation/validation failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
