from __future__ import annotations

import html
import secrets
import sqlite3
import string
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QRegularExpression, Qt
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


VER = "0.1 | 2026-06"
DB_PATH = Path("data/main_data.db")
ENV_PATH = Path(".env")
KEY_NAME = "XEY_HEX"
DEFAULT_KEY = "123abc"
BASE64_ASCII = string.ascii_letters + string.digits + "+/"


def key_bytes_from_hex(hex_key: str) -> bytes:
    return bytes.fromhex(hex_key)


def _xor_bytes(source: bytes, key_bytes: bytes) -> bytes:
    return bytes(byte ^ key_bytes[index % len(key_bytes)] for index, byte in enumerate(source))


def _pad_short_text(text_bytes: bytes, key_len: int) -> bytes:
    if len(text_bytes) >= key_len:
        return text_bytes
    target_len = key_len
    while len(text_bytes) + 2 > target_len:
        target_len += key_len
    random_len = target_len - len(text_bytes) - 2
    random_tail = "".join(secrets.choice(BASE64_ASCII) for _ in range(random_len)).encode("ascii")
    return text_bytes + b"/*" + random_tail


def text_to_xor_hex(text: str, hex_key: str) -> str:
    text_bytes = text.encode("utf-8")
    if not hex_key:
        return text_bytes.hex()
    if not is_valid_hex_key(hex_key):
        raise ValueError("Invalid hex key")
    key_bytes = key_bytes_from_hex(hex_key)
    return _xor_bytes(_pad_short_text(text_bytes, len(key_bytes)), key_bytes).hex()


def text_from_xor_hex(value: str, hex_key: str) -> str:
    if not value:
        return ""
    try:
        xor_bytes = bytes.fromhex(value)
    except ValueError:
        return value
    if not hex_key:
        return xor_bytes.decode("utf-8", errors="replace")
    if not is_valid_hex_key(hex_key):
        return value
    key_bytes = key_bytes_from_hex(hex_key)
    decoded = _xor_bytes(xor_bytes, key_bytes)
    decoded = decoded.split(b"/*", 1)[0]
    return decoded.decode("utf-8", errors="replace")


def _read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def read_key_hex() -> str:
    for line in _read_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != KEY_NAME:
            continue
        return value.strip().strip("\"'")
    return ""


