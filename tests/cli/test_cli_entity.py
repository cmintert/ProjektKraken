import pytest
from unittest.mock import patch, MagicMock
from src.cli.entity import main as entity_main


@pytest.fixture
def mock_db():
    with patch("src.cli.entity.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.entity.validate_database_path", return_value=True) as mock:
        yield mock


def test_entity_create_success(mock_db, mock_validate, capsys):
    with patch("src.cli.entity.CreateEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_cmd_instance.execute.return_value.data = {"id": "new-entity-id"}
        mock_cmd_instance.execute.return_value.message = "Success"

        with patch(
            "sys.argv",
            ["entity.py", "create", "-d", "test.db", "-n", "Hero", "-t", "character"],
        ):
            with pytest.raises(SystemExit) as e:
                entity_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Created entity: new-entity-id" in out
        MockCmd.assert_called_once()
        args = MockCmd.call_args[0][0]
        assert args["name"] == "Hero"
        assert args["type"] == "character"


def test_entity_list(mock_db, mock_validate, capsys):
    mock_entity = MagicMock()
    mock_entity.to_dict.return_value = {"id": "e1", "name": "Ent1", "type": "char"}
    mock_entity.id = "e1"
    mock_entity.name = "Ent1"
    mock_entity.type = "char"
    mock_db.get_entities.return_value = [mock_entity]
    mock_db.get_all_entities.return_value = [mock_entity]

    with patch("sys.argv", ["entity.py", "list", "-d", "test.db"]):
        with pytest.raises(SystemExit) as e:
            entity_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Found 1 entity" in out
    assert "Ent1" in out


def test_entity_show(mock_db, mock_validate, capsys):
    mock_entity = MagicMock()
    mock_entity.to_dict.return_value = {
        "id": "e1",
        "name": "Ent1",
        "type": "char",
        "description": "Desc",
    }
    mock_entity.id = "e1"
    mock_entity.name = "Ent1"
    mock_entity.type = "char"
    mock_entity.description = "Desc"
    mock_entity.attributes = {}
    mock_db.get_entity.return_value = mock_entity
    mock_db.get_relations_for_entity.return_value = []

    with patch("sys.argv", ["entity.py", "show", "-d", "test.db", "--id", "e1"]):
        with pytest.raises(SystemExit) as e:
            entity_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Entity Details" in out
    assert "Name: Ent1" in out
    assert "Type: char" in out


def test_entity_update(mock_db, mock_validate, capsys):
    with patch("src.cli.entity.UpdateEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True

        with patch(
            "sys.argv",
            ["entity.py", "update", "-d", "test.db", "--id", "e1", "-n", "NewName"],
        ):
            with pytest.raises(SystemExit) as e:
                entity_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated entity: e1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "e1"
        assert MockCmd.call_args[0][1]["name"] == "NewName"


def test_entity_delete(mock_db, mock_validate, capsys):
    with patch("src.cli.entity.DeleteEntityCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value.success = True
        mock_cmd_instance.execute.return_value.message = "Deleted"

        with patch(
            "sys.argv",
            ["entity.py", "delete", "-d", "test.db", "--id", "e1", "--force"],
        ):
            with pytest.raises(SystemExit) as e:
                entity_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Deleted entity: e1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "e1"
