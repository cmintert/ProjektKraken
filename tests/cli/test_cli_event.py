import pytest
from unittest.mock import patch, MagicMock
from src.cli.event import main as event_main


@pytest.fixture
def mock_db():
    with patch("src.cli.event.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.event.validate_database_path", return_value=True) as mock:
        yield mock


def test_event_create_success(mock_db, mock_validate, capsys):
    with patch("src.cli.event.CreateEventCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_cmd_instance.execute.return_value.data = {"id": "new-event-id"}

        with patch(
            "sys.argv",
            ["event.py", "create", "-d", "test.db", "-n", "Battle", "--date", "123.4"],
        ):
            with pytest.raises(SystemExit) as e:
                event_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Created event: new-event-id" in out
        MockCmd.assert_called_once()
        args = MockCmd.call_args[0][0]
        assert args["name"] == "Battle"
        assert args["lore_date"] == 123.4


def test_event_list(mock_db, mock_validate, capsys):
    mock_event = MagicMock()
    mock_event.to_dict.return_value = {
        "id": "ev1",
        "name": "Event1",
        "lore_date": 100.0,
    }
    mock_event.id = "ev1"
    mock_event.name = "Event1"
    mock_event.lore_date = 100.0
    mock_db.get_events.return_value = [mock_event]
    mock_db.get_all_events.return_value = [mock_event]

    with patch("sys.argv", ["event.py", "list", "-d", "test.db"]):
        with pytest.raises(SystemExit) as e:
            event_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Found 1 event" in out
    assert "Event1" in out


def test_event_show(mock_db, mock_validate, capsys):
    mock_event = MagicMock()
    mock_event.to_dict.return_value = {
        "id": "ev1",
        "name": "Event1",
        "lore_date": 100.0,
        "description": "Desc",
    }
    mock_event.id = "ev1"
    mock_event.name = "Event1"
    mock_event.lore_date = 100.0
    mock_event.description = "Desc"
    mock_event.attributes = {}
    mock_db.get_event.return_value = mock_event
    mock_db.get_relations_for_event.return_value = []

    with patch("sys.argv", ["event.py", "show", "-d", "test.db", "--id", "ev1"]):
        with pytest.raises(SystemExit) as e:
            event_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Event Details" in out
    assert "Name: Event1" in out


def test_event_update(mock_db, mock_validate, capsys):
    with patch("src.cli.event.UpdateEventCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "sys.argv",
            ["event.py", "update", "-d", "test.db", "--id", "ev1", "-n", "NewName"],
        ):
            with pytest.raises(SystemExit) as e:
                event_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated event: ev1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "ev1"
        assert MockCmd.call_args[0][1]["name"] == "NewName"


def test_event_delete(mock_db, mock_validate, capsys):
    with patch("src.cli.event.DeleteEventCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "sys.argv",
            ["event.py", "delete", "-d", "test.db", "--id", "ev1", "--force"],
        ):
            with pytest.raises(SystemExit) as e:
                event_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Deleted event: ev1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "ev1"
