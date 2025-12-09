import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """
    Ensure QApplication is instantiated only once.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_service():
    """
    Provides a fresh in-memory database service for each test.
    """
    from src.services.db_service import DatabaseService

    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture(autouse=True)
def mock_invoke_method():
    """
    Mocks QMetaObject.invokeMethod to prevent TypeErrors when called with MagicMocks
    and to allow verifying thread-safe calls.
    """
    from unittest.mock import patch

    with patch("PySide6.QtCore.QMetaObject.invokeMethod") as mock:
        yield mock
