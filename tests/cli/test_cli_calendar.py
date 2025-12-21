import pytest
from unittest.mock import patch, MagicMock
from src.cli.calendar import main as calendar_main


@pytest.fixture
def mock_db():
    with patch("src.cli.calendar.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.calendar.validate_database_path", return_value=True) as mock:
        yield mock


def test_calendar_create(mock_db, mock_validate, capsys):
    with patch("src.cli.calendar.CreateCalendarConfigCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value.success = True

        with patch(
            "sys.argv", ["calendar.py", "create", "-d", "test.db", "-n", "Fantasy"]
        ):
            with pytest.raises(SystemExit) as e:
                calendar_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Created calendar" in out
        MockCmd.assert_called_once()


def test_calendar_list(mock_db, mock_validate, capsys):
    mock_conf = MagicMock()
    mock_conf.id = "c1"
    mock_conf.name = "Fantasy"
    mock_conf.epoch_name = "Era"
    mock_conf.is_active = True
    mock_conf.months = []
    mock_db.get_all_calendar_configs.return_value = [mock_conf]

    with patch("sys.argv", ["calendar.py", "list", "-d", "test.db"]):
        with pytest.raises(SystemExit) as e:
            calendar_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Fantasy" in out
    assert "ACTIVE" in out


def test_calendar_set_active(mock_db, mock_validate, capsys):
    with patch("src.cli.calendar.SetActiveCalendarCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value.success = True

        with patch(
            "sys.argv", ["calendar.py", "set-active", "-d", "test.db", "--id", "c1"]
        ):
            with pytest.raises(SystemExit) as e:
                calendar_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "is now active" in out
        MockCmd.assert_called_once()
