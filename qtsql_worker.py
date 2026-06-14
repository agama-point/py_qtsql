from __future__ import annotations

import secrets
import sqlite3
import string
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


DB_PATH = Path("data/main_data.db")
ENV_PATH = Path(".env")
KEY_NAME = "XEY_HEX"
DEFAULT_KEY = "123abc"
BASE64_ASCII = string.ascii_letters + string.digits + "+/"


def is_valid_hex_key(hex_value: str) -> bool:
    if not hex_value or len(hex_value) % 2:
        return False
    try:
        bytes.fromhex(hex_value)
    except ValueError:
        return False
    return True


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
        if name.strip() == KEY_NAME:
            return value.strip().strip("\"'")
    return ""


def save_key_hex(hex_value: str) -> None:
    lines = _read_env_lines()
    replacement = f"{KEY_NAME}={hex_value}"
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{KEY_NAME}="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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
    if not is_valid_hex_key(hex_key):
        raise ValueError("XOR key must be non-empty base16 with an even length.")
    key_bytes = bytes.fromhex(hex_key)
    return _xor_bytes(_pad_short_text(text_bytes, len(key_bytes)), key_bytes).hex()


def text_from_xor_hex(value: str, hex_key: str) -> str:
    if not value:
        return ""
    try:
        xor_bytes = bytes.fromhex(value)
    except ValueError:
        return value
    if not is_valid_hex_key(hex_key):
        return value
    decoded = _xor_bytes(xor_bytes, bytes.fromhex(hex_key)).split(b"/*", 1)[0]
    return decoded.decode("utf-8", errors="replace")


class QtSqlWorker(QObject):
    log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(str)
    key_signal = pyqtSignal(str)
    rows_signal = pyqtSignal(list)
    edit_record_signal = pyqtSignal(dict)
    info_record_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._key = ""
        self._decode = False
        self._filters = {"key1": False, "key2": False}

    @pyqtSlot()
    def initialize(self) -> None:
        self._ensure_key()
        self._ensure_database()
        self._key = read_key_hex()
        self.key_signal.emit(self._key)
        self.log_signal.emit(f"key loaded from {ENV_PATH} ({len(self._key) // 2} bytes)", "muted")
        self.load_records()

    @pyqtSlot(str, object)
    def run_action(self, action: str, payload: object = None) -> None:
        data = dict(payload or {})
        try:
            if action == "save_key":
                self.save_key(str(data.get("key") or ""))
            elif action == "load_records":
                self._decode = bool(data.get("decode", self._decode))
                self._filters = {
                    "key1": bool(data.get("key1", self._filters["key1"])),
                    "key2": bool(data.get("key2", self._filters["key2"])),
                }
                self.load_records()
            elif action == "add_record":
                self.add_record(data)
            elif action == "update_record":
                self.update_record(data)
            elif action == "toggle_key1":
                self.toggle_key1(int(data.get("uid")))
            elif action == "delete_record":
                self.delete_record(int(data.get("uid")))
            elif action == "get_record_for_edit":
                self.emit_record(int(data.get("uid")), for_edit=True)
            elif action == "get_record_info":
                self.emit_record(int(data.get("uid")), for_edit=False)
            else:
                self.log_signal.emit(f"unknown action: {action}", "warn")
        except (ValueError, sqlite3.Error) as exc:
            self.error_signal.emit("QtSQL action failed", str(exc))
            self.log_signal.emit(f"{action} failed: {exc}", "error")

    def _ensure_key(self) -> None:
        if not is_valid_hex_key(read_key_hex()):
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

    def save_key(self, key: str) -> None:
        key = key.strip().lower()
        if not is_valid_hex_key(key):
            raise ValueError("XOR key must be non-empty base16 with an even length.")
        save_key_hex(key)
        self._key = key
        self.key_signal.emit(key)
        self.log_signal.emit(f"key saved as {KEY_NAME} hex", "info")
        self.load_records()

    def add_record(self, data: dict[str, Any]) -> None:
        number = self._parse_number(data.get("number"))
        text_hex = text_to_xor_hex(str(data.get("text") or ""), self._key)
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute(
                "INSERT INTO records (number, text, note, key1, key2) VALUES (?, ?, ?, ?, ?)",
                (
                    number,
                    text_hex,
                    str(data.get("note") or ""),
                    int(bool(data.get("key1"))),
                    int(bool(data.get("key2"))),
                ),
            )
        self.log_signal.emit(f"record inserted uid={cursor.lastrowid}", "info")
        self.load_records()

    def update_record(self, data: dict[str, Any]) -> None:
        uid = int(data.get("uid"))
        number = self._parse_number(data.get("number"))
        text_hex = text_to_xor_hex(str(data.get("text") or ""), self._key)
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
                    str(data.get("note") or ""),
                    int(bool(data.get("key1"))),
                    int(bool(data.get("key2"))),
                    uid,
                ),
            )
        self.log_signal.emit(f"record updated uid={uid}", "info")
        self.load_records()

    def toggle_key1(self, uid: int) -> None:
        row = self._get_record(uid)
        new_value = 0 if int(row["key1"]) else 1
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("UPDATE records SET key1 = ? WHERE uid = ?", (new_value, uid))
        self.log_signal.emit(f"uid={uid} key1 -> {bool(new_value)}", "info")
        self.load_records()

    def delete_record(self, uid: int) -> None:
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("DELETE FROM records WHERE uid = ?", (uid,))
        self.log_signal.emit(f"record deleted uid={uid}", "warn")
        self.load_records()

    def emit_record(self, uid: int, for_edit: bool) -> None:
        row = self._decorate_row(self._get_record(uid))
        if for_edit:
            self.edit_record_signal.emit(row)
            self.log_signal.emit(f"record loaded for edit uid={uid}", "muted")
        else:
            self.info_record_signal.emit(row)

    def load_records(self) -> None:
        query = "SELECT uid, number, text, note, key1, key2 FROM records"
        filters = []
        params: list[Any] = []
        if self._filters["key1"]:
            filters.append("key1 = ?")
            params.append(1)
        if self._filters["key2"]:
            filters.append("key2 = ?")
            params.append(1)
        if filters:
            query = f"{query} WHERE {' AND '.join(filters)}"
        query = f"{query} ORDER BY uid DESC"
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        decorated = [self._decorate_row(dict(row)) for row in rows]
        self.rows_signal.emit(decorated)
        self.status_signal.emit(f"{len(decorated)} rows")
        active_filters = [name for name, enabled in self._filters.items() if enabled]
        self.log_signal.emit(f"loaded {len(decorated)} records ({', '.join(active_filters) or 'all'})", "debug")

    def _get_record(self, uid: int) -> dict[str, Any]:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT uid, number, text, note, key1, key2 FROM records WHERE uid = ?",
                (uid,),
            ).fetchone()
        if row is None:
            raise ValueError(f"record uid={uid} not found")
        return dict(row)

    def _decorate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        raw_text = str(row.get("text") or "")
        decoded_text = text_from_xor_hex(raw_text, self._key)
        row["raw_text"] = raw_text
        row["decoded_text"] = decoded_text
        row["display_text"] = decoded_text if self._decode else raw_text
        return row

    def _parse_number(self, value: object) -> int:
        text = str(value or "").strip()
        return int(text) if text else 0
