"""Real process checks for the supported offline CLI entry points."""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image
from PySide6.QtCore import QSettings

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.cli import cli as unified_cli
from src.cli import importer
from src.cli import index as index_cli
from src.core.image_attachment import ImageAttachment
from src.core.world import World
from src.services.asset_store import AssetStore
from src.services.db_service import DatabaseService
from src.services.world_storage_settings import WorldStorageSettings

ROOT = Path(__file__).resolve().parents[2]

GROUPS = (
    "event",
    "entity",
    "relation",
    "map",
    "attachment",
    "calendar",
    "timeline",
    "wiki",
    "index",
    "longform",
    "obsidian",
    "backup",
    "graph",
    "info",
)


@pytest.fixture
def cli_world(tmp_path):
    world = World.create(tmp_path, "CLI World")
    env = os.environ.copy()
    env["PROJEKTKRAKEN_PERFORMANCE_WORLDS_DIR"] = str(tmp_path)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["APPDATA"] = str(tmp_path / "appdata")
    env["HOME"] = str(tmp_path / "home")
    return world, env


def _backup_directory(tmp_path: Path) -> Path:
    """Locate backups beneath the fixture's isolated platform data directory."""
    if sys.platform == "win32":
        base = tmp_path / "appdata"
    elif sys.platform == "darwin":
        base = tmp_path / "home" / "Library" / "Application Support"
    else:
        base = tmp_path / "home" / ".local" / "share"
    return base / "ProjektKraken" / "backups"


def invoke(env: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *arguments],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize("group", GROUPS)
def test_both_group_entry_points_have_help(cli_world, group):
    _, env = cli_world
    for entry in (("src.cli.cli", group), (f"src.cli.{group}",)):
        result = invoke(env, *entry, "--help")
        assert result.returncode == 0, (entry, result.stderr)


def test_published_example_modules_and_flags(cli_world):
    _, env = cli_world
    for relative_path in ("README.md", "src/cli/README.md", "docs/reference/cli.md"):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        for line in content.splitlines():
            if not line.startswith("python -m "):
                continue
            words = shlex.split(line)
            module = words[2]
            prefix = words[3:5] if module == "src.cli.cli" else words[3:4]
            help_result = invoke(env, module, *prefix, "--help")
            assert help_result.returncode == 0, (
                relative_path,
                line,
                help_result.stderr,
            )
            for flag in re.findall(r"(?<!\w)--[a-z][a-z-]+", line):
                assert flag in help_result.stdout, (relative_path, line, flag)


def test_json_create_empty_lists_and_existing_target(cli_world, tmp_path):
    world, env = cli_world
    db = str(world.db_path)
    for group in ("entity", "event"):
        empty = invoke(env, "src.cli.cli", group, "list", "-d", db, "--json")
        assert empty.returncode == 0, empty.stderr
        assert json.loads(empty.stdout) == []

    entity = invoke(
        env,
        "src.cli.cli",
        "entity",
        "create",
        "-d",
        db,
        "--name",
        "Mara",
        "--type",
        "character",
        "--json",
    )
    assert entity.returncode == 0, entity.stderr
    entity_id = json.loads(entity.stdout)["id"]
    event = invoke(
        env,
        "src.cli.event",
        "create",
        "-d",
        db,
        "--name",
        "Arrival",
        "--date",
        "100.5",
        "--json",
    )
    assert event.returncode == 0, event.stderr
    event_data = json.loads(event.stdout)
    assert event_data["lore_date"] == 100.5

    missing = invoke(
        env,
        "src.cli.cli",
        "entity",
        "create",
        "-d",
        str(tmp_path / "missing.kraken"),
        "--name",
        "Wrong",
        "--type",
        "character",
        "--json",
    )
    assert missing.returncode == 1
    assert missing.stdout == ""
    assert "Database file not found" in missing.stderr
    assert not (tmp_path / "missing.kraken").exists()
    assert (
        json.loads(
            invoke(
                env,
                "src.cli.entity",
                "show",
                "-d",
                db,
                "--id",
                entity_id,
                "--json",
            ).stdout
        )["id"]
        == entity_id
    )
    changed = invoke(
        env,
        "src.cli.cli",
        "entity",
        "update",
        "-d",
        db,
        "--id",
        entity_id,
        "--name",
        "Mara II",
    )
    assert changed.returncode == 0, changed.stderr
    changed_event = invoke(
        env,
        "src.cli.event",
        "update",
        "-d",
        db,
        "--id",
        event_data["id"],
        "--name",
        "Arrival II",
    )
    assert changed_event.returncode == 0, changed_event.stderr
    for group, item_id in (("entity", entity_id), ("event", event_data["id"])):
        deleted = invoke(
            env,
            "src.cli.cli",
            group,
            "delete",
            "-d",
            db,
            "--id",
            item_id,
            "--force",
        )
        assert deleted.returncode == 0, deleted.stderr
    stats = invoke(env, "src.cli.cli", "info", "show", "-d", db, "--json")
    assert stats.returncode == 0, stats.stderr
    assert json.loads(stats.stdout)["objects"]["entities"] == 0


