"""Verify packaged offline Help with the actual Qt rich-text renderer."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QTextBrowser

from src.core.help_bundle import file_hash
from src.services.help_bundle_service import HelpBundleService


def probe_help(service: HelpBundleService | None = None) -> dict[str, Any]:
    """Read every local page in Qt without network or authoring dependencies."""
    service = service or HelpBundleService()
    metadata = service.validate()
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setOpenLinks(False)
    characters = 0
    try:
        for page in service.pages():
            browser.setSource(QUrl.fromLocalFile(str(service.resource_path(page.path))))
            text = browser.toPlainText()
            if page.title not in text:
                raise ValueError(f"Qt did not render Help page title: {page.path}")
            characters += len(text)
            for anchor in page.anchors:
                if (
                    f'name="{html.escape(anchor, quote=True)}"'
                    not in browser.document().toHtml()
                ):
                    raise ValueError(f"Qt lost Help anchor: {page.path}#{anchor}")
                browser.scrollToAnchor(anchor)
    finally:
        browser.close()
        browser.deleteLater()
    return {
        "version": metadata.version,
        "revision": metadata.revision,
        "source_dirty": metadata.dirty,
        "pages": len(service.pages()),
        "search_documents": len(service.search_documents()),
        "rendered_characters": characters,
        "manifest_sha256": file_hash(Path(service.root) / "manifest.json"),
    }


def run_help_probe(
    argv: list[str], service: HelpBundleService | None = None
) -> int | None:
    """Handle an internal Help-only package probe before any world initialization."""
    if "--help-bundle-smoke-report" not in argv:
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help-bundle-smoke-report", type=Path, required=True)
    options = parser.parse_args(argv[1:])
    app = QApplication.instance() or QApplication([argv[0]])
    report: dict[str, Any]
    try:
        report = {"success": True, "help_evidence": probe_help(service), "errors": []}
    except (OSError, ValueError, RuntimeError) as exc:
        report = {"success": False, "errors": [str(exc)]}
    options.help_bundle_smoke_report.parent.mkdir(parents=True, exist_ok=True)
    options.help_bundle_smoke_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Keep the application alive until all renderer work and report writing finish.
    del app
    return 0 if report["success"] else 1
