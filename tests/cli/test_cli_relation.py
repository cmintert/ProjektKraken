from unittest.mock import patch

import pytest

from src.cli.relation import main as relation_main


@pytest.fixture
def mock_db():
    with patch("src.cli.relation.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.relation.validate_database_path", return_value=True) as mock:
        yield mock


def test_relation_add(mock_db, mock_validate, capsys):
    with patch("src.cli.relation.AddRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value = True

        with patch(
            "sys.argv",
            [
                "relation.py",
                "add",
                "-d",
                "test.db",
                "-s",
                "e1",
                "-t",
                "e2",
                "--type",
                "friend",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                relation_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Added relation" in out
        MockCmd.assert_called_once()
        args = MockCmd.call_args[0]
        assert args[0] == "e1"
        assert args[1] == "e2"
        assert args[2] == "friend"


def test_relation_list(mock_db, mock_validate, capsys):
    mock_db.get_relations.return_value = [
        {"id": "r1", "target_id": "e2", "rel_type": "friend", "attributes": {}}
    ]
    mock_db.get_incoming_relations.return_value = []
    mock_db.get_name.side_effect = lambda x: "Target" if x == "e2" else "Source"

    with patch("sys.argv", ["relation.py", "list", "-d", "test.db", "--source", "e1"]):
        with pytest.raises(SystemExit) as e:
            relation_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "Outgoing (1):" in out
    assert "friend" in out


def test_relation_update(mock_db, mock_validate, capsys):
    with patch("src.cli.relation.UpdateRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value = True
        mock_db.get_relation.return_value = {
            "id": "r1",
            "target_id": "e2",
            "rel_type": "friend",
        }

        with patch(
            "sys.argv",
            ["relation.py", "update", "-d", "test.db", "--id", "r1", "--type", "enemy"],
        ):
            with pytest.raises(SystemExit) as e:
                relation_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated relation: r1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][2] == "enemy"


def test_relation_delete(mock_db, mock_validate, capsys):
    with patch("src.cli.relation.RemoveRelationCommand") as MockCmd:
        mock_cmd_instance = MockCmd.return_value
        mock_cmd_instance.execute.return_value = True

        with patch(
            "sys.argv",
            ["relation.py", "delete", "-d", "test.db", "--id", "r1", "--force"],
        ):
            with pytest.raises(SystemExit) as e:
                relation_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Deleted relation: r1" in out
        MockCmd.assert_called_once()
        assert MockCmd.call_args[0][0] == "r1"
