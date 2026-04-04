"""Tests for translatarr.pipeline — SRT lookup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from translatarr.pipeline import find_srt_by_lang, find_source_srt_with_label, target_srt_tags


# ─────────────────────────────────────────────────────────────────────────────
# find_srt_by_lang
# ─────────────────────────────────────────────────────────────────────────────

class TestFindSrtByLang:
    def test_finds_plain_lang_tag(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fr.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == tmp_path / "Movie.2016.fr.srt"

    def test_finds_iso3_alias(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fre.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == tmp_path / "Movie.2016.fre.srt"

    def test_finds_hi_variant(self, tmp_path):
        # Reproduces bug: .fr.hi.srt was not detected as a French subtitle
        mkv = tmp_path / "A.Silent.Voice.2016.1080p.BluRay.x264-HAiKU.mkv"
        mkv.touch()
        (tmp_path / "A.Silent.Voice.2016.1080p.BluRay.x264-HAiKU.fr.hi.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is not None

    def test_finds_sdh_variant(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fr.sdh.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is not None

    def test_plain_takes_priority_over_hi(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        plain = tmp_path / "Movie.2016.fr.srt"
        plain.touch()
        (tmp_path / "Movie.2016.fr.hi.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == plain

    def test_returns_none_when_absent(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is None
