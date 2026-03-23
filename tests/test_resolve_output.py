"""Tests for _resolve_output automatic suffix selection."""

import argparse
from pathlib import Path

import pytest

from mkv2srt.cli import _resolve_output


def _make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "input": None,
        "output": None,
        "from_srt": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestResolveOutput:
    def test_explicit_output_always_wins(self, tmp_path):
        out = tmp_path / "custom.srt"
        args = _make_args(input=tmp_path / "movie.mkv", output=out)
        assert _resolve_output(args) == out

    def test_default_fr_srt(self, tmp_path):
        mkv = tmp_path / "movie.mkv"
        args = _make_args(input=mkv)
        assert _resolve_output(args) == tmp_path / "movie.fr.srt"

    def test_fallback_to_cc_when_fr_exists(self, tmp_path):
        mkv = tmp_path / "movie.mkv"
        (tmp_path / "movie.fr.srt").write_text("existing", encoding="utf-8")
        args = _make_args(input=mkv)
        assert _resolve_output(args) == tmp_path / "movie.fr.cc.srt"

    def test_fallback_to_sdh_when_fr_and_cc_exist(self, tmp_path):
        mkv = tmp_path / "movie.mkv"
        (tmp_path / "movie.fr.srt").write_text("existing", encoding="utf-8")
        (tmp_path / "movie.fr.cc.srt").write_text("existing", encoding="utf-8")
        args = _make_args(input=mkv)
        assert _resolve_output(args) == tmp_path / "movie.fr.sdh.srt"

    def test_fallback_to_numbered_when_all_standard_taken(self, tmp_path):
        mkv = tmp_path / "movie.mkv"
        (tmp_path / "movie.fr.srt").write_text("existing", encoding="utf-8")
        (tmp_path / "movie.fr.cc.srt").write_text("existing", encoding="utf-8")
        (tmp_path / "movie.fr.sdh.srt").write_text("existing", encoding="utf-8")
        args = _make_args(input=mkv)
        assert _resolve_output(args) == tmp_path / "movie.fr.2.srt"

    def test_numbered_skips_existing(self, tmp_path):
        mkv = tmp_path / "movie.mkv"
        for name in ["movie.fr.srt", "movie.fr.cc.srt", "movie.fr.sdh.srt",
                      "movie.fr.2.srt"]:
            (tmp_path / name).write_text("existing", encoding="utf-8")
        args = _make_args(input=mkv)
        assert _resolve_output(args) == tmp_path / "movie.fr.3.srt"

    def test_from_srt_mode_default(self, tmp_path):
        srt = tmp_path / "movie.en.srt"
        args = _make_args(from_srt=srt)
        # stem is "movie.en", so output is "movie.en.fr.srt"
        assert _resolve_output(args) == tmp_path / "movie.en.fr.srt"

    def test_from_srt_mode_with_existing(self, tmp_path):
        srt = tmp_path / "movie.en.srt"
        (tmp_path / "movie.en.fr.srt").write_text("existing", encoding="utf-8")
        args = _make_args(from_srt=srt)
        assert _resolve_output(args) == tmp_path / "movie.en.fr.cc.srt"
