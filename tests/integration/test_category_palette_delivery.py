"""Real worker delivery allocates persisted colors without GUI-thread SQL."""

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal

from src.app.category_palette_composition import compose_category_palette
from src.commands.entity_commands import CreateEntityCommand
from src.core.category_palette import category_key
from src.gui.widgets.unified_list import UnifiedListWidget
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.integration, pytest.mark.real_qt_invoke]


class Requests(QObject):
    initialize = Signal()
    command = Signal(object)
    cleanup = Signal()


def test_worker_allocates_new_types_and_gui_rejects_stale_world_results(
    qapp, qtbot, tmp_path
):
    path = str(tmp_path / "palette.kraken")
    thread = QThread()
    worker = DatabaseWorker(path, {"CreateEntityCommand": CreateEntityCommand})
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    view = UnifiedListWidget()
    qtbot.addWidget(view)
    parent = QObject()
    # Composition receives the same narrow shell attributes as the real startup.
    parent.worker = worker
    parent.worker_thread = thread
    parent.db_path = path
    parent.unified_list = view
    coordinator = compose_category_palette(parent)
    requests = Requests()
    queued = Qt.ConnectionType.QueuedConnection
    requests.initialize.connect(worker.initialize_db, queued)
    requests.command.connect(worker.run_command, queued)
    requests.cleanup.connect(worker.cleanup, queued)
    provider_threads = []
    original = coordinator._task._database

    def provider():
        provider_threads.append(QThread.currentThread())
        return original()

    coordinator._task._database = provider
    received = []
    publish = coordinator._publish

    def observe(snapshot):
        assert QThread.currentThread() == qapp.thread()
        received.append(dict(snapshot))
        publish(snapshot)

    coordinator._publish = observe
    thread.start()
    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000):
            requests.initialize.emit()
        for name in ("Character", "Concept", "Deity"):
            with qtbot.waitSignal(worker.command_finished, timeout=5000) as result:
                requests.command.emit(
                    {
                        "type": "CreateEntityCommand",
                        "data": CreateEntityCommand(
                            {"name": name, "type": name}
                        ).to_dict(),
                    }
                )
            assert result.args[0].success
        qtbot.waitUntil(
            lambda: len(view._model._category_assignments) == 3, timeout=5000
        )
        saved = dict(view._model._category_assignments)
        assert len(set(saved.values())) == 3
        with qtbot.waitSignal(worker.command_finished, timeout=5000):
            requests.command.emit(
                {
                    "type": "CreateEntityCommand",
                    "data": CreateEntityCommand(
                        {"name": "Faith", "type": "Religion"}
                    ).to_dict(),
                }
            )
        qtbot.waitUntil(
            lambda: len(view._model._category_assignments) == 4, timeout=5000
        )
        assert all(
            view._model._category_assignments[key] == slot
            for key, slot in saved.items()
        )
        assert (
            view._model._category_assignments[category_key("entity", "Religion")]
            not in saved.values()
        )
        stale = {
            "database": path,
            "generation": coordinator._generation,
            "sequence": coordinator._sequence,
            "assignments": saved,
        }
        coordinator.initialized(False)
        coordinator._receive(stale)
        assert view._model._category_assignments == {}
        assert all(t == thread and t != qapp.thread() for t in provider_threads)
    finally:
        coordinator.shutdown()
        with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
            requests.cleanup.emit()
        thread.quit()
        assert thread.wait(5000)
