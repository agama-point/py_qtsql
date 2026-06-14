from __future__ import annotations

import sys

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from qtsql_ui import MainWindow
from qtsql_worker import QtSqlWorker


def main() -> int:
    app = QApplication(sys.argv)

    worker_thread = QThread()
    worker = QtSqlWorker()
    worker.moveToThread(worker_thread)

    window = MainWindow()
    window.action_requested.connect(worker.run_action)
    worker.log_signal.connect(window.append_debug)
    worker.status_signal.connect(window.set_status)
    worker.key_signal.connect(window.set_key)
    worker.rows_signal.connect(window.set_records)
    worker.edit_record_signal.connect(window.load_record_for_edit)
    worker.info_record_signal.connect(window.show_record_info)
    worker.error_signal.connect(window.show_error)
    worker_thread.started.connect(worker.initialize)

    app.aboutToQuit.connect(worker_thread.quit)
    worker_thread.finished.connect(worker.deleteLater)

    worker_thread.start()
    window.show()
    exit_code = app.exec()
    worker_thread.wait(3000)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
