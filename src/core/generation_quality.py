"""Mechanical generation checks, independent of provider and factual judgment."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import ceil
from typing import Any

from src.core.markdown_content import parse_content


@dataclass(frozen=True)
class GenerationFinding:
    """An observable change requiring author review."""

    code: str
    message: str


def estimate_tokens(text: str) -> int:
    """Return a UTF-8 heuristic, never a measured model token count."""
    return ceil(len(text.encode("utf-8")) / 3)


def output_allowance(source: str, operation: str) -> int:
    """Recommend a complete-description output budget in 256-token steps."""
    if operation == "create":
        return 1024
    factor = 1.75 if operation.startswith("expand") else 1.25
    desired = max(1024, ceil(factor * estimate_tokens(source)) + 256)
    return min(100000, ceil(desired / 256) * 256)


def completion_status(reason: str | None) -> str:
    """Describe termination separately from job success and factual fidelity."""
    if reason == "length":
        return "incomplete"
    return "complete" if reason == "stop" else "unknown"


def _walk(tokens: Iterable[Any]) -> Iterable[Any]:
    for token in tokens:
        yield token
        yield from _walk(token.children or ())


def _signature(source: str) -> tuple[list[Any], list[Any], list[str]]:
    parsed = parse_content(source)
    links = [
        (token.meta.get("target"), token.content)
        for token in _walk(parsed.tokens)
        if token.type == "kraken_wikilink"
    ]
    structure = [
        (token.type, token.tag, token.markup)
        for token in parsed.tokens
        if token.type
        in {
            "heading_open",
            "bullet_list_open",
            "ordered_list_open",
            "list_item_open",
            "blockquote_open",
        }
    ]
    lines = source.splitlines(keepends=True)
    protected = [
        "".join(lines[token.map[0] : token.map[1]])
        for token in parsed.tokens
        if token.type in {"table_open", "fence", "code_block", "html_block"}
        and token.map is not None
    ]
    protected.extend(
        str(token.content)
        for token in _walk(parsed.tokens)
        if token.type == "code_inline"
    )
    return links, structure, protected


def assess_candidate(
    source: str,
    candidate: str,
    finish_reason: str | None = None,
    action: str = "replace",
) -> list[GenerationFinding]:
    """Compare source structures using Kraken syntax, excluding literal links."""
    findings = []
    if completion_status(finish_reason) == "incomplete":
        findings.append(GenerationFinding("truncated", "Output token limit reached."))
    if not source:
        return findings
    before = _signature(source)
    after = _signature(candidate)
    if action == "append":
        if (
            any(link in before[0] for link in after[0])
            or any(block in before[2] for block in after[2])
            or candidate.strip() == source.strip()
        ):
            findings.append(
                GenerationFinding("duplicate_source", "Append repeats source content.")
            )
        return findings
    for old, new, code, message in zip(
        before,
        after,
        ("links_changed", "structure_changed", "protected_blocks_changed"),
        (
            "Wiki-link targets, aliases, counts or order changed.",
            "Heading or list structure changed.",
            "A table or literal block changed.",
        ),
        strict=True,
    ):
        if old != new:
            findings.append(GenerationFinding(code, message))
    return findings


def assessment_dict(source: str, candidate: str, reason: str | None) -> dict[str, Any]:
    """Serialize mechanical findings without claiming factual validation."""
    return {
        "completion_status": completion_status(reason),
        "findings": [
            asdict(item) for item in assess_candidate(source, candidate, reason)
        ],
        "factual_fidelity": "unverified",
    }
