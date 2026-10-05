"""JSONL run log (P5 §5.6): every newly executed record (cache misses only) is appended
to results/runs/{experiment}/{YYYYMMDD}.jsonl."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from src.agents.base import RunRecord
from src.config import PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / "results" / "runs"
_lock = threading.Lock()


def log_record(record: RunRecord, root: Path = RUNS_DIR) -> Path:
    path = root / record.request.experiment / f"{datetime.now():%Y%m%d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = record.model_dump_json() + "\n"
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(line)
    return path
