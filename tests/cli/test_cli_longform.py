import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest

from src.cli.longform import main as longform_main
from src.core.entities import Entity
from src.services.db_service import DatabaseService
from src.services.longform_builder import get_longform_meta

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def mock_db():
    with patch("src.cli.longform.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.longform.validate_database_path", return_value=True) as mock:
        yield mock


def test_longform_export(mock_db, mock_validate, capsys):
    with patch(
        "src.cli.longform.longform_builder.export_longform_to_markdown",
        return_value="# Doc Content",
    ):
        with patch("sys.argv", ["longform.py", "export", "-d", "test.db"]):
            with pytest.raises(SystemExit) as e:
                longform_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "# Doc Content" in out


def test_longform_add(mock_db, mock_validate, capsys):
    # 'add' is move_entry but with logic to handle missing meta
    with patch("src.cli.longform.MoveLongformEntryCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_db.get_name.return_value = "Test Event"

        # Mock _get_current_meta to return {}
        with patch("src.cli.longform._get_current_meta", return_value={}):
            with patch(
                "sys.argv",
                [
                    "longform.py",
                    "add",
                    "-d",
                    "test.db",
                    "--table",
                    "events",
                    "--id",
                    "ev1",
                ],
            ):
                with pytest.raises(SystemExit) as e:
                    longform_main()
                assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Moved/Added entry: ev1" in out
        MockCmd.assert_called_once()


def test_longform_promote(mock_db, mock_validate, capsys):
    with patch("src.cli.longform.PromoteLongformEntryCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "src.cli.longform._get_current_meta", return_value={"position": 100}
        ):
            with patch(
                "sys.argv",
                [
                    "longform.py",
                    "promote",
                    "-d",
                    "test.db",
                    "--table",
                    "events",
                    "--id",
                    "ev1",
                ],
            ):
                with pytest.raises(SystemExit) as e:
                    longform_main()
                assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Promoted entry: ev1" in out
        MockCmd.assert_called_once()


def test_real_world_cli_metadata_and_reopen(db_service, tmp_path):
    """CLI mutations operate on canonical metadata and survive reopening."""
    parent = Entity(name="Parent", type="test")
    child = Entity(name="Child", type="test")
    db_service.insert_entity(parent)
    db_service.insert_entity(child)
    path = tmp_path / "cli.kraken"
    with closing(sqlite3.connect(path)) as destination:
        db_service.require_connection().backup(destination)

    def run(command, *options):
        with patch("sys.argv", ["longform.py", command, "-d", str(path), *options]):
            with pytest.raises(SystemExit) as result:
                longform_main()
        assert result.value.code == 0

    def read_meta(record_id):
        service = DatabaseService(str(path), read_only=True)
        try:
            service.connect()
            return get_longform_meta(service.require_connection(), "entities", record_id)
        finally:
            service.close()

    parent_args = ("--table", "entities", "--id", parent.id)
    child_args = ("--table", "entities", "--id", child.id)
    run("add", *parent_args, "--position", "250")
    run("add", *child_args, "--position", "750")
    assert read_meta(parent.id)["position"] == 250
    run("demote", *child_args)
    assert read_meta(child.id)["parent_id"] == parent.id
    assert read_meta(child.id)["depth"] == 1
    run("promote", *child_args)
    assert read_meta(child.id)["parent_id"] is None
    assert read_meta(child.id)["depth"] == 0
    run("move", *child_args, "--position", "900")
    assert read_meta(child.id)["position"] == 900
    run("reindex")
    assert read_meta(parent.id)["position"] == 100
    assert read_meta(child.id)["position"] == 200
    run("remove", *child_args)
    assert read_meta(child.id)["excluded"] is True
    output = tmp_path / "outline.md"
    run("export", "--output", str(output))
    assert "Parent" in output.read_text(encoding="utf-8")
    # Export respects deliberate document membership and never re-adds removals.
    assert read_meta(child.id)["excluded"] is True
    assert "Child" not in output.read_text(encoding="utf-8")


def test_longform_reindex(mock_db, mock_validate, capsys):
    with patch(
        "src.cli.longform.longform_builder.reindex_document_positions"
    ) as mock_reindex:
        with patch("sys.argv", ["longform.py", "reindex", "-d", "test.db"]):
            with pytest.raises(SystemExit) as e:
                longform_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Reindexed longform" in out
        mock_reindex.assert_called_once()
