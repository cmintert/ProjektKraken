"""Isolated real-Chromium probe for longform stored-content security."""

# ruff: noqa: E402, I001 -- Qt environment must be set before PySide imports.

import json
import os
import sys
from pathlib import Path
from typing import Any

# Configure Qt before importing PySide6. Windows and headless runners do not
# provide a reliable GPU context, so use the same supported software path as
# the packaged Windows smoke test.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, Qt
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWidgets import QApplication

from src.webserver.markdown_renderer import render_longform_markdown

_TIMEOUT_MS = 15_000
_RESULT_PREFIX = "RESULT_JSON="


def _wait_for_load(page: QWebEnginePage, html: str) -> None:
    """Load HTML and fail normally if Chromium does not finish in time."""
    results: list[bool] = []
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def on_finished(success: bool) -> None:
        results.append(success)
        loop.quit()

    page.loadFinished.connect(on_finished)
    page.setHtml(html)
    timer.start(_TIMEOUT_MS)
    loop.exec()
    timer.stop()
    page.loadFinished.disconnect(on_finished)

    if not results:
        raise TimeoutError("Chromium did not finish loading the security probe")
    if not results[0]:
        raise RuntimeError("Chromium failed to load the security probe")


def _run_javascript(page: QWebEnginePage, script: str) -> str:
    """Execute JavaScript and return its string result synchronously."""
    results: list[Any] = []
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def on_result(result: Any) -> None:
        results.append(result)
        loop.quit()

    page.runJavaScript(script, on_result)
    timer.start(_TIMEOUT_MS)
    loop.exec()
    timer.stop()

    if not results:
        raise TimeoutError("Chromium did not return the security probe result")
    if not isinstance(results[0], str):
        raise TypeError("Chromium returned a non-string security probe result")
    return results[0]


def _build_probe() -> tuple[str, str]:
    """Build the browser shell and script for the stored-content attack probe."""
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
    script_path = _REPO_ROOT / "src" / "webserver" / "static" / "app.js"
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
    return shell, f"{app_script}\n{assertion_script}"


def main() -> int:
    """Run the probe in a dedicated Qt process and print its observed DOM state."""
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    profile = QWebEngineProfile(app)
    page = QWebEnginePage(profile)
    try:
        shell, script = _build_probe()
        _wait_for_load(page, shell)
        observed = _run_javascript(page, script)
        print(f"{_RESULT_PREFIX}{observed}", flush=True)
        return 0
    finally:
        page.deleteLater()
        QCoreApplication.sendPostedEvents(page, QEvent.Type.DeferredDelete)
        app.processEvents()
        profile.deleteLater()
        QCoreApplication.sendPostedEvents(profile, QEvent.Type.DeferredDelete)
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
