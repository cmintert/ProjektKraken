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
