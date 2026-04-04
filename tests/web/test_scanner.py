"""Unit tests for translatarr_web.scanner — file discovery and DB sync."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
from translatarr_web.database import init_db
from translatarr_web.scanner import _parse_episode, _parse_movie_title, scan_library


@pytest.fixture()
def scan_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── Filename parsers ──────────────────────────────────────────────────────────

class TestParseEpisode:
    def test_sonarr_style(self, tmp_path):
        p = tmp_path / "From (2022) - S01E03 - Choosing Day (1080p).mkv"
        result = _parse_episode(p)
        assert result is not None
        assert result["series_name"] == "From"
        assert result["season"] == 1
        assert result["episode"] == 3
        assert result["title"] == "Choosing Day"

    def test_plain_sXXeXX(self, tmp_path):
        p = tmp_path / "show.S02E07.mkv"
        result = _parse_episode(p)
        assert result is not None
        assert result["season"] == 2
        assert result["episode"] == 7

    def test_no_episode_returns_none(self, tmp_path):
        p = tmp_path / "Inception (2010).mkv"
        assert _parse_episode(p) is None


class TestParseMovieTitle:
    def test_with_year(self, tmp_path):
        p = tmp_path / "Inception (2010).mkv"
        title, year = _parse_movie_title(p)
        assert title == "Inception"
        assert year == 2010

    def test_without_year(self, tmp_path):
        p = tmp_path / "Unknown Movie.mkv"
        title, year = _parse_movie_title(p)
        assert title == "Unknown Movie"
        assert year is None

    def test_radarr_dot_separated(self, tmp_path):
        p = tmp_path / "A.Silent.Voice.2016.1080p.BluRay.x264-HAiKU.mkv"
        title, year = _parse_movie_title(p)
        assert title == "A Silent Voice"
        assert year == 2016

    def test_radarr_dot_separated_with_group_tag(self, tmp_path):
        p = tmp_path / "The.Dark.Knight.2008.1080p.BluRay.x264-GROUP[EtHD].mkv"
        title, year = _parse_movie_title(p)
        assert title == "The Dark Knight"
        assert year == 2008


# ── scan_library ──────────────────────────────────────────────────────────────

class TestScanLibrary:
    def test_discovers_movies(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        (movies_dir / "Inception (2010).mkv").write_bytes(b"")
        (movies_dir / "Dune (2021).mkv").write_bytes(b"")

        result = scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        assert result.added == 2
        rows = scan_db.execute("SELECT * FROM media_items WHERE media_type='movie'").fetchall()
        assert len(rows) == 2
        titles = {r["title"] for r in rows}
        assert "Inception" in titles
        assert "Dune" in titles

    def test_discovers_series_sonarr_structure(self, scan_db, tmp_path):
        tv_dir = tmp_path / "tv" / "From (2022)" / "Season 1"
        tv_dir.mkdir(parents=True)
        (tv_dir / "From (2022) - S01E01 - Pilot (1080p).mkv").write_bytes(b"")
        (tv_dir / "From (2022) - S01E02 - Episode 2 (1080p).mkv").write_bytes(b"")

        result = scan_library(scan_db, series_path=str(tmp_path / "tv"), movies_path="/nonexistent")

        assert result.added == 2
        rows = scan_db.execute(
            "SELECT * FROM media_items WHERE media_type='episode'"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["series_name"] == "From"

    def test_detects_existing_source_srt(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Inception (2010).mkv"
        mkv.write_bytes(b"")
        (movies_dir / "Inception (2010).en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        row = scan_db.execute("SELECT has_source_srt FROM media_items").fetchone()
        assert row["has_source_srt"] == 1

    def test_detects_embedded_target_srt(self, scan_db, tmp_path, monkeypatch):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Inception (2010).mkv"
        mkv.write_bytes(b"")

        import translatarr_web.scanner as scanner_mod
        monkeypatch.setattr(scanner_mod, "find_embedded_sub_by_lang", lambda path, tags: 12)

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        row = scan_db.execute("SELECT has_target_srt FROM media_items").fetchone()
        assert row["has_target_srt"] == 1

    def test_detects_existing_target_srt(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Inception (2010).mkv"
        mkv.write_bytes(b"")
        (movies_dir / "Inception (2010).fr.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nBonjour\n")

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        row = scan_db.execute("SELECT has_target_srt FROM media_items").fetchone()
        assert row["has_target_srt"] == 1

    def test_removes_deleted_files(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Old Movie.mkv"
        mkv.write_bytes(b"")

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))
        assert scan_db.execute("SELECT COUNT(*) FROM media_items").fetchone()[0] == 1

        mkv.unlink()
        result = scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))
        assert result.removed == 1
        assert scan_db.execute("SELECT COUNT(*) FROM media_items").fetchone()[0] == 0

    def test_removes_orphan_srt_when_mkv_deleted(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Old Movie (2020).mkv"
        srt = movies_dir / "Old Movie (2020).fr.srt"
        mkv.write_bytes(b"")
        srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nTest\n")

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))
        assert srt.exists()

        mkv.unlink()
        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))
        assert not srt.exists()

    def test_updates_existing_entries(self, scan_db, tmp_path):
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        mkv = movies_dir / "Inception (2010).mkv"
        mkv.write_bytes(b"")

        scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        # Add a target SRT on disk, re-scan
        (movies_dir / "Inception (2010).fr.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nBonjour\n")
        result = scan_library(scan_db, series_path="/nonexistent", movies_path=str(movies_dir))

        assert result.added == 0
        assert result.updated == 1
        row = scan_db.execute("SELECT has_target_srt FROM media_items").fetchone()
        assert row["has_target_srt"] == 1

    def test_nonexistent_dirs_are_skipped(self, scan_db):
        result = scan_library(
            scan_db,
            series_path="/nonexistent/tv",
            movies_path="/nonexistent/movies",
        )
        assert result.added == 0
