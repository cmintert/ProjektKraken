from unittest.mock import MagicMock, patch

import pytest

from src.cli.map import main as map_main
from src.cli.wiki import main as wiki_main

# --- Map CLI Tests ---


@patch("src.cli.map.validate_database_path", return_value=True)
@patch("src.cli.map.DatabaseService")
@patch("src.cli.map.CreateMapCommand")
@patch("sys.argv", ["map.py", "create", "--database", "test.db", "--name", "Test Map"])
def test_map_create(MockCommand, MockDB, MockValidate, capsys):
    mock_cmd_instance = MockCommand.return_value
    mock_cmd_instance.execute.return_value.success = True
    mock_cmd_instance.execute.return_value.data = {"id": "new-map-id"}

    with pytest.raises(SystemExit) as e:
        map_main()

    assert e.value.code == 0
    MockCommand.assert_called_once()
    assert MockCommand.call_args[0][0]["name"] == "Test Map"


@patch("src.cli.map.validate_database_path", return_value=True)
@patch("src.cli.map.DatabaseService")
@patch("src.cli.map.CreateMarkerCommand")
@patch(
    "sys.argv",
    [
        "map.py",
        "marker-add",
        "--database",
        "test.db",
        "--map-id",
        "m1",
        "--object-id",
        "o1",
        "--object-type",
        "event",
        "--x",
        "10",
        "--y",
        "20",
    ],
)
def test_map_add_marker(MockCommand, MockDB, MockValidate):
    mock_cmd_instance = MockCommand.return_value
    mock_cmd_instance.execute.return_value.success = True
    mock_cmd_instance.execute.return_value.data = {"id": "marker-id"}

    with pytest.raises(SystemExit) as e:
        map_main()
    assert e.value.code == 0
    MockCommand.assert_called_once()
    args = MockCommand.call_args[0][0]
    assert args["x"] == 10.0
    assert args["y"] == 20.0


# --- Wiki CLI Tests ---


@patch("src.cli.wiki.validate_database_path", return_value=True)
@patch("src.cli.wiki.DatabaseService")
@patch("src.cli.wiki.ProcessWikiLinksCommand")
@patch("sys.argv", ["wiki.py", "scan", "--database", "test.db", "--source", "ent1"])
def test_wiki_scan(MockCommand, MockDB, MockValidate):
    mock_db = MockDB.return_value
    # Mock finding the object
    mock_entity = MagicMock()
    mock_entity.description = "Some text with [[WikiLinks]]."
    mock_db.get_entity.return_value = mock_entity

    mock_cmd = MockCommand.return_value
    mock_cmd.execute.return_value.success = True
    mock_cmd.execute.return_value.message = "Scanned successfully"

    with pytest.raises(SystemExit) as e:
        wiki_main()
    assert e.value.code == 0
    MockCommand.assert_called_once()
    assert MockCommand.call_args[0][1] == "Some text with [[WikiLinks]]."
