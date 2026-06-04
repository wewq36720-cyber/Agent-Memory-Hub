"""JSONL Writer — append-only source-of-truth log.

DIST-01 contract: every tool call first appends a JSONL line and fsyncs it,
returning the byte offset (used as memories.episode_id reference). Only after
JSONL durability succeeds may MySQL writes proceed; on MySQL failure the JSONL
is NOT rolled back — the truth log is the source of replay.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonlWriter:
    """Append-only writer for daily-rotated JSONL log files.

    Thread-safe via internal lock. Each call performs:
    1. JSON serialize the event
    2. Append line to today's file
    3. fsync to disk (durability)
    4. Return byte offset of the line (for memories.episode_id reference)
    """

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_date: str | None = None
        self._current_path: Path | None = None
        self._fh = None  # type: ignore[assignment]

    def _today_filename(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"

    def _rotate_if_needed(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._current_date:
            if self._fh is not None:
                try:
                    self._fh.flush()
                    os.fsync(self._fh.fileno())
                finally:
                    self._fh.close()
            self._current_date = today
            self._current_path = self.log_dir / f"{today}.jsonl"
            # Binary append, unbuffered — we fsync explicitly anyway.
            self._fh = open(self._current_path, "ab", buffering=0)

    def append(self, event: dict[str, Any]) -> int:
        """Append one JSONL line. Returns the byte offset where this line started.

        The offset is stable (within the day's file) and can be used as the
        memories.episode_id reference per DIST-01.
        """
        with self._lock:
            self._rotate_if_needed()
            assert self._fh is not None
            # Auto-stamp ts if caller didn't supply one.
            event.setdefault("ts", datetime.now(timezone.utc).isoformat())
            line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
            offset = self._fh.tell()
            self._fh.write(line.encode("utf-8"))
            self._fh.flush()
            os.fsync(self._fh.fileno())
            return offset

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.flush()
                    os.fsync(self._fh.fileno())
                finally:
                    self._fh.close()
                    self._fh = None

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_default_writer: JsonlWriter | None = None
_singleton_lock = threading.Lock()


def get_writer() -> JsonlWriter:
    """Get the process-wide default JsonlWriter (lazy init from settings)."""
    global _default_writer
    with _singleton_lock:
        if _default_writer is None:
            from ..config import settings

            _default_writer = JsonlWriter(settings.jsonl_log_dir)
        return _default_writer