def test_marker_bounds_and_partial_attachment(cli_world, tmp_path):
    world, env = cli_world
    db = str(world.db_path)
    entity = invoke(
        env,
        "src.cli.entity",
        "create",
        "-d",
        db,
        "--name",
        "Mara",
        "--type",
        "character",
        "--json",
    )
    entity_id = json.loads(entity.stdout)["id"]
    image_path = tmp_path / "portrait.png"
    Image.new("RGB", (4, 4), "white").save(image_path)
    created_map = invoke(
        env,
        "src.cli.map",
        "create",
        "-d",
        db,
        "--name",
        "Atlas",
        "--image",
        str(image_path),
    )
    assert created_map.returncode == 0, created_map.stderr
    maps = invoke(env, "src.cli.map", "list", "-d", db, "--json")
    map_id = json.loads(maps.stdout)[0]["id"]
    base = (
        "src.cli.cli",
        "map",
        "marker-add",
        "-d",
        db,
        "--map-id",
        map_id,
        "--object-type",
        "entity",
        "--object-id",
        entity_id,
    )
    invalid = invoke(env, *base, "--x", "100", "--y", "0.5")
    assert invalid.returncode == 1
    valid = invoke(env, *base, "--x", "0", "--y", "1")
    assert valid.returncode == 0, valid.stderr
    markers = invoke(
        env,
        "src.cli.map",
        "marker-list",
        "-d",
        db,
        "--map-id",
        map_id,
        "--json",
    )
    marker_id = json.loads(markers.stdout)[0]["id"]
    invalid_update = invoke(
        env,
        "src.cli.map",
        "marker-update",
        "-d",
        db,
        "--id",
        marker_id,
        "--x",
        "-0.1",
    )
    assert invalid_update.returncode == 1
    valid_update = invoke(
        env,
        "src.cli.map",
        "marker-update",
        "-d",
        db,
        "--id",
        marker_id,
        "--x",
        "0.5",
    )
    assert valid_update.returncode == 0, valid_update.stderr

    missing_path = tmp_path / "absent.png"
    imported = invoke(
        env,
        "src.cli.cli",
        "attachment",
        "add",
        "-d",
        db,
        "--type",
        "entities",
        "--id",
        entity_id,
        str(image_path),
        str(missing_path),
    )
    assert imported.returncode == 1
    assert str(missing_path) in imported.stderr
    listed = invoke(
        env,
        "src.cli.attachment",
        "list",
        "-d",
        db,
        "--type",
        "entity",
        "--id",
        entity_id,
        "--json",
    )
    attachments = json.loads(listed.stdout)
    assert len(attachments) == 1
    assert attachments[0]["owner_type"] == "entity"
    assert (world.path / attachments[0]["image_rel_path"]).is_file()
    added_second = invoke(
        env,
        "src.cli.attachment",
        "add",
        "-d",
        db,
        "--type",
        "entity",
        "--id",
        entity_id,
        str(image_path),
    )
    assert added_second.returncode == 0, added_second.stderr
    updated = invoke(
        env,
        "src.cli.attachment",
        "caption",
        "-d",
        db,
        "--id",
        attachments[0]["id"],
        "--caption",
        "Portrait",
    )
    assert updated.returncode == 0, updated.stderr
    current = json.loads(
        invoke(
            env,
            "src.cli.attachment",
            "list",
            "-d",
            db,
            "--type",
            "entity",
            "--id",
            entity_id,
            "--json",
        ).stdout
    )
    ids = [item["id"] for item in current]
    reordered = invoke(
        env,
        "src.cli.attachment",
        "reorder",
        "-d",
        db,
        "--type",
        "entity",
        "--id",
        entity_id,
        "--ids",
        ",".join(reversed(ids)),
    )
    assert reordered.returncode == 0, reordered.stderr
    removed = invoke(
        env,
        "src.cli.attachment",
        "remove",
        "-d",
        db,
        "--id",
        ids[0],
        "--force",
    )
    assert removed.returncode == 0, removed.stderr
    marker_deleted = invoke(
        env,
        "src.cli.map",
        "marker-delete",
        "-d",
        db,
        "--id",
        marker_id,
        "--force",
    )
    assert marker_deleted.returncode == 0, marker_deleted.stderr
    map_updated = invoke(
        env,
        "src.cli.map",
        "update",
        "-d",
        db,
        "--id",
        map_id,
        "--name",
        "Atlas II",
    )
    assert map_updated.returncode == 0, map_updated.stderr
    map_deleted = invoke(
        env,
        "src.cli.map",
        "delete",
        "-d",
        db,
        "--id",
        map_id,
        "--force",
    )
    assert map_deleted.returncode == 0, map_deleted.stderr


