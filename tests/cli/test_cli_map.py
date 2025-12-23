from unittest.mock import MagicMock, patch

import pytest

from src.cli.map import main as map_main


@pytest.fixture
def mock_db():
    with patch("src.cli.map.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.map.validate_database_path", return_value=True) as mock:
        yield mock


def test_map_create_success(mock_db, mock_validate, capsys):
    with patch("src.cli.map.CreateMapCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_cmd_instance.execute.return_value.data = {"id": "new-map-id"}

        with patch(
            "sys.argv",
            [
                "map.py",
                "create",
                "-d",
                "test.db",
                "--name",
                "World Map",
                "--image",
                "world.png",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Created map: new-map-id" in out
        MockCmd.assert_called_once()
        args = MockCmd.call_args[0][0]
        assert args["name"] == "World Map"
        assert args["image_path"] == "world.png"


def test_map_list(mock_db, mock_validate, capsys):
    mock_map = MagicMock()
    mock_map.to_dict.return_value = {
        "id": "map1",
        "name": "Map1",
        "image_path": "img.png",
    }
    mock_map.id = "map1"
    mock_map.name = "Map1"
    mock_map.image_path = "img.png"
    mock_db.get_all_maps.return_value = [mock_map]

    with patch("sys.argv", ["map.py", "list", "-d", "test.db"]):
        with pytest.raises(SystemExit) as e:
            map_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Found 1 map" in out
    assert "Map1" in out


def test_map_update(mock_db, mock_validate, capsys):
    with patch("src.cli.map.UpdateMapCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "sys.argv",
            ["map.py", "update", "-d", "test.db", "--id", "map1", "--name", "NewName"],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated map: map1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "map1"
        assert MockCmd.call_args[0][1]["name"] == "NewName"


def test_map_delete(mock_db, mock_validate, capsys):
    with patch("src.cli.map.DeleteMapCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        # Mock get_map for safety check
        mock_map = MagicMock()
        mock_map.name = "MapToDelete"
        mock_db.get_map.return_value = mock_map

        with patch(
            "sys.argv",
            ["map.py", "delete", "-d", "test.db", "--id", "map1", "--force"],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Deleted map: map1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "map1"


def test_marker_add(mock_db, mock_validate, capsys):
    with patch("src.cli.map.CreateMarkerCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_cmd_instance.execute.return_value.data = {"id": "marker1"}

        with patch(
            "sys.argv",
            [
                "map.py",
                "marker-add",
                "-d",
                "test.db",
                "--map-id",
                "map1",
                "--object-id",
                "obj1",
                "--object-type",
                "entity",
                "--x",
                "100",
                "--y",
                "200",
                "--label",
                "MyMarker",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Added marker: marker1" in out
        MockCmd.assert_called_once()
        args = MockCmd.call_args[0][0]
        assert args["map_id"] == "map1"
        assert args["x"] == 100.0
        assert args["label"] == "MyMarker"


def test_marker_update(mock_db, mock_validate, capsys):
    with patch("src.cli.map.UpdateMarkerCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "sys.argv",
            [
                "map.py",
                "marker-update",
                "-d",
                "test.db",
                "--id",
                "marker1",
                "--x",
                "150",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated marker: marker1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "marker1"
        assert MockCmd.call_args[0][1]["x"] == 150.0


def test_marker_delete(mock_db, mock_validate, capsys):
    with patch("src.cli.map.DeleteMarkerCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        # Mock get_marker for safety check
        mock_marker = MagicMock()
        mock_marker.label = "MarkerToDelete"
        mock_db.get_marker.return_value = mock_marker

        with patch(
            "sys.argv",
            ["map.py", "marker-delete", "-d", "test.db", "--id", "marker1", "--force"],
        ):
            with pytest.raises(SystemExit) as e:
                map_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Deleted marker: marker1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "marker1"


def test_marker_list(mock_db, mock_validate, capsys):
    mock_marker = MagicMock()
    mock_marker.to_dict.return_value = {
        "id": "marker1",
        "object_type": "entity",
        "object_id": "ent1",
        "x": 10,
        "y": 20,
    }
    mock_marker.id = "marker1"
    mock_marker.object_type = "entity"
    mock_marker.object_id = "ent1"
    mock_marker.x = 10
    mock_marker.y = 20
    mock_marker.label = "Label"
    mock_marker.attributes = {}

    mock_db.get_markers_for_map.return_value = [mock_marker]

    with patch(
        "sys.argv", ["map.py", "marker-list", "-d", "test.db", "--map-id", "map1"]
    ):
        with pytest.raises(SystemExit) as e:
            map_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Found 1 marker" in out
    assert "marker1" in out
