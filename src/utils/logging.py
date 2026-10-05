"""Logging setup: console + one file per script run under logs/."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from src.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(run_name: str, level: int = logging.INFO, log_dir: Path = LOG_DIR) -> Path:
    """Configure the root logger; returns the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_name}_{datetime.now():%Y%m%d_%H%M%S}.log"
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    console = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    for handler in (console, file_handler):
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    return log_file