def test_relation_calendar_timeline_wiki_and_exports(cli_world, tmp_path):
    world, env = cli_world
    db = str(world.db_path)

    def run(group, action, *options):
        result = invoke(env, "src.cli.cli", group, action, "-d", db, *options)
        assert result.returncode == 0, (group, action, result.stderr, result.stdout)
        return result

    first = json.loads(
        run(
            "entity", "create", "--name", "Mara", "--type", "character", "--json"
        ).stdout
    )["id"]
    second = json.loads(
        run("entity", "create", "--name", "North", "--type", "place", "--json").stdout
    )["id"]
    run("relation", "add", "--source", first, "--target", second, "--type", "visits")
    relations = json.loads(run("relation", "list", "--source", first, "--json").stdout)
    assert len(relations["outgoing"]) == 1
    relation_id = relations["outgoing"][0]["id"]
    run("relation", "update", "--id", relation_id, "--type", "knows")

    run(
        "calendar",
        "create",
        "--name",
        "Test Calendar",
        "--months",
        "Spring:30,Summer:30",
        "--week",
        "One,Two",
    )
    calendars = json.loads(run("calendar", "list", "--json").stdout)
    calendar_id = calendars[0]["id"]
    run("calendar", "show", "--id", calendar_id, "--json")
    run("calendar", "set-active", "--id", calendar_id)
    run("timeline", "group", "--tags", "journey")
    run("timeline", "clear")
    run("timeline", "tag-color", "--tag", "journey", "--color", "#445566")
    run("wiki", "scan", "--source", first)

    graph_path = tmp_path / "graph.json"
    run("graph", "export", "--out-file", str(graph_path))
    assert isinstance(json.loads(graph_path.read_text(encoding="utf-8")), dict)
    longform_path = tmp_path / "longform.md"
    run("longform", "export", "--output", str(longform_path))
    assert longform_path.is_file()
    vault_path = tmp_path / "vault"
    run("obsidian", "export", "--out-dir", str(vault_path))
    assert vault_path.is_dir()
    run("relation", "delete", "--id", relation_id, "--force")
    run("calendar", "delete", "--id", calendar_id, "--force")
    assert json.loads(run("calendar", "list", "--json").stdout) == []


def test_index_action_usage_and_dispatch(cli_world):
    world, env = cli_world
    for action in ("rebuild", "index-object", "query", "delete-object"):
        for entry in (("src.cli.cli", "index"), ("src.cli.index",)):
            help_result = invoke(env, *entry, action, "--help")
            assert help_result.returncode == 0, help_result.stderr
            assert "--database" in help_result.stdout
            missing = invoke(env, *entry, action)
            assert missing.returncode == 2


def test_index_handlers_run_from_both_parsers(cli_world, monkeypatch, capsys):
    world, _ = cli_world
    provider = MagicMock()
    provider.rebuild_index.return_value = SimpleNamespace(per_type={}, failed=0)
    provider.query.return_value = []
    monkeypatch.setattr(index_cli, "create_search_service", lambda *a, **k: provider)
    actions = (
        ("rebuild", []),
        ("index-object", ["--type", "entity", "--id", "fixture-id"]),
        ("query", ["--text", "Mara", "--json"]),
        ("delete-object", ["--type", "entity", "--id", "fixture-id"]),
    )
    for entry in ("src.cli.index", "src.cli.cli"):
        for action, options in actions:
            prefix = ["index"] if entry == "src.cli.cli" else []
            monkeypatch.setattr(
                sys,
                "argv",
                [entry, *prefix, action, "-d", str(world.db_path), *options],
            )
            if entry == "src.cli.cli":
                with pytest.raises(SystemExit) as outcome:
                    unified_cli.main()
                assert outcome.value.code == 0
            else:
                assert index_cli.main() == 0
            output = capsys.readouterr().out
            if action == "query":
                assert json.loads(output) == []
    assert provider.rebuild_index.call_count == 2
    assert provider.index_entity.call_count == 2
    assert provider.delete_index_for_object.call_count == 2


