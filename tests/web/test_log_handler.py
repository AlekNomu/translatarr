"""Unit tests for translatarr_web.log_handler — WebLogHandler."""

from __future__ import annotations

import logging
import threading
import time
import pytest

from translatarr_web.log_handler import WebLogHandler


def _emit(handler: WebLogHandler, message: str, level: int = logging.INFO) -> None:
    record = logging.LogRecord(
        name="translatarr", level=level,
        pathname="", lineno=0,
        msg=message, args=(), exc_info=None,
    )
    handler.emit(record)


class TestWebLogHandler:
    def test_buffer_stores_entries(self):
        h = WebLogHandler(max_buffer=100)
        _emit(h, "hello")
        assert len(h.get_recent(10)) == 1
        assert h.get_recent(10)[0]["message"] == "hello"

    def test_buffer_respects_max_size(self):
        h = WebLogHandler(max_buffer=3)
        for i in range(5):
            _emit(h, f"msg {i}")
        recent = h.get_recent(10)
        assert len(recent) == 3
        # Oldest entries evicted; last 3 remain
        assert recent[-1]["message"] == "msg 4"

    def test_subscribe_receives_entries(self):
        h = WebLogHandler()
        q = h.subscribe()
        _emit(h, "live message")
        entry = q.get_nowait()
        assert entry["message"] == "live message"

    def test_unsubscribe_stops_delivery(self):
        h = WebLogHandler()
        q = h.subscribe()
        h.unsubscribe(q)
        _emit(h, "should not arrive")
        with pytest.raises(Exception):
            q.get_nowait()

    def test_get_recent_respects_n(self):
        h = WebLogHandler()
        for i in range(10):
            _emit(h, f"msg {i}")
        assert len(h.get_recent(3)) == 3

    def test_level_is_recorded(self):
        h = WebLogHandler()
        _emit(h, "error!", logging.ERROR)
        assert h.get_recent(1)[0]["level"] == "ERROR"

    def test_concurrent_subscribe(self):
        h = WebLogHandler()
        results: list[str] = []
        lock = threading.Lock()

        def worker():
            q = h.subscribe()
            try:
                entry = q.get(timeout=1)
                with lock:
                    results.append(entry["message"])
            except Exception:
                pass

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        time.sleep(0.05)
        _emit(h, "broadcast")
        for t in threads:
            t.join(timeout=2)

        assert len(results) == 5
        assert all(r == "broadcast" for r in results)
