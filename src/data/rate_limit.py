"""Request pacing with an optional daily quota persisted across processes."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from src.utils.io import atomic_write


class QuotaExhausted(RuntimeError):
    """The daily call quota for an API key has been used up."""


class RateLimiter:
    """Allow at most `per_second` calls per second and `daily_quota` calls per local day.

    The daily count is stored in `state_path`, so restarting a script does not reset it.
    """

    def __init__(
        self,
        per_second: float,
        daily_quota: int | None = None,
        state_path: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        if per_second <= 0:
            raise ValueError("per_second must be positive")
        if daily_quota is not None and state_path is None:
            raise ValueError("state_path is required when daily_quota is set")
        self.min_interval = 1.0 / per_second
        self.daily_quota = daily_quota
        self.state_path = state_path
        self._clock, self._sleep, self._today = clock, sleep, today
        self._last: float | None = None
        self._lock = threading.Lock()

    def _load_count(self) -> int:
        if self.state_path is None or not self.state_path.exists():
            return 0
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        return int(state.get(self._today().isoformat(), 0))

    def _save_count(self, count: int) -> None:
        assert self.state_path is not None
        atomic_write(self.state_path, json.dumps({self._today().isoformat(): count}).encode())

    def used_today(self) -> int:
        return self._load_count()

    def acquire(self) -> None:
        """Block until a call is allowed; raise QuotaExhausted if the daily quota is used up."""
        with self._lock:
            if self.daily_quota is not None:
                count = self._load_count()
                if count >= self.daily_quota:
                    raise QuotaExhausted(f"daily quota of {self.daily_quota} calls reached")
            now = self._clock()
            if self._last is not None:
                wait = self.min_interval - (now - self._last)
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            self._last = now
            if self.daily_quota is not None:
                self._save_count(count + 1)
