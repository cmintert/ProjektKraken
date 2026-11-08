"""Contain and decode explicitly shared image assets outside the DB thread."""

import base64
import hashlib
import json
import math
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.core.mcp_access import MAX_IMAGE_RESULT_BYTES, McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_contracts import require_scope
from src.services.mcp_image_variants import image_variants

CROP_COMPONENTS = 4


def image_job(db: DatabaseService, request: dict[str, Any]) -> dict[str, Any]:
    """Resolve only persisted identities and contained active-world asset files."""
    require_scope(request, "images")
    args = request["arguments"]
    kind, identifier = args.get("source_kind"), args.get("source_id")
    require_scope(request, "maps" if kind == "map" else "attachments")
    variant = args.get("variant_id")
    if kind == "map":
        item = db.get_map(identifier)
        chosen = (
            next(
                (
                    entry
                    for entry in image_variants(item)
                    if entry["variant_id"] == (variant or "base")
                ),
                None,
            )
            if item
            else None
        )
        stored = chosen["_file"] if chosen else None
    elif kind == "attachment":
        attachment = db.get_attachment_repo().get(identifier)
        stored = attachment.image_rel_path if attachment else None
        if variant not in {None, "original"}:
            raise McpFailure("UNSUPPORTED_VARIANT")
    else:
        raise McpFailure("INVALID_INPUT")
    if stored is None:
        raise McpFailure("NOT_FOUND")
    root = Path(db.db_path).resolve().parent
    relative = Path(stored)
    if relative.is_absolute() or ".." in relative.parts:
        raise McpFailure("ASSET_UNAVAILABLE")
    path = (root / relative).resolve()
    assets = (root / "assets").resolve()
    if not assets.is_relative_to(root) or not path.is_relative_to(assets):
        raise McpFailure("ASSET_UNAVAILABLE")
    crop = args.get("crop")
    if crop is not None:
        _validate_crop(crop)
        if kind != "map":
            raise McpFailure("INVALID_INPUT")
    return {
        "path": str(path),
        "root": str(root),
        "crop": crop,
        "source_kind": kind,
        "source_id": identifier,
        "variant_id": (variant or "base") if kind == "map" else "original",
    }


def _validate_crop(crop: Any) -> None:
    if (
        not isinstance(crop, list)
        or len(crop) != CROP_COMPONENTS
        or any(
            type(value) not in {int, float}
            or not math.isfinite(value)
            or not 0 <= value <= 1
            for value in crop
        )
    ):
        raise McpFailure("INVALID_INPUT")
    if crop[0] >= crop[2] or crop[1] >= crop[3]:
        raise McpFailure("INVALID_INPUT")


def fingerprint(path: Path) -> str:
    """Hash a bounded asset, detecting replacement even without a database edit."""
    if path.stat().st_size > 64 * 1024 * 1024:
        raise McpFailure("IMAGE_LIMIT")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_image(job: dict[str, Any], expired: Callable[[], bool]) -> dict[str, Any]:
    """Use an isolated process; terminate it when the owning request is cancelled."""
    if expired():
        raise McpFailure("UNAVAILABLE")
    path = Path(job["path"])
    before = fingerprint(path)
    executable = Path(sys.executable)
    command = (
        [str(executable.with_name("KrakenMCP.exe")), "--image-helper"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "src.services.mcp_image_helper"]
    )
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ) as process:
        payload: bytes | None = json.dumps(job).encode()
        deadline = time.monotonic() + 9
        try:
            while True:
                if expired() or time.monotonic() >= deadline:
                    raise McpFailure("TIMEOUT")
                try:
                    output, _ = process.communicate(payload, timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    payload = None
            if process.returncode:
                raise McpFailure("IMAGE_UNAVAILABLE")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    if len(output) > MAX_IMAGE_RESULT_BYTES - 16384:
        raise McpFailure("RESULT_TOO_LARGE")
    data = json.loads(output)
    if fingerprint(path) != before:
        raise McpFailure("WORLD_CHANGED")
    # Validate the helper protocol before it can become native MCP image content.
    base64.b64decode(data["image"], validate=True)
    return {**data, "asset_revision": before}
