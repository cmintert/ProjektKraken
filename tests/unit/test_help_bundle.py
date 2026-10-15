"""Offline Help generation, integrity, containment and Qt rendering regressions."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest
from PIL import Image
from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QTextBrowser

from scripts.build_help import ROOT, write_json
from src.app.help_package_probe import probe_help, run_help_probe
from src.core.help_bundle import HELP_INPUT_FILES, file_hash
from src.services.help_bundle_service import HelpBundleError, HelpBundleService

pytestmark = pytest.mark.ci_fast


def run_build(root):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from scripts.build_help import build_help; "
            "build_help(Path(__import__('sys').argv[1]))",
            str(root),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def generated_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("help-source")
    shutil.copyfile(ROOT / ".gitignore", root / ".gitignore")
    shutil.copytree(ROOT / "docs/user", root / "docs/user")
    for name in HELP_INPUT_FILES:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    fixture = root / "docs/user/fixture.md"
    fixture.write_text(
        "# Calendar Ω\n\n(help-fixture)=\n\n## Seasons\n\n"
        "On 3 Été, year −42: 星.\n\n"
        "| Month | Days |\n| --- | --- |\n| Été | 30 |\n\n"
        "```text\n3 Été −42\n```\n\n"
        "1. First\n2. Second\n\n"
        "![Calendar](calendar.png)\n\n"
        "[Manual](index.md#user-manual)\n\n"
        "{ref}`help-manual-home`\n\n"
        "[Qt](https://example.invalid/reference)\n",
        encoding="utf-8",
    )
    Image.new("RGB", (4, 4), "white").save(root / "docs/user/calendar.png")
    registry_path = root / "docs/help-topics.json"
    registry = json.loads(registry_path.read_text("utf-8"))
    registry["topics"][0]["control_excerpt_target"] = "help-authoring-create"
    write_json(registry_path, registry)
    index = root / "docs/user/index.md"
    index.write_text(
        index.read_text("utf-8").replace(
            "\ntroubleshooting\n", "\ntroubleshooting\nfixture\n"
        ),
        encoding="utf-8",
    )
    for args in (
        ("init",),
        ("add", "."),
        (
            "-c",
            "user.name=Help Test",
            "-c",
            "user.email=help@example.invalid",
            "commit",
            "-m",
            "fixture",
        ),
    ):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    result = run_build(root)
    assert result.returncode == 0, result.stderr
    return root


@pytest.fixture
def help_root(generated_root, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(generated_root, root)
    return root


def bundle(root):
    return root / "docs/_build/help"


def service(root, **kwargs):
    return HelpBundleService(bundle(root), **kwargs)


def test_all_topics_search_and_navigation(generated_root):
    reader = service(generated_root, source_root=generated_root)
    reader.validate()
    registry = json.loads((generated_root / "docs/help-topics.json").read_text("utf-8"))
    assert len(registry["topics"]) == 49
    for topic in registry["topics"]:
        resolved = reader.resolve_topic(topic["id"])
        assert resolved.id == topic["id"]
        assert resolved.fragment == topic["target"]
        reader.resource_path(resolved.page + "#" + resolved.fragment)
    assert reader.resolve_topic("unknown.topic").id == "manual.home"
    assert "Create an event or entity" in reader.load_control_excerpt(
        "authoring.create"
    )
    assert reader.load_control_excerpt("unknown.topic") is None
    assert len(reader.pages()) == 13
    assert "getting-started.html" in reader.load_page("index.html")
    reader.resource_path("maps.html#dated-path-and-region-geometry")
    search = reader.search_documents()
    assert any("星" in entry.text for entry in search)
    assert {t["id"] for t in registry["topics"]}.issubset(
        {topic for entry in search for topic in entry.topic_ids}
    )
    assert (
        reader.resolve_topic("date.evidence").page
        == reader.resolve_topic("event.chronology").page
    )
    # These concepts share a manual page but need distinct task landing sections.
    for first, second in (
        ("date.evidence", "event.chronology"),
        ("entity.historical-editing", "entity.value-source"),
        ("writing.edit", "writing.links"),
    ):
        assert reader.resolve_topic(first).title != reader.resolve_topic(second).title


def test_deterministic_rebuild(generated_root):
    path = bundle(generated_root)
    before = {
        p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }
    result = run_build(generated_root)
    assert result.returncode == 0, result.stderr
    assert before == {
        p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("change", ["target", "asset", "link", "raw", "remote"])
def test_failed_generation_preserves_bundle(help_root, change):
    path = bundle(help_root) / "manifest.json"
    before = path.read_bytes()
    source = help_root / "docs/user/fixture.md"
    if change == "target":
        source = help_root / "docs/user/maps.md"
        source.write_text(
            source.read_text("utf-8").replace(
                "(help-map-features)=", "(renamed-target)="
            ),
            encoding="utf-8",
        )
    elif change == "asset":
        (help_root / "docs/user/calendar.png").unlink()
    else:
        text = {
            "link": "\n[Broken](maps.md#missing-fragment)\n",
            "raw": "\n<script>alert(1)</script>\n",
            "remote": "\n![Remote](https://example.invalid/image.png)\n",
        }[change]
        source.write_text(source.read_text("utf-8") + text, encoding="utf-8")
    result = run_build(help_root)
    assert result.returncode != 0
    if change == "remote":
        assert "Remote images are not allowed" in result.stderr
        assert "Could not fetch" not in result.stderr
    assert path.read_bytes() == before


def test_stale_version_and_corrupt_payload(help_root):
    with pytest.raises(HelpBundleError, match="app version") as error:
        service(help_root, version="0.0.0").validate()
    assert error.value.code == "version"
    canonical = help_root / "docs/user/maps.md"
    canonical.write_text(canonical.read_text("utf-8") + "\nChanged\n", encoding="utf-8")
    with pytest.raises(HelpBundleError) as error:
        service(help_root, source_root=help_root).validate()
    assert error.value.code == "stale"
    html = bundle(help_root) / "index.html"
    html.write_text("corrupt", encoding="utf-8")
    with pytest.raises(HelpBundleError, match="hash mismatch"):
        service(help_root).validate()


@pytest.mark.parametrize(
    "uri",
    [
        "../world.kraken",
        "%2e%2e/world.kraken",
        "https://example.invalid/page",
        "//host/path",
        "file:///C:/secret",
        "C:/secret",
        "maps.html#missing",
        "maps.html?remote=true",
        "maps.html%5c..%5csecret",
    ],
)
def test_confined_navigation(generated_root, uri):
    with pytest.raises(HelpBundleError) as error:
        service(generated_root).resource_path(uri)
    assert error.value.code == "path"


def test_escaped_symlink(help_root, tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("outside", encoding="utf-8")
    link = bundle(help_root) / "index.html"
    link.unlink()
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(HelpBundleError) as error:
        service(help_root).validate()
    assert error.value.code == "path"


def test_missing_and_malformed_bundle(tmp_path, help_root):
    with pytest.raises(HelpBundleError) as error:
        HelpBundleService(tmp_path / "absent").validate()
    assert error.value.code == "missing"
    path = bundle(help_root) / "manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    manifest["topics"][0]["related_ids"] = ["missing.topic"]
    write_json(path, manifest)
    with pytest.raises(HelpBundleError, match="related topic"):
        service(help_root).validate()


def test_package_identity_and_arbitrary_working_directory(
    help_root, tmp_path, monkeypatch
):
    path = bundle(help_root) / "manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    info = help_root / "build-info.json"
    identity = {
        "version": manifest["version"],
        "commit": manifest["revision"],
        "source_dirty": manifest["dirty"],
        "help_manifest_sha256": file_hash(path),
    }
    write_json(info, identity)
    monkeypatch.chdir(tmp_path)
    service(help_root, build_info=info).validate()
    identity["commit"] = "wrong-revision"
    write_json(info, identity)
    with pytest.raises(HelpBundleError, match="build identity"):
        service(help_root, build_info=info).validate()


def test_frozen_default_uses_bundle_root(help_root, tmp_path, monkeypatch):
    package = tmp_path / "package"
    shutil.copytree(bundle(help_root), package / "_internal/help")
    path = package / "_internal/help/manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    write_json(
        package / "build-info.json",
        {
            "version": manifest["version"],
            "commit": manifest["revision"],
            "source_dirty": manifest["dirty"],
            "help_manifest_sha256": file_hash(path),
        },
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(package / "_internal"), raising=False)
    monkeypatch.setattr(sys, "executable", str(package / "ProjektKraken.exe"))
    monkeypatch.chdir(tmp_path)
    assert HelpBundleService().validate().version == manifest["version"]


def test_qt_rendering_anchors_tables_code_images(generated_root, qapp):
    reader = service(generated_root)
    evidence = probe_help(reader)
    assert evidence["pages"] == 13
    browser = QTextBrowser()
    try:
        browser.setSource(QUrl.fromLocalFile(str(reader.resource_path("fixture.html"))))
        assert "3 Été, year −42: 星" in browser.toPlainText()
        assert "First" in browser.toPlainText()
        assert "<table" in browser.document().toHtml()
        assert "3 Été −42" in browser.toPlainText()
        assert 'href="https://' not in reader.load_page("fixture.html")
        # QTextBrowser navigation follows an emitted explicit target.
        assert 'name="help-fixture"' in browser.document().toHtml()
        browser.scrollToAnchor("help-fixture")
        images = list((bundle(generated_root) / "assets").iterdir())
        image = browser.document().resource(
            QTextDocument.ResourceType.ImageResource, QUrl.fromLocalFile(str(images[0]))
        )
        assert image is not None
        assert not image.isNull()
    finally:
        browser.close()
        browser.deleteLater()


def test_help_only_probe_without_world_startup(generated_root, tmp_path, qapp):
    report = tmp_path / "probe.json"
    assert run_help_probe(["Kraken"]) is None
    assert (
        run_help_probe(
            ["Kraken", "--help-bundle-smoke-report", str(report)],
            service(generated_root),
        )
        == 0
    )
    result = json.loads(report.read_text("utf-8"))
    assert result["success"]
    assert result["help_evidence"]["pages"] == 13
    assert not (tmp_path / "worlds").exists()
