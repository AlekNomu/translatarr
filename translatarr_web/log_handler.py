"""
translatarr_web.log_handler
~~~~~~~~~~~~~~~~~~~~~~~
Custom logging handler that captures log records for SSE streaming
to the web UI and provides a circular buffer of recent entries.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections import deque


class WebLogHandler(logging.Handler):
    """Thread-safe handler that buffers log records for SSE subscribers."""

    def __init__(self, max_buffer: int = 1000) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=max_buffer)
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": self.format(record),
        }
        with self._lock:
            self._buffer.append(entry)
            dead: list[queue.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self) -> queue.Queue:
        """Create a new subscriber queue for SSE streaming."""
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def get_recent(self, n: int = 200) -> list[dict]:
        """Return the last *n* log entries."""
        with self._lock:
            items = list(self._buffer)
        return items[-n:]

    def sse_generate(self, q: queue.Queue):
        """Generator that yields SSE-formatted log entries."""
        try:
            while True:
                try:
                    entry = q.get(timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            self.unsubscribe(q)