def save_key_hex(hex_value: str) -> None:
    lines = _read_env_lines()
    replacement = f"{KEY_NAME}={hex_value}"
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{KEY_NAME}="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def is_valid_hex_key(hex_value: str) -> bool:
    if not hex_value or len(hex_value) % 2:
        return False
    try:
        bytes.fromhex(hex_value)
    except ValueError:
        return False
    return True


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("py_qtsql | SQLite XOR Demo")
        self.resize(1260, 780)
        self.setMinimumSize(980, 620)
        self._rows: list[dict[str, Any]] = []
        self._editing_uid: int | None = None
        self._ensure_key()
        self._ensure_database()
        self._build_ui()
        self._apply_theme()
        self.load_key()
        self.load_records()

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
        save_btn.clicked.connect(self.save_key)
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
        new_btn.clicked.connect(self.add_record)
        row.addWidget(new_btn)
        self.save_edit_button = QPushButton("Save edit")
        self.save_edit_button.clicked.connect(self.save_edit)
        self.save_edit_button.setEnabled(False)
        row.addWidget(self.save_edit_button)
        cancel_edit_btn = QPushButton("Cancel edit")
        cancel_edit_btn.clicked.connect(self.clear_edit_form)
        row.addWidget(cancel_edit_btn)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.load_records)
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
        self.filter_key1_checkbox.toggled.connect(self.load_records)
        row.addWidget(self.filter_key1_checkbox)
        self.filter_key2_checkbox = QCheckBox("k2")
        self.filter_key2_checkbox.toggled.connect(self.load_records)
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
        self.decode_checkbox.toggled.connect(lambda: self.render_table())
        table_header.addWidget(self.decode_checkbox)
        table_layout.addLayout(table_header)
        self.records_table = QTableWidget(0, 6)
        self.records_table.setObjectName("RecordsTable")
        self.records_table.setHorizontalHeaderLabels(["uid", "number", "text", "note", "key1", "key2"])
        self.records_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.cellClicked.connect(self.toggle_key1_from_row)
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

    def _ensure_key(self) -> None:
        if is_valid_hex_key(read_key_hex()):
            return
        save_key_hex(DEFAULT_KEY)

    def _ensure_database(self) -> None:
        DB_PATH.parent.mkdir(exist_ok=True)
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    uid INTEGER PRIMARY KEY AUTOINCREMENT,
                    number INTEGER,
                    text TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    key1 INTEGER NOT NULL DEFAULT 0,
                    key2 INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def load_key(self) -> None:
        key = read_key_hex()
        self.key_input.setText(key)
        self.append_debug(f"key loaded from {ENV_PATH} ({len(key) // 2} bytes)", "muted")

    def save_key(self) -> None:
        key = self.current_key()
        if not is_valid_hex_key(key):
            QMessageBox.warning(self, "Invalid key", "XOR key must be non-empty base16 with an even length.")
            return
        save_key_hex(key)
        self.append_debug(f"key saved as {KEY_NAME} hex", "info")
        self.load_records()

    def toggle_key_visibility(self, visible: bool) -> None:
        self.key_input.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.show_key_button.setText("Hide" if visible else "Show")

    def add_record(self) -> None:
        number_text = self.number_input.text().strip()
        try:
            number = int(number_text) if number_text else 0
        except ValueError:
            QMessageBox.warning(self, "Invalid number", "number must be an integer.")
            return
        if not is_valid_hex_key(self.current_key()):
            QMessageBox.warning(self, "Invalid key", "XOR key must be non-empty base16 with an even length.")
            return
        text_hex = text_to_xor_hex(self.text_input.text().strip(), self.current_key())
        note = self.note_input.toPlainText()
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute(
                "INSERT INTO records (number, text, note, key1, key2) VALUES (?, ?, ?, ?, ?)",
                (
                    number,
                    text_hex,
                    note,
                    int(self.key1_checkbox.isChecked()),
                    int(self.key2_checkbox.isChecked()),
                ),
            )
        self.append_debug(f"record inserted uid={cursor.lastrowid}", "info")
        self.clear_edit_form()
        self.load_records()

    def save_edit(self) -> None:
        if self._editing_uid is None:
            return
        number_text = self.number_input.text().strip()
        try:
            number = int(number_text) if number_text else 0
        except ValueError:
            QMessageBox.warning(self, "Invalid number", "number must be an integer.")
            return
        if not is_valid_hex_key(self.current_key()):
            QMessageBox.warning(self, "Invalid key", "XOR key must be non-empty base16 with an even length.")
            return
        text_hex = text_to_xor_hex(self.text_input.text().strip(), self.current_key())
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                """
                UPDATE records
                SET number = ?, text = ?, note = ?, key1 = ?, key2 = ?
                WHERE uid = ?
                """,
                (
                    number,
                    text_hex,
                    self.note_input.toPlainText(),
                    int(self.key1_checkbox.isChecked()),
                    int(self.key2_checkbox.isChecked()),
                    self._editing_uid,
                ),
            )
        self.append_debug(f"record updated uid={self._editing_uid}", "info")
        self.clear_edit_form()
        self.load_records()

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
        self.load_records()

    def load_records(self) -> None:
        query = "SELECT uid, number, text, note, key1, key2 FROM records"
        filters = []
        params: list[Any] = []
        if self.filter_key1_checkbox.isChecked():
            filters.append("key1 = ?")
            params.append(1)
        if self.filter_key2_checkbox.isChecked():
            filters.append("key2 = ?")
            params.append(1)
        if filters:
            query = f"{query} WHERE {' AND '.join(filters)}"
        query = f"{query} ORDER BY uid DESC"

        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        self._rows = [dict(row) for row in rows]
        self.render_table()
        self.status_label.setText(f"{len(self._rows)} rows")
        active_filters = []
        if self.filter_key1_checkbox.isChecked():
            active_filters.append("k1")
        if self.filter_key2_checkbox.isChecked():
            active_filters.append("k2")
        self.append_debug(f"loaded {len(self._rows)} records ({', '.join(active_filters) or 'all'})", "debug")

    def render_table(self) -> None:
        self.records_table.setRowCount(0)
        true_bg = QColor("#173820")
        false_bg = QColor("#3a2428")
        key = self.current_key()
        decode_text = self.decode_checkbox.isChecked()
        for row_data in self._rows:
            row = self.records_table.rowCount()
            self.records_table.insertRow(row)
            raw_text = str(row_data["text"])
            values = [
                str(row_data["uid"]),
                str(row_data["number"]),
                text_from_xor_hex(raw_text, key) if decode_text else raw_text,
                str(row_data["note"]),
                "true" if row_data["key1"] else "false",
                "true" if row_data["key2"] else "false",
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
        self.records_table.selectRow(row)
        menu = QMenu(self)
        info_action = menu.addAction("Info")
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        selected = menu.exec(self.records_table.viewport().mapToGlobal(position))
        if selected == info_action:
            self.show_record_info(row)
            return
        if selected == edit_action:
            self.edit_record(row)
            return
        if selected == delete_action:
            self.delete_record(row)

    def decoded_row(self, row: int) -> dict[str, Any]:
        row_data = dict(self._rows[row])
        row_data["decoded_text"] = text_from_xor_hex(str(row_data["text"]), self.current_key())
        return row_data

    def show_record_info(self, row: int) -> None:
        row_data = self.decoded_row(row)
        message = (
            f"uid: {row_data['uid']}\n"
            f"number: {row_data['number']}\n"
            f"text decoded:\n{row_data['decoded_text']}\n\n"
            f"note:\n{row_data['note']}\n\n"
            f"key1: {bool(row_data['key1'])}\n"
            f"key2: {bool(row_data['key2'])}"
        )
        QMessageBox.information(self, f"Record uid={row_data['uid']}", message)

    def edit_record(self, row: int) -> None:
        row_data = self.decoded_row(row)
        self._editing_uid = int(row_data["uid"])
        self.edit_state_label.setText(f"Editing uid={self._editing_uid}")
        self.save_edit_button.setEnabled(True)
        self.number_input.setText(str(row_data["number"]))
        self.text_input.setText(str(row_data["decoded_text"]))
        self.note_input.setPlainText(str(row_data["note"]))
        self.key1_checkbox.setChecked(bool(row_data["key1"]))
        self.key2_checkbox.setChecked(bool(row_data["key2"]))
        self.append_debug(f"record loaded for edit uid={self._editing_uid}", "muted")

    def delete_record(self, row: int) -> None:
        row_data = self._rows[row]
        uid = int(row_data["uid"])
        answer = QMessageBox.question(
            self,
            "Delete record",
            f"Really delete record uid={uid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("DELETE FROM records WHERE uid = ?", (uid,))
        if self._editing_uid == uid:
            self.clear_edit_form()
        self.append_debug(f"record deleted uid={uid}", "warn")
        self.load_records()

    def toggle_key1_from_row(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._rows):
            return
        uid = int(self._rows[row]["uid"])
        new_value = 0 if int(self._rows[row]["key1"]) else 1
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("UPDATE records SET key1 = ? WHERE uid = ?", (new_value, uid))
        self.append_debug(f"uid={uid} key1 -> {bool(new_value)}", "info")
        self.load_records()

    def current_key(self) -> str:
        return self.key_input.text().strip().lower()

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
