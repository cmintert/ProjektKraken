"""Chromium-level regression coverage for longform stored HTML injection."""

import json
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWebEngineCore import QWebEnginePage

from src.webserver.markdown_renderer import render_longform_markdown


@pytest.mark.integration
@pytest.mark.slow
def test_longform_renderer_keeps_published_payload_inert_in_chromium(
    qapp: Any, qtbot: Any
) -> None:
    """Render hostile stored content through the real Chromium DOM implementation."""
    imported_title = '<img src=x onerror="globalThis.__titleXss=true">Imported title'
    markdown_source = f"""# {imported_title}

<script>globalThis.__bodyXss = true</script>
<img src="https://attacker.invalid/pixel" onerror="globalThis.__imgXss=true">
**Safe formatting** and [[id:target-id|working wiki link]].
"""
    sections = [
        {
            "id": "source-id",
            "title": imported_title,
            "html": render_longform_markdown(markdown_source),
            "table": "entities",
            "heading_level": 1,
            "lore_date": None,
            "lore_duration": 0,
        },
        {
            "id": "target-id",
            "title": "Target",
            "html": render_longform_markdown("# Target\n\nDestination"),
            "table": "entities",
            "heading_level": 1,
            "lore_date": None,
            "lore_duration": 0,
        },
    ]
    shell = """<!doctype html><html><body data-initial-theme="dark_mode"
data-lan-access="false"><main id="content-panel"><div
id="longform-content"></div><div id="empty-state" class="hidden"><p
id="empty-message"></p></div></main><nav id="toc"></nav><span
id="item-count"></span></body></html>"""
    script_path = (
        Path(__file__).parents[2] / "src" / "webserver" / "static" / "app.js"
    )
    app_script = script_path.read_text(encoding="utf-8")
    assertion_script = f"""
window.__bodyXss = false;
window.__imgXss = false;
window.__titleXss = false;
cacheDom();
renderSections({json.dumps(sections)});
document.querySelector('a.wikilink-anchor')?.click();
JSON.stringify({{
    bodyXss: window.__bodyXss,
    imageXss: window.__imgXss,
    titleXss: window.__titleXss,
    activeElements: document.querySelectorAll(
        'script, img, iframe, object, svg, form, [onerror], [onclick], [onload]'
    ).length,
    attackerResources: document.querySelectorAll(
        '[src*="attacker.invalid"], [href*="attacker.invalid"]'
    ).length,
    formatting: document.querySelector('#longform-content strong')?.textContent,
    wikiHref: document.querySelector('a.wikilink-anchor')?.getAttribute('href'),
    wikiText: document.querySelector('a.wikilink-anchor')?.textContent,
    locationHash: window.location.hash,
    tocText: document.querySelector('#toc a')?.textContent,
    tocMarkup: document.querySelector('#toc a img') === null
}});
"""

    page = QWebEnginePage()
    try:
        with qtbot.waitSignal(page.loadFinished, timeout=15_000) as load_signal:
            page.setHtml(shell)
        assert load_signal.args == [True]

        results: list[str] = []
        page.runJavaScript(
            f"{app_script}\n{assertion_script}",
            lambda result: results.append(result),
        )
        qtbot.waitUntil(lambda: bool(results), timeout=15_000)
        observed = json.loads(results[0])

        assert observed == {
            "bodyXss": False,
            "imageXss": False,
            "titleXss": False,
            "activeElements": 0,
            "attackerResources": 0,
            "formatting": "Safe formatting",
            "wikiHref": "#section-1",
            "wikiText": "working wiki link",
            "locationHash": "#section-1",
            "tocText": imported_title,
            "tocMarkup": True,
        }
    finally:
        page.deleteLater()
        qapp.processEvents()
