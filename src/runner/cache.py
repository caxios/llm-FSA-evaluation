"""Call cache (SQLite, WAL mode; P5 §5.6). One row per cache key; writes are
transactional, so an interrupted run never leaves a half-written row."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from src.agents.base import RunRecord
from src.config import PROJECT_ROOT

DEFAULT_PATH = PROJECT_ROOT / "results" / "cache" / "calls.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  cache_key TEXT PRIMARY KEY,
  experiment TEXT, firm_id TEXT, model_key TEXT, prompt_version TEXT,
  record_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class CallCache:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)

    def get(self, key: str) -> RunRecord | None:
        with self.lock:
            row = self.conn.execute("SELECT record_json FROM calls WHERE cache_key = ?",
                                    (key,)).fetchone()
        return RunRecord.model_validate_json(row[0]) if row else None

    def has(self, key: str) -> bool:
        with self.lock:
            return self.conn.execute("SELECT 1 FROM calls WHERE cache_key = ?",
                                     (key,)).fetchone() is not None

    def put(self, record: RunRecord) -> None:
        r = record.request
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO calls VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (record.cache_key, r.experiment, r.firm_id, r.model_key, r.prompt_version,
                     record.model_dump_json(), datetime.now().isoformat(timespec="seconds")))
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def records(self, model_key: str | None = None) -> list[RunRecord]:
        sql, args = "SELECT record_json FROM calls", ()
        if model_key:
            sql, args = sql + " WHERE model_key = ?", (model_key,)
        with self.lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [RunRecord.model_validate_json(r[0]) for r in rows]

    def __len__(self) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
