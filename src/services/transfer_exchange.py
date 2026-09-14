"""File adapters for the unified lore exchange pipeline (no GUI or database)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from src.core.transfer import EXCHANGE_VERSION, LORE_KINDS
from src.services.import_service import ImportService

CSV_FIELDS = {
    "entities": ["id", "name", "type", "description", "tags", "attributes"],
    "events": [
        "id",
        "name",
        "type",
        "lore_date",
        "lore_duration",
        "description",
        "tags",
        "attributes",
    ],
    "relations": ["id", "source_id", "target_id", "rel_type", "attributes"],
}


def fingerprint(path: str) -> str:
    """Fingerprint source bytes so reviewed input cannot change unnoticed."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path: str, delimiter: str = "") -> tuple[list[str], list[dict[str, str]]]:
    """Read UTF-8 CSV/TSV with bounded delimiter detection and quoted newlines."""
    text = Path(path).read_text(encoding="utf-8-sig")
    if not delimiter:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = "\t" if Path(path).suffix.lower() == ".tsv" else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    fields = list(reader.fieldnames or [])
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("CSV needs a header row with unique column names.")
    rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(
            "A CSV row has more cells than its header. Check the delimiter."
        )
    return fields, rows


def parse_json(text: str) -> dict[str, Any]:
    """Accept legacy lore and versioned exchange; reject unrelated JSON schemas."""
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError(
            "Lore JSON must be an object containing entities/events/relations."
        )
    if "exchange_version" in raw and raw["exchange_version"] != EXCHANGE_VERSION:
        raise ValueError("This lore exchange version is not supported.")
    if any(key in raw for key in LORE_KINDS):
        data = {key: raw.get(key, []) for key in LORE_KINDS}
    elif "name" in raw:
        data = ImportService.parse_only(raw)
    else:
        raise ValueError(
            "This is not lore JSON. Palette and graph JSON have other workflows."
        )
    for kind, rows in data.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{kind} must be a list of objects.")
    return data


def _csv_data(
    source: dict[str, Any], path: str, label: str, warnings: list[str]
) -> dict[str, Any]:
    kind = source.get("kind", "entities")
    if kind not in LORE_KINDS:
        raise ValueError("Choose entities, events or relations for the CSV.")
    headers, rows = read_csv(path, source.get("delimiter", ""))
    mapping = source.get("mapping") or {
        name: name for name in headers if name in CSV_FIELDS[kind]
    }
    ignored = [name for name in headers if not mapping.get(name)]
    if ignored:
        warnings.append(f"{label}: ignored columns: {', '.join(ignored)}")
    data: dict[str, Any] = {kind: []}
    for index, row in enumerate(rows, 2):
        item: dict[str, Any] = {
            target: row.get(column, "")
            for column, target in mapping.items()
            if target and row.get(column, "") != ""
        }
        for field in ("attributes", "tags"):
            if field in item:
                item[field] = json.loads(item[field])
        item["_transfer_source"] = f"{label}: row {index}"
        data[kind].append(item)
    return data


def load_sources(sources: list[dict[str, Any]], pasted: str = "") -> dict[str, Any]:
    """Combine every input, retaining source labels for review and diagnostics."""
    combined: dict[str, Any] = {key: [] for key in LORE_KINDS}
    hashes: dict[str, str] = {}
    warnings: list[str] = []
    inputs = list(sources)
    if pasted.strip():
        inputs.append({"text": pasted, "path": "", "label": "Pasted JSON"})
    for source in inputs:
        path = source.get("path", "")
        label = path or source.get("label", "Pasted JSON")
        suffix = Path(path).suffix.lower() if path else ".json"
        if path:
            hashes[path] = fingerprint(path)
        try:
            if suffix in {".csv", ".tsv"}:
                data = _csv_data(source, path, label, warnings)
            elif suffix == ".md":
                data = ImportService.parse_markdown_file(
                    Path(path).read_text(encoding="utf-8-sig"), Path(path).stem
                )
            elif suffix == ".json":
                data = parse_json(
                    Path(path).read_text(encoding="utf-8-sig")
                    if path
                    else source["text"]
                )
            else:
                raise ValueError(f"Unsupported extension {suffix}.")
            for kind in LORE_KINDS:
                for row in data.get(kind, []):
                    row.setdefault("_transfer_source", label)
                    combined[kind].append(row)
        except (ValueError, OSError, TypeError) as exc:
            raise ValueError(f"{label}: {exc}") from exc
    if not any(combined.values()):
        raise ValueError("No lore records were found in the selected inputs.")
    combined["source_hashes"] = hashes
    combined["warnings"] = warnings
    return combined


def csv_text(kind: str, records: list[dict[str, Any]]) -> str:
    """Serialize a canonical table without losing multiline or structured cells."""
    fields = CSV_FIELDS[kind]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = dict(record)
        if kind != "relations":
            row["tags"] = row.get("attributes", {}).get("_tags", [])
        for name in ("tags", "attributes"):
            if name in row:
                row[name] = json.dumps(row[name], ensure_ascii=False)
        writer.writerow(row)
    return output.getvalue()


def template_text(kind: str = "entities", format_key: str = "csv") -> str:
    """Return useful, re-importable starter data."""
    example: dict[str, Any] = {"name": "Example", "type": "character"}
    if kind == "events":
        example = {"name": "Example event", "type": "generic", "lore_date": 1.0}
    elif kind == "relations":
        example = {
            "source_id": "SOURCE_UUID",
            "target_id": "TARGET_UUID",
            "rel_type": "related",
        }
    if format_key == "csv":
        return csv_text(kind, [example])
    return json.dumps({"exchange_version": EXCHANGE_VERSION, kind: [example]}, indent=2)
