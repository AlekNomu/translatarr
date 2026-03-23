"""Tests for --scan mode."""

import argparse
from pathlib import Path
from unittest.mock import patch

from mkv2srt.cli import _run_scan


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
        sync_check=True,
        scan=scan_dir,
    )


class TestRunScan:
    def test_finds_all_mkv_files(self, tmp_path):
        """--scan should discover all .mkv files recursively."""
        (tmp_path / "a.mkv").write_bytes(b"")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "b.mkv").write_bytes(b"")

        processed = []

        def fake_run_single(args):
            processed.append(args.input)

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli._run_single", side_effect=fake_run_single):
            _run_scan(args)

        names = sorted(p.name for p in processed)
        assert names == ["a.mkv", "b.mkv"]

    def test_no_mkv_files(self, tmp_path):
        """--scan on an empty dir should not call _run_single."""
        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli._run_single") as mock:
            _run_scan(args)
        mock.assert_not_called()

    def test_ignores_non_mkv_files(self, tmp_path):
        """--scan should skip .mp4, .avi, etc."""
        (tmp_path / "video.mp4").write_bytes(b"")
        (tmp_path / "video.avi").write_bytes(b"")
        (tmp_path / "movie.mkv").write_bytes(b"")

        processed = []

        def fake_run_single(args):
            processed.append(args.input)

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli._run_single", side_effect=fake_run_single):
            _run_scan(args)

        assert len(processed) == 1
        assert processed[0].name == "movie.mkv"

    def test_continues_on_failure(self, tmp_path):
        """--scan should continue processing after a file fails."""
        (tmp_path / "a.mkv").write_bytes(b"")
        (tmp_path / "b.mkv").write_bytes(b"")
        (tmp_path / "c.mkv").write_bytes(b"")

        call_count = 0

        def fail_on_second(args):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("simulated failure")

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli._run_single", side_effect=fail_on_second):
            _run_scan(args)

        assert call_count == 3

    def test_scan_with_existing_srt(self, tmp_path):
        """--scan should process MKV that has an existing .en.srt next to it."""
        mkv = tmp_path / "movie.mkv"
        mkv.write_bytes(b"")
        (tmp_path / "movie.en.srt").write_text(SRT_CONTENT, encoding="utf-8")

        processed = []

        def fake_run_single(args):
            processed.append(args.input)

        args = _make_scan_args(tmp_path)
        with patch("mkv2srt.cli._run_single", side_effect=fake_run_single):
            _run_scan(args)

        assert len(processed) == 1
        assert processed[0] == mkv
