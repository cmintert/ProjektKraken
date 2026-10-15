"""Qt-independent inspection declarations and reviewed source identities."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

_CONTROL_CONSTRUCTORS = frozenset(
    {
        "QPushButton",
        "QToolButton",
        "QLineEdit",
        "QPlainTextEdit",
        "QTextEdit",
        "QComboBox",
        "QCheckBox",
        "QRadioButton",
        "QSpinBox",
        "QDoubleSpinBox",
        "ScrollSafeSpinBox",
        "ScrollSafeDoubleSpinBox",
        "QListWidget",
        "QTreeWidget",
        "QTableWidget",
        "QTreeView",
        "QSlider",
        "QDialogButtonBox",
    }
)


def symbol_fingerprint(tree: ast.Module, symbol: str) -> str:
    """Fingerprint executable structure, ignoring comments and formatting."""
    parts = symbol.split(".")
    parent: ast.AST = tree
    for part in parts:
        matches = [
            node
            for node in ast.walk(parent)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == part
        ]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous source symbol: {symbol}")
        parent = matches[0]
    return hashlib.sha256(
        ast.dump(parent, include_attributes=False).encode()
    ).hexdigest()


def check_inventory(root: Path) -> list[str]:
    """Report missing bindings, destinations and unreviewed relevant changes."""
    errors: list[str] = []
    try:
        catalog = json.loads((root / "docs/help-inspection.json").read_text("utf-8"))
        topics = {
            record["id"]: record
            for record in json.loads(
                (root / "docs/help-topics.json").read_text("utf-8")
            )["topics"]
        }
        trees: dict[str, ast.Module] = {}
        texts: dict[str, str] = {}
        _check_bindings(root, catalog, topics, texts, errors)
        _check_new_controls(root, catalog, errors)
        for review in catalog["source_reviews"]:
            path = review["source"]
            file = (root / path).resolve()
            if not file.is_relative_to(root.resolve()):
                raise ValueError(f"Source escapes repository: {path}")
            if path not in trees:
                trees[path] = ast.parse(file.read_text("utf-8"))
            actual = symbol_fingerprint(trees[path], review["symbol"])
            if actual != review["sha256"]:
                errors.append(
                    f"{path}:{review['symbol']}: Help impact review required; "
                    "update the explanation or record why it remains accurate"
                )
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        errors.append(f"Invalid inspection inventory: {exc}")
    return errors


def _check_new_controls(root: Path, catalog: dict[str, Any], errors: list[str]) -> None:
    """Require a declaration or explicit exemption for native input factories."""
    exemptions = {
        (item["source"], item["symbol"])
        for item in catalog.get("factory_exemptions", [])
        if item.get("reason")
    }
    paths = [*(root / "src/gui").rglob("*.py"), root / "src/app/ui_manager.py"]
    for path in paths:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text("utf-8"))
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in _CONTROL_CONSTRUCTORS:
                continue
            parent = parents.get(node)
            if (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "declare_inspection"
            ):
                continue
            parts: list[str] = []
            while parent is not None:
                if isinstance(parent, (ast.ClassDef, ast.FunctionDef)):
                    parts.insert(0, parent.name)
                parent = parents.get(parent)
            symbol = ".".join(parts)
            source = path.relative_to(root).as_posix()
            if (source, symbol) not in exemptions:
                errors.append(
                    f"{source}:{symbol}: declare inspection for {node.func.id} "
                    "or record a justified factory exemption"
                )


def _check_bindings(
    root: Path,
    catalog: dict[str, Any],
    topics: dict[str, dict[str, Any]],
    texts: dict[str, str],
    errors: list[str],
) -> None:
    ids: set[str] = set()
    reviewed = {(r["source"], r["symbol"]) for r in catalog["source_reviews"]}
    for record in catalog["bindings"]:
        meaning = record["id"]
        if meaning in ids:
            errors.append(f"Duplicate inspection meaning: {meaning}")
        ids.add(meaning)
        topic = topics.get(record["topic_id"])
        if topic is None:
            errors.append(f"{meaning}: unknown task {record['topic_id']}")
            continue
        page = "docs/user/" + topic["source"]
        for path in (page, record["source"]):
            file = (root / path).resolve()
            if not file.is_relative_to(root.resolve()):
                raise ValueError(f"Inventory path escapes repository: {path}")
            if path not in texts:
                texts[path] = file.read_text("utf-8")
        if f"({record['target']})=" not in texts[page]:
            errors.append(
                f"{meaning}: missing canonical explanation {record['target']}"
            )
        declaration = "|".join((meaning, record["topic_id"], record["target"]))
        if declaration not in texts[record["source"]]:
            errors.append(f"{meaning}: missing construction declaration")
        if (record["source"], record["symbol"]) not in reviewed:
            errors.append(f"{meaning}: source symbol has no Help impact review")
