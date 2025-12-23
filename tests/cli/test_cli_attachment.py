from unittest.mock import MagicMock, patch

import pytest

from src.cli.attachment import main as attachment_main


@pytest.fixture
def mock_db():
    with patch("src.cli.attachment.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.connect.return_value = None
        mock_instance.attachment_service = MagicMock()
        yield mock_instance


@pytest.fixture
def mock_validate():
    with patch("src.cli.attachment.validate_database_path", return_value=True) as mock:
        yield mock


def test_attachment_add(mock_db, mock_validate, capsys):
    with patch("src.cli.attachment.AddImagesCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value.success = True
        mock_cmd.execute.return_value.message = "Added 1 images"

        with patch(
            "sys.argv",
            [
                "attachment.py",
                "add",
                "-d",
                "test.db",
                "--type",
                "entities",
                "--id",
                "e1",
                "img.png",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                attachment_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Added 1 images" in out
        MockCmd.assert_called_once()


def test_attachment_list(mock_db, mock_validate, capsys):
    mock_att = MagicMock()
    mock_att.id = "a1"
    mock_att.filename = "img.png"
    mock_att.caption = "Cap"
    mock_att.position = 0
    mock_db.attachment_service.get_attachments.return_value = [mock_att]

    with patch(
        "sys.argv",
        ["attachment.py", "list", "-d", "test.db", "--type", "entities", "--id", "e1"],
    ):
        with pytest.raises(SystemExit) as e:
            attachment_main()
        assert e.value.code == 0

    out, _ = capsys.readouterr()
    assert "img.png" in out
    assert "Cap" in out


def test_attachment_update_caption(mock_db, mock_validate, capsys):
    with patch("src.cli.attachment.UpdateImageCaptionCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value.success = True

        with patch(
            "sys.argv",
            [
                "attachment.py",
                "caption",
                "-d",
                "test.db",
                "--id",
                "a1",
                "-c",
                "New Cap",
            ],
        ):
            with pytest.raises(SystemExit) as e:
                attachment_main()
            assert e.value.code == 0

        out, _ = capsys.readouterr()
        assert "Updated caption" in out
        MockCmd.assert_called_once()
