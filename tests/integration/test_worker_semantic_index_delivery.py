"""Real queued semantic indexing stays on the database worker thread."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal

from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.integration, pytest.mark.real_qt_invoke]


class _IndexRequests(QObject):
    index = Signal(str, str, list)


def test_queued_index_uses_worker_thread_and_delivers_existing_signal(qapp, qtbot):
    thread = QThread()
    worker = DatabaseWorker("test.db")
    worker.db_service = MagicMock()
    requests = _IndexRequests()
    calls = []
    search = MagicMock()

    def index_entity(object_id, exclusions):
        calls.append((QThread.currentThread(), object_id, exclusions))

    search.index_entity.side_effect = index_entity
    worker.moveToThread(thread)
    requests.index.connect(worker.index_object, Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    try:
        with patch(
            "src.services.search_service.create_search_service", return_value=search
        ) as create:
            with qtbot.waitSignal(worker.operation_finished, timeout=5000) as result:
                requests.index.emit("entity", "queued-id", ["private"])

        assert result.args == ["Indexed entity queued-id."]
        assert calls == [(thread, "queued-id", ["private"])]
        create.assert_called_once()
        worker.db_service.get_connection.assert_called_once()
        assert qapp.thread() != thread
    finally:
        thread.quit()
        assert thread.wait(5000)
