import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli.obsidian import export_obsidian
from src.services.obsidian_exporter import ExportResult


@pytest.fixture
def mock_db_service():
    with patch("src.cli.obsidian.DatabaseService") as mock:
        yield mock


@pytest.fixture
def mock_exporter():
    with patch("src.cli.obsidian.ObsidianExporter") as mock:
        yield mock


def test_export_obsidian_success(mock_db_service, mock_exporter, tmp_path):
    """Test successful obsidian export."""
    args = argparse.Namespace(
        database="world.kraken",
        out_dir=str(tmp_path),
        no_relations=False,
        verbose=False,
    )

    exporter_instance = mock_exporter.return_value
    exporter_instance.export_to_folder.return_value = ExportResult(
        success=True, files_created=10, output_dir=tmp_path, errors=[]
    )

    assert export_obsidian(args) == 0
    exporter_instance.export_to_folder.assert_called_with(
        Path(str(tmp_path)), include_relations=True
    )


def test_export_obsidian_no_relations(mock_db_service, mock_exporter, tmp_path):
    """Test obsidian export without relations."""
    args = argparse.Namespace(
        database="world.kraken", out_dir=str(tmp_path), no_relations=True, verbose=False
    )

    exporter_instance = mock_exporter.return_value
    exporter_instance.export_to_folder.return_value = ExportResult(
        success=True, files_created=5, output_dir=tmp_path, errors=[]
    )

    assert export_obsidian(args) == 0
    exporter_instance.export_to_folder.assert_called_with(
        Path(str(tmp_path)), include_relations=False
    )


def test_export_obsidian_failure(mock_db_service, mock_exporter, tmp_path):
    """Test failed obsidian export."""
    args = argparse.Namespace(
        database="world.kraken",
        out_dir=str(tmp_path),
        no_relations=False,
        verbose=False,
    )

    exporter_instance = mock_exporter.return_value
    exporter_instance.export_to_folder.return_value = ExportResult(
        success=False,
        files_created=0,
        output_dir=tmp_path,
        errors=["Permission denied"],
    )

    assert export_obsidian(args) == 1
