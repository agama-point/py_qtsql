from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QRegularExpression, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from qtsql_worker import DB_PATH, KEY_NAME


VER = "0.1 | 2026-06"


class MainWindow(QWidget):
    action_requested = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("py_qtsql | SQLite XOR Demo")
        self.resize(1260, 780)
        self.setMinimumSize(980, 620)
        self._rows: list[dict[str, Any]] = []
        self._editing_uid: int | None = None
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([430, 830])
        root.addWidget(splitter, stretch=1)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("Agama QtSQL App")
        title.setObjectName("AppTitle")
        title_row.addWidget(title)
        version = QLabel(f"ver. {VER}")
        version.setObjectName("Version")
        title_row.addWidget(version)
        title_row.addStretch()
        layout.addLayout(title_row)

        layout.addWidget(self._build_key_box())
        layout.addWidget(self._build_record_box())
        layout.addWidget(self._build_filter_box())
        layout.addStretch()
        return panel

    def _build_key_box(self) -> QGroupBox:
        box = QGroupBox("Key")
        layout = QVBoxLayout(box)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("hex XOR key, e.g. 123abc567def")
        self.key_input.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9A-Fa-f]*"), self))
        layout.addWidget(self.key_input)

        row = QHBoxLayout()
        self.show_key_button = QPushButton("Show")
        self.show_key_button.setCheckable(True)
        self.show_key_button.toggled.connect(self.toggle_key_visibility)
        row.addWidget(self.show_key_button)
        save_btn = QPushButton("Edit / Save")
        save_btn.clicked.connect(self.request_save_key)
        row.addWidget(save_btn)
        row.addStretch()
        layout.addLayout(row)

        self.key_hint = QLabel(f"{KEY_NAME} in .env stores raw base16 key input.")
        self.key_hint.setObjectName("Muted")
        self.key_hint.setWordWrap(True)
        layout.addWidget(self.key_hint)
        return box

    def _build_record_box(self) -> QGroupBox:
        box = QGroupBox("DB")
        layout = QVBoxLayout(box)
        self.edit_state_label = QLabel("New record")
        self.edit_state_label.setObjectName("Muted")
        layout.addWidget(self.edit_state_label)
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("number")
        layout.addWidget(self.number_input)
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("text")
        layout.addWidget(self.text_input)
        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("note")
        self.note_input.setMinimumHeight(105)
        layout.addWidget(self.note_input)

        flags = QHBoxLayout()
        self.key1_checkbox = QCheckBox("key1")
        self.key2_checkbox = QCheckBox("key2")
        flags.addWidget(self.key1_checkbox)
        flags.addWidget(self.key2_checkbox)
        flags.addStretch()
        layout.addLayout(flags)

        row = QHBoxLayout()
        new_btn = QPushButton("New record")
        new_btn.clicked.connect(self.request_add_record)
        row.addWidget(new_btn)
        self.save_edit_button = QPushButton("Save edit")
        self.save_edit_button.clicked.connect(self.request_save_edit)
        self.save_edit_button.setEnabled(False)
        row.addWidget(self.save_edit_button)
        cancel_edit_btn = QPushButton("Cancel edit")
        cancel_edit_btn.clicked.connect(self.clear_edit_form)
        row.addWidget(cancel_edit_btn)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.request_load_records)
        row.addWidget(reload_btn)
        row.addStretch()
        layout.addLayout(row)

        self.db_hint = QLabel(str(DB_PATH))
        self.db_hint.setObjectName("Muted")
        layout.addWidget(self.db_hint)
        return box

    def _build_filter_box(self) -> QGroupBox:
        box = QGroupBox("Filter")
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        all_btn = QPushButton("All")
        all_btn.clicked.connect(self.clear_filters)
        row.addWidget(all_btn)
        self.filter_key1_checkbox = QCheckBox("k1")
        self.filter_key1_checkbox.toggled.connect(self.request_load_records)
        row.addWidget(self.filter_key1_checkbox)
        self.filter_key2_checkbox = QCheckBox("k2")
        self.filter_key2_checkbox.toggled.connect(self.request_load_records)
        row.addWidget(self.filter_key2_checkbox)
        row.addStretch()
        layout.addLayout(row)
        return box

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(8)

        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("SQLite status / debug")
        title.setObjectName("Title")
        top.addWidget(title)
        top.addStretch()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("Status")
        top.addWidget(self.status_label)
        copy_btn = QPushButton("Copy log")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.debug_box.toPlainText()))
        top.addWidget(copy_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.debug_box.clear())
        top.addWidget(clear_btn)
        log_layout.addLayout(top)

        self.debug_box = QTextBrowser()
        self.debug_box.setObjectName("VerboseLog")
        log_layout.addWidget(self.debug_box, stretch=1)
        right_splitter.addWidget(log_panel)

        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(8)
        table_header = QHBoxLayout()
        table_title = QLabel("DB records")
        table_title.setObjectName("Title")
        table_header.addWidget(table_title)
        table_header.addStretch()
        self.decode_checkbox = QCheckBox("decode")
        self.decode_checkbox.setChecked(False)
        self.decode_checkbox.toggled.connect(self.request_load_records)
        table_header.addWidget(self.decode_checkbox)
        table_layout.addLayout(table_header)

        self.records_table = QTableWidget(0, 6)
        self.records_table.setObjectName("RecordsTable")
        self.records_table.setHorizontalHeaderLabels(["uid", "number", "text", "note", "key1", "key2"])
        self.records_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.cellClicked.connect(self.request_toggle_key1)
        self.records_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.records_table.customContextMenuRequested.connect(self.show_records_menu)
        header = self.records_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table_layout.addWidget(self.records_table, stretch=1)
        right_splitter.addWidget(table_panel)
        right_splitter.setSizes([280, 500])
        layout.addWidget(right_splitter, stretch=1)
        return panel

    def request_save_key(self) -> None:
        self.action_requested.emit("save_key", {"key": self.current_key()})

    def request_add_record(self) -> None:
        self.action_requested.emit("add_record", self.form_payload())
        self.clear_edit_form()

    def request_save_edit(self) -> None:
        if self._editing_uid is None:
            return
        payload = self.form_payload()
        payload["uid"] = self._editing_uid
        self.action_requested.emit("update_record", payload)
        self.clear_edit_form()

    def request_load_records(self) -> None:
        self.action_requested.emit("load_records", self.view_options())

    def request_toggle_key1(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._rows):
            return
        self.action_requested.emit("toggle_key1", {"uid": self._rows[row]["uid"]})

    def form_payload(self) -> dict[str, Any]:
        return {
            "number": self.number_input.text(),
            "text": self.text_input.text(),
            "note": self.note_input.toPlainText(),
            "key1": self.key1_checkbox.isChecked(),
            "key2": self.key2_checkbox.isChecked(),
        }

    def view_options(self) -> dict[str, Any]:
        return {
            "decode": self.decode_checkbox.isChecked(),
            "key1": self.filter_key1_checkbox.isChecked(),
            "key2": self.filter_key2_checkbox.isChecked(),
        }

    def set_key(self, key: str) -> None:
        self.key_input.setText(key)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_records(self, rows: list) -> None:
        self._rows = [dict(row) for row in rows]
        self.records_table.setRowCount(0)
        true_bg = QColor("#173820")
        false_bg = QColor("#3a2428")
        for row_data in self._rows:
            row = self.records_table.rowCount()
            self.records_table.insertRow(row)
            values = [
                str(row_data.get("uid") or ""),
                str(row_data.get("number") or ""),
                str(row_data.get("display_text") or ""),
                str(row_data.get("note") or ""),
                "true" if row_data.get("key1") else "false",
                "true" if row_data.get("key2") else "false",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column in (4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setBackground(true_bg if value == "true" else false_bg)
                self.records_table.setItem(row, column, item)

    def show_records_menu(self, position) -> None:
        item = self.records_table.itemAt(position)
        if item is None:
            return
        row = item.row()
        if row < 0 or row >= len(self._rows):
            return
        uid = self._rows[row]["uid"]
        self.records_table.selectRow(row)
        menu = QMenu(self)
        info_action = menu.addAction("Info")
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        selected = menu.exec(self.records_table.viewport().mapToGlobal(position))
        if selected == info_action:
            self.action_requested.emit("get_record_info", {"uid": uid})
        elif selected == edit_action:
            self.action_requested.emit("get_record_for_edit", {"uid": uid})
        elif selected == delete_action:
            self.confirm_delete(uid)

    def confirm_delete(self, uid: int) -> None:
        answer = QMessageBox.question(
            self,
            "Delete record",
            f"Really delete record uid={uid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.action_requested.emit("delete_record", {"uid": uid})
            if self._editing_uid == uid:
                self.clear_edit_form()

    def show_record_info(self, row_data: dict) -> None:
        message = (
            f"uid: {row_data.get('uid')}\n"
            f"number: {row_data.get('number')}\n"
            f"text decoded:\n{row_data.get('decoded_text') or ''}\n\n"
            f"note:\n{row_data.get('note') or ''}\n\n"
            f"key1: {bool(row_data.get('key1'))}\n"
            f"key2: {bool(row_data.get('key2'))}"
        )
        QMessageBox.information(self, f"Record uid={row_data.get('uid')}", message)

    def load_record_for_edit(self, row_data: dict) -> None:
        self._editing_uid = int(row_data["uid"])
        self.edit_state_label.setText(f"Editing uid={self._editing_uid}")
        self.save_edit_button.setEnabled(True)
        self.number_input.setText(str(row_data.get("number") or ""))
        self.text_input.setText(str(row_data.get("decoded_text") or ""))
        self.note_input.setPlainText(str(row_data.get("note") or ""))
        self.key1_checkbox.setChecked(bool(row_data.get("key1")))
        self.key2_checkbox.setChecked(bool(row_data.get("key2")))

    def clear_edit_form(self) -> None:
        self._editing_uid = None
        self.edit_state_label.setText("New record")
        self.save_edit_button.setEnabled(False)
        self.number_input.clear()
        self.text_input.clear()
        self.note_input.clear()
        self.key1_checkbox.setChecked(False)
        self.key2_checkbox.setChecked(False)

    def clear_filters(self) -> None:
        self.filter_key1_checkbox.blockSignals(True)
        self.filter_key2_checkbox.blockSignals(True)
        self.filter_key1_checkbox.setChecked(False)
        self.filter_key2_checkbox.setChecked(False)
        self.filter_key1_checkbox.blockSignals(False)
        self.filter_key2_checkbox.blockSignals(False)
        self.request_load_records()

    def toggle_key_visibility(self, visible: bool) -> None:
        self.key_input.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.show_key_button.setText("Hide" if visible else "Show")

    def current_key(self) -> str:
        return self.key_input.text().strip().lower()

    def show_error(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def append_debug(self, text: str, level: str = "info") -> None:
        colors = {
            "info": "#39ff72",
            "debug": "#85c7ff",
            "muted": "#8b96a3",
            "warn": "#ffd166",
            "error": "#ff6b6b",
        }
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = colors.get(level, colors["info"])
        self.debug_box.append(f'<pre style="color: {color};">[{timestamp}] {html.escape(text)}</pre>')
        self.debug_box.verticalScrollBar().setValue(self.debug_box.verticalScrollBar().maximum())

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #121417;
                color: #e8e8e8;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 11pt;
            }
            QLabel#Title {
                font-size: 15pt;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#AppTitle {
                font-size: 15pt;
                font-weight: 700;
                color: #63d9ff;
            }
            QLabel#Version {
                color: #7a828c;
                font-size: 9pt;
                padding-top: 5px;
            }
            QLabel#Status {
                color: #9ad1ff;
                padding: 4px 0;
            }
            QLabel#Muted {
                color: #8b96a3;
            }
            QGroupBox {
                border: 1px solid #333941;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background: #26313d;
                border: 1px solid #3d4a57;
                border-radius: 5px;
                padding: 8px 10px;
            }
            QPushButton:hover {
                background: #314153;
            }
            QPushButton:pressed {
                background: #1d2732;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #58616b;
                background: #1b2026;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 3px solid #58616b;
                background: #39ff14;
            }
            QLineEdit, QTextBrowser, QTextEdit, QTableWidget {
                background: #0f1114;
                border: 1px solid #333941;
                border-radius: 5px;
                padding: 6px;
                color: #e8e8e8;
            }
            QTextBrowser#VerboseLog {
                background: #070b08;
                border-color: #2f5f3b;
                color: #39ff72;
                font-family: Consolas, Cascadia Mono, monospace;
                font-size: 9pt;
            }
            QTableWidget#RecordsTable {
                background: #0d1013;
                alternate-background-color: #121820;
                gridline-color: #2d343c;
                font-family: Consolas, Cascadia Mono, monospace;
                font-size: 9pt;
            }
            QHeaderView::section {
                background: #202833;
                color: #d7e0ea;
                border: 0;
                border-right: 1px solid #343d47;
                padding: 5px 6px;
                font-weight: 600;
            }
            QSplitter::handle {
                background: #262b31;
            }
            """
        )