def test_import_targets_only_selected_world(cli_world, tmp_path):
    target, env = cli_world
    other = World.create(tmp_path, "Other World")
    source = tmp_path / "import.json"
    source.write_text(
        json.dumps({"entities": [{"name": "Imported", "type": "place"}]}),
        encoding="utf-8",
    )
    imported = invoke(
        env,
        "src.app.main",
        "import",
        "--file",
        str(source),
        "--database",
        str(target.db_path),
    )
    assert imported.returncode == 0, imported.stderr
    assert str(target.db_path) in imported.stderr
    selected = invoke(
        env, "src.cli.entity", "list", "-d", str(target.db_path), "--json"
    )
    untouched = invoke(
        env, "src.cli.entity", "list", "-d", str(other.db_path), "--json"
    )
    assert len(json.loads(selected.stdout)) == 1
    assert json.loads(untouched.stdout) == []


def test_import_active_world_fallback_uses_registered_manifest(
    cli_world, monkeypatch, tmp_path
):
    world, _ = cli_world
    other = World.create(tmp_path, "Other World")
    monkeypatch.setattr(importer, "get_worlds_dir", lambda: tmp_path)
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    storage = WorldStorageSettings(settings)
    storage.set_active_world_path(world.path)
    assert importer._resolve_import_world(None).db_path == world.db_path
    assert importer._resolve_import_world(str(other.db_path)).db_path == other.db_path
    storage.set_active_world_path(tmp_path / "missing")
    assert importer._resolve_import_world(None) is None


def test_backup_create_list_and_restore_new_target(cli_world, tmp_path):
    world, env = cli_world
    db = str(world.db_path)
    created = invoke(
        env,
        "src.cli.entity",
        "create",
        "-d",
        db,
        "--name",
        "Saved",
        "--type",
        "place",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    backup = invoke(env, "src.cli.cli", "backup", "create", "-d", db)
    assert backup.returncode == 0, backup.stderr
    backups = list(_backup_directory(tmp_path).rglob("*.kraken"))
    assert len(backups) == 1
    listed = invoke(env, "src.cli.backup", "list", "-d", db)
    assert listed.returncode == 0, listed.stderr
    assert backups[0].name in listed.stdout
    target = tmp_path / "restored.kraken"
    restored = invoke(
        env,
        "src.cli.cli",
        "backup",
        "restore",
        "-d",
        str(target),
        "--file",
        str(backups[0]),
        "--force",
    )
    assert restored.returncode == 0, restored.stderr
    assert target.is_file()
    entities = invoke(env, "src.cli.entity", "list", "-d", str(target), "--json")
    assert [item["name"] for item in json.loads(entities.stdout)] == ["Saved"]


def test_legacy_attachment_repair_is_previewed_and_backed_up(cli_world, tmp_path):
    world, env = cli_world
    db = str(world.db_path)
    owner = json.loads(
        invoke(
            env,
            "src.cli.entity",
            "create",
            "-d",
            db,
            "--name",
            "Owner",
            "--type",
            "character",
            "--json",
        ).stdout
    )["id"]
    source = tmp_path / "old.png"
    Image.new("RGB", (4, 4), "white").save(source)
    image_rel, thumb_rel, size = AssetStore(str(world.path)).import_image(
        "entities", owner, str(source)
    )
    legacy_id = Path(image_rel).stem
    service = DatabaseService(db)
    service.connect()
    service.get_attachment_repo().insert(
        ImageAttachment(
            id=legacy_id,
            owner_type="entities",
            owner_id=owner,
            image_rel_path=image_rel,
            thumb_rel_path=thumb_rel,
            resolution=size,
        )
    )
    service.close()

    preview = invoke(env, "src.cli.attachment", "repair-legacy", "-d", db)
    assert preview.returncode == 0, preview.stderr
    assert "Legacy attachment records: 1" in preview.stdout
    before = invoke(
        env,
        "src.cli.attachment",
        "list",
        "-d",
        db,
        "--type",
        "entity",
        "--id",
        owner,
        "--json",
    )
    assert json.loads(before.stdout) == []
    asset_path = world.path / image_rel
    hidden = asset_path.with_suffix(".hidden")
    asset_path.rename(hidden)
    refused = invoke(
        env,
        "src.cli.attachment",
        "repair-legacy",
        "-d",
        db,
        "--apply",
        "--force",
    )
    assert refused.returncode == 1
    assert "Missing or unsafe asset" in refused.stderr
    hidden.rename(asset_path)
    applied = invoke(
        env,
        "src.cli.cli",
        "attachment",
        "repair-legacy",
        "-d",
        db,
        "--apply",
        "--force",
    )
    assert applied.returncode == 0, applied.stderr
    assert "Recovery backup:" in applied.stderr
    backups = list(_backup_directory(tmp_path).rglob("*.kraken"))
    assert len(backups) == 1
    after = invoke(
        env,
        "src.cli.attachment",
        "list",
        "-d",
        db,
        "--type",
        "entity",
        "--id",
        owner,
        "--json",
    )
    assert json.loads(after.stdout)[0]["id"] == legacy_id
    assert asset_path.is_file()
