"""Tests for --scan mode."""

import argparse
import threading
import time
from pathlib import Path
from unittest.mock import patch

from mkv2srt.cli import _run_scan
from mkv2srt.pipeline import whisper_lock as _whisper_lock


SRT_CONTENT = """\
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,500 --> 00:00:06,000
Goodbye world

"""


def _make_scan_args(scan_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        input=None,
        output=None,
        from_srt=None,
        model="medium",
        language=None,
        target="fr",
        sync_check=True,
        scan=scan_dir,
        workers=4,
    )


class TestRunScan:
    def test_finds_all_mkv_files(self, tmp_path):
        """--scan should discover all .mkv files recursively."""
        (tmp_path / "a.mkv").write_bytes(b"")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "b.mkv").write_bytes(b"")

        processed = []

        def fake_run(mkv_path, output_path, **kwargs):
            processed.append(mkv_path)
            return True

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        names = sorted(p.name for p in processed)
        assert names == ["a.mkv", "b.mkv"]

    def test_no_mkv_files(self, tmp_path):
        """--scan on an empty dir should not call run_from_mkv."""
        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli.run_from_mkv") as mock:
            _run_scan(args)
        mock.assert_not_called()

    def test_ignores_non_mkv_files(self, tmp_path):
        """--scan should skip .mp4, .avi, etc."""
        (tmp_path / "video.mp4").write_bytes(b"")
        (tmp_path / "video.avi").write_bytes(b"")
        (tmp_path / "movie.mkv").write_bytes(b"")

        processed = []

        def fake_run(mkv_path, output_path, **kwargs):
            processed.append(mkv_path)
            return True

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert len(processed) == 1
        assert processed[0].name == "movie.mkv"

    def test_continues_on_failure(self, tmp_path):
        """--scan should continue processing after a file fails."""
        (tmp_path / "a.mkv").write_bytes(b"")
        (tmp_path / "b.mkv").write_bytes(b"")
        (tmp_path / "c.mkv").write_bytes(b"")

        call_count = 0

        def fail_on_second(mkv_path, output_path, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("simulated failure")
            return True

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fail_on_second):
            _run_scan(args)

        assert call_count == 3

    def test_scan_with_existing_srt(self, tmp_path):
        """--scan should process MKV that has an existing .en.srt next to it."""
        mkv = tmp_path / "movie.mkv"
        mkv.write_bytes(b"")
        (tmp_path / "movie.en.srt").write_text(SRT_CONTENT, encoding="utf-8")

        processed = []

        def fake_run(mkv_path, output_path, **kwargs):
            processed.append(mkv_path)
            return True

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert len(processed) == 1
        assert processed[0] == mkv


# ─────────────────────────────────────────────────────────────────────────────
# Concurrent workers
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkers:
    def test_files_processed_concurrently(self, tmp_path):
        """Multiple files should run in parallel, not sequentially."""
        for i in range(4):
            (tmp_path / f"{i}.mkv").write_bytes(b"")

        max_concurrent = 0
        lock = threading.Lock()
        active = 0

        def fake_run(mkv_path, output_path, **kwargs):
            nonlocal active, max_concurrent
            with lock:
                active += 1
                max_concurrent = max(max_concurrent, active)
            time.sleep(0.1)
            with lock:
                active -= 1
            return True

        args = _make_scan_args(tmp_path)
        args.workers = 4
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert max_concurrent > 1

    def test_workers_get_independent_args(self, tmp_path):
        """Each worker should get its own copy of args (no shared mutation)."""
        for i in range(3):
            (tmp_path / f"{i}.mkv").write_bytes(b"")

        seen_inputs = []
        lock = threading.Lock()

        def fake_run(mkv_path, output_path, **kwargs):
            time.sleep(0.05)
            with lock:
                seen_inputs.append(mkv_path.name)
            return True

        args = _make_scan_args(tmp_path)
        args.workers = 3
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert sorted(seen_inputs) == ["0.mkv", "1.mkv", "2.mkv"]

    def test_whisper_lock_serializes(self, tmp_path):
        """_whisper_lock should prevent concurrent access to the guarded section."""
        for i in range(4):
            (tmp_path / f"{i}.mkv").write_bytes(b"")

        max_inside_lock = 0
        lock_active = 0
        check_lock = threading.Lock()
        violation = False

        def fake_run(mkv_path, output_path, **kwargs):
            nonlocal lock_active, max_inside_lock, violation
            with _whisper_lock:
                with check_lock:
                    lock_active += 1
                    if lock_active > 1:
                        violation = True
                    max_inside_lock = max(max_inside_lock, lock_active)
                time.sleep(0.05)
                with check_lock:
                    lock_active -= 1
            return True

        args = _make_scan_args(tmp_path)
        args.workers = 4
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert not violation, "Multiple threads entered _whisper_lock simultaneously"
        assert max_inside_lock == 1

    def test_workers_capped_to_file_count(self, tmp_path):
        """workers should not exceed the number of files."""
        (tmp_path / "only.mkv").write_bytes(b"")

        processed = []

        def fake_run(mkv_path, output_path, **kwargs):
            processed.append(mkv_path.name)
            return True

        args = _make_scan_args(tmp_path)
        args.workers = 8
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert processed == ["only.mkv"]

    def test_failure_does_not_block_other_workers(self, tmp_path):
        """A failing file should not prevent other workers from completing."""
        for i in range(4):
            (tmp_path / f"{i}.mkv").write_bytes(b"")

        results = []
        lock = threading.Lock()

        def fake_run(mkv_path, output_path, **kwargs):
            if mkv_path.name == "1.mkv":
                raise RuntimeError("boom")
            time.sleep(0.05)
            with lock:
                results.append(mkv_path.name)
            return True

        args = _make_scan_args(tmp_path)
        args.workers = 4
        with patch("mkv2srt.cli.run_from_mkv", side_effect=fake_run):
            _run_scan(args)

        assert sorted(results) == ["0.mkv", "2.mkv", "3.mkv"]
