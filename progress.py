import sqlite3
import threading
from pathlib import Path

_CONFIG_DIR = Path.home() / ".audiobook_player"
_DB_FILE = _CONFIG_DIR / "progress.db"


class ProgressStore:
    def __init__(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(_DB_FILE), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                book_id  TEXT PRIMARY KEY,
                file_idx INTEGER DEFAULT 0,
                position REAL    DEFAULT 0.0
            )
        """)
        self._conn.commit()

    def get(self, book_id: str) -> dict:
        row = self._conn.execute(
            "SELECT file_idx, position FROM progress WHERE book_id=?", (book_id,)
        ).fetchone()
        if row:
            return {"file_idx": row[0], "position": row[1]}
        return {"file_idx": 0, "position": 0.0}

    def save(self, book_id: str, file_idx: int, position: float):
        with self._lock:
            self._conn.execute("""
                INSERT INTO progress (book_id, file_idx, position) VALUES (?,?,?)
                ON CONFLICT(book_id) DO UPDATE SET
                    file_idx=excluded.file_idx,
                    position=excluded.position
            """, (book_id, file_idx, position))
            self._conn.commit()

    def get_all(self) -> dict:
        rows = self._conn.execute(
            "SELECT book_id, file_idx, position FROM progress"
        ).fetchall()
        return {r[0]: {"file_idx": r[1], "position": r[2]} for r in rows}
