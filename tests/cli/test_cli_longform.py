from unittest.mock import patch

import pytest

from src.cli.longform import main as longform_main


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
